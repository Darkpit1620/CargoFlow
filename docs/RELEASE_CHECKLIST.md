# CargoFlow release checklist

## Development verification

- [ ] The Stage 10 installer completed successfully on the local computer.
- [ ] `python manage.py check` returns no issues.
- [ ] `python manage.py makemigrations --check --dry-run` reports no model changes.
- [ ] `python manage.py migrate --check` reports no pending migrations.
- [ ] `python manage.py test --verbosity 1` passes all project tests.
- [ ] `python manage.py cargo_audit` was reviewed (informational under development settings).
- [ ] Homepage, staff login, dashboard, dispatch, shipping tools, warehouse, billing, analytics, workboard, fleet, and support pages were manually checked.

## GitHub safety

- [ ] The project root is a Git repository; the staged file list was reviewed.
- [ ] Only source code, project documentation, static source assets, and migrations are staged.
- [ ] No `.env`, `.cargoflow-secret`, `.venv`, `db.sqlite3`, backups, real customer data, exported reports, or screenshots with private information are staged.
- [ ] The Stage 10 `check_github_safety.py` returns PASS.
- [ ] The Stage 11 enhanced `verify_release_staging.py` returns PASS.
- [ ] No passwords, tokens, or real personal/customer data were entered in README or commit messages.
- [ ] No production credentials were committed in previous Git history.

## GitHub publishing (deliberate separate action)

Run `git diff --cached --stat`, `git status`, and inspect files, then commit and create a public repository **only when you have reviewed the contents and want to publish**. Publishing is never automatic during the Stage 11 verification step.

## Internet deployment is a separate milestone

- [ ] Configure environment-specific `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and `DJANGO_DEBUG=0`.
- [ ] Verify HTTPS and cookie policies and run `python manage.py check --deploy`.
- [ ] Run `python manage.py cargo_audit --strict`.
- [ ] Provision managed PostgreSQL and plan/validate any migration from SQLite.
- [ ] Configure a production WSGI/ASGI host; never deploy Django development `runserver`.
- [ ] Implement backup, restore, monitoring, incident handling, and data-retention procedures.
- [ ] Review public endpoint throttling and staff permission testing.

**Current scope:** Portfolio-ready after local tests and manual review. No claim of production-grade deployment readiness is made.
