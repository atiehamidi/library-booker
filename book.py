#!/usr/bin/env python3
"""
Nightly booker for Bibliotheek Utrecht "Werken in de bibliotheek".

Books Bibliotheek LRC -> Werkplek HushMeet (studiecabine) -> studiecabine 1,
10:00-13:00, for TOMORROW, right after Amsterdam midnight (when that day opens).

Only uses the Python standard library. Config via environment variables:
  LIBRARY_EMAIL   (required) the email you use for werkplekreservering
  START / END     default 10:00 / 13:00   (library max is 3 hours)
  LOCATION        default 47  (Bibliotheek LRC)
  TYPE            default 39  (Werkplek HushMeet (studiecabine))
  RESOURCE        default 568 (studiecabine 1)
  DAYS            weekdays to book, Mon=1..Sun=7, default "1,2,3,4,5,6,7"
  TARGET_DATE     optional YYYY-MM-DD override (for manual runs)
  WAIT_FOR_MIDNIGHT  "1" (default) = if started before midnight, sleep until 00:00:05
  DRY_RUN         "1" = log in and check, but don't submit the booking
"""
import datetime as dt
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

BASE = "https://bibliotheekutrecht.crmplatform.nl/reserveringen"
TZ = ZoneInfo("Europe/Amsterdam")

EMAIL = os.environ.get("LIBRARY_EMAIL", "").strip()
START = os.environ.get("START", "10:00")
END = os.environ.get("END", "13:00")
LOCATION = os.environ.get("LOCATION", "47")
TYPE = os.environ.get("TYPE", "39")
RESOURCE = os.environ.get("RESOURCE", "568")
DAYS = {int(d) for d in os.environ.get("DAYS", "1,2,3,4,5,6,7").split(",") if d.strip()}
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
WAIT = os.environ.get("WAIT_FOR_MIDNIGHT", "1") == "1"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def log(msg):
    print(f"[{dt.datetime.now(TZ):%Y-%m-%d %H:%M:%S %Z}] {msg}", flush=True)


def req(method, url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    r = urllib.request.Request(url, data=body, method=method, headers={
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/page/reservering.vm",
        **({"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"} if body else {}),
    })
    try:
        with opener.open(r, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), url


def login():
    q = urllib.parse.urlencode({"emailadres": EMAIL})
    status, _, final = req("GET", f"{BASE}/werkplekkenVerificatie.vm?{q}")
    if "reservering.vm" not in final:
        raise SystemExit(f"Login failed (status {status}, ended at {final}). Is LIBRARY_EMAIL right?")
    log("Logged in.")


def location_info():
    status, body, _ = req("GET", f"{BASE}/page/js/locations.vm")
    return json.loads(body)[LOCATION]


def reservations(date):
    q = urllib.parse.urlencode({"location": LOCATION, "type": TYPE, "date": date})
    status, body, _ = req("POST", f"{BASE}/page/js/reservations.vm?{q}")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def wait_for_midnight():
    now = dt.datetime.now(TZ)
    midnight = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
    secs = (midnight - now).total_seconds()
    if now.hour >= 20 and secs > 0:  # started in the evening -> wait for the new day to open
        log(f"Waiting {int(secs)}s until {midnight:%H:%M:%S} for the new day to open…")
        time.sleep(secs)


def main():
    if not EMAIL:
        raise SystemExit("Set LIBRARY_EMAIL.")
    if WAIT and not os.environ.get("TARGET_DATE"):
        wait_for_midnight()

    today = dt.datetime.now(TZ).date()
    target = dt.date.fromisoformat(os.environ["TARGET_DATE"]) if os.environ.get("TARGET_DATE") \
        else today + dt.timedelta(days=1)
    if target.isoweekday() not in DAYS:
        log(f"{target} ({target:%A}) is not in DAYS={sorted(DAYS)} — nothing to do.")
        return

    log(f"Target: {target} {START}-{END}, location {LOCATION}, resource {RESOURCE}")
    login()

    loc = location_info()
    log(f"{loc.get('shortname')}: open {loc.get('openingtime')}-{loc.get('closingtime')}, "
        f"your bookings here {loc.get('user-orders')}/{loc.get('max-orders')}, "
        f"max {loc.get('max-hours')}h, window {loc.get('max-days')} days")
    if loc.get("user-orders", 0) >= loc.get("max-orders", 99):
        raise SystemExit("You're at the max number of bookings for this location — cancel one first.")

    data = {"location": LOCATION, "type": TYPE, "date": target.isoformat(),
            "start": START, "end": END, "resource": RESOURCE}

    if DRY_RUN:
        r = reservations(target.isoformat())
        mine = [x for x in r.get("reservations", []) if str(x.get("resource")) == RESOURCE]
        log(f"DRY RUN — would POST {data}. Existing bookings on that cabin: {mine}. Blocks: {r.get('blocks')}")
        return

    last = ""
    for attempt in range(1, 13):  # ~6 minutes of retries in case the day opens a bit late
        status, body, _ = req("POST", f"{BASE}/page/makereservation.vm", data)
        if 200 <= status < 300:
            log(f"✅ Booked {target} {START}-{END}. Server said: {body[:300]}")
            return
        try:
            last = json.loads(body).get("result", body)
        except json.JSONDecodeError:
            last = body[:300]
        log(f"Attempt {attempt} failed ({status}): {last}")
        time.sleep(30)

    raise SystemExit(f"❌ Could not book {target}: {last}")


if __name__ == "__main__":
    main()
