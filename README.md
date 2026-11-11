# Library cabin booker

Every night just after 00:00 (Amsterdam) this books **Bibliotheek LRC → studiecabine 1, 10:00–13:00** for the next day.

## Setup (5 min)
1. Create a new **private** GitHub repo and upload these files (keep the `.github/workflows/` folder).
2. Repo → Settings → Secrets and variables → Actions → New repository secret:
   `LIBRARY_EMAIL` = the email you use for werkplekreservering.
3. Actions tab → enable workflows → "Book library study cabin" → Run workflow (leave *Dry run* ticked) to test the login.

## Notes
- Change times/days in `.github/workflows/book-library.yml` (`START`, `END`, `DAYS`). Library max is 3 hours.
- Library limit: max 2 open bookings at LRC.
- GitHub pauses scheduled workflows after 60 days with no repo activity — you'll get an email; click "enable" to resume.
