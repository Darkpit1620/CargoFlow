# CargoFlow: Local operations and troubleshooting

## Start the server

In your existing CargoFlow folder:

```powershell
& ".\.venv\Scripts\python.exe" manage.py runserver 8003
```

Open `http://127.0.0.1:8003/`. Stop with `Ctrl+C`.

## Test the complete application

```powershell
& ".\.venv\Scripts\python.exe" manage.py check
& ".\.venv\Scripts\python.exe" manage.py makemigrations --check --dry-run
& ".\.venv\Scripts\python.exe" manage.py migrate --check
& ".\.venv\Scripts\python.exe" manage.py test --verbosity 1
```

## Common issues

- **Port already in use:** Stop the previous Django terminal or use a different port.
- **404 at `/favicon.ico`:** Usually harmless; it only indicates no tab icon has been configured.
- **403 on a staff page:** Sign in with a staff account (Django `is_staff=True`).
- **Database migration issues:** Inspect the exact error. Back up `db.sqlite3` before trying a repair. Do not delete the database.
- **Git not installed:** Install Git for Windows and rerun the release prep script; this does not affect the Django application.
- **Missing dependency:** Use the existing `.venv` and install from `requirements.txt`.
- **Stage 11 says Stage 10 missing:** Install/verify Stage 10 first; this release pack deliberately does not install missing earlier stages.
- **Stage 11 checks fail:** Read the report in the ignored `.cargoflow_backups/release_*` folder and copy the failing output to support. The project will not be automatically published.

## Data safeguards

The Stage 11 installer copies the SQLite file into an ignored backup location before updating the README or Git preparation files. It **never alters the active database, runs migrations, drops tables, or writes business records**. If you use PostgreSQL, stop and use a PostgreSQL-aware backup/restore process rather than treating a SQLite snapshot as a safe backup.
