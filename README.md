# CargoFlow

**CargoFlow** is a Django 5.2 / Django REST Framework logistics operations application for managing shipments, last-mile delivery, warehouse movement, vehicles, billing, customer support, and operational reporting. It was built as a full-stack portfolio project.

> **Status:** Local development and portfolio demonstration. This application is not yet certified for production or for processing real customer payments. Cash, M-Pesa, and bank payments are recorded manually after staff verification; no funds are transferred.

## Features

| Area | Functions | Local URL |
| --- | --- | --- |
| Shipments | Create, search, and update shipments; view progress | `/shipments/` |
| Tracking | Limited public shipment-status lookup | `/track/` |
| Dispatch | Assign drivers, record attempts, confirm delivery | `/operations/dispatch/` |
| Shipping tools | QR shipping labels, bulk CSV import, driver manifests | `/shipping/manifest/` |
| Support | Log and resolve delivery issues, flag overdue deliveries | `/support/` |
| Fleet | Register vehicles, assignments, service reminders | `/fleet/` |
| Billing | Invoices, payment records, outstanding balances | `/billing/` |
| Analytics | Activity trends, balances, driver performance | `/insights/` |
| Team workboard | Assign tasks, deadlines, private operational notes | `/workboard/` |
| Warehouse | Hubs, storage bins, parcel movement history | `/warehouse/` |
| System Center | Staff activity overview and basic security readiness | `/system/` |
| REST API | Staff-protected shipment/driver APIs, limited public tracking | `/api/` |

## Technology

- Python 3.10+ and Django 5.2 LTS
- Django REST Framework
- HTML, CSS and Django templates
- SQLite for local development; PostgreSQL can be configured separately
- QR labels powered by the `qrcode` Python package

## Run locally (Windows PowerShell)

Clone the repository and open its folder in VS Code. Then run:

```powershell
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" manage.py migrate
& ".\.venv\Scripts\python.exe" manage.py createsuperuser
& ".\.venv\Scripts\python.exe" manage.py runserver 8003
```

Visit `http://127.0.0.1:8003/`. A local development secret is generated automatically in `.cargoflow-secret` (which is excluded from Git). Staff pages require an account with `is_staff=True`; the superuser can access them.

> **Existing installs:** Do not delete your existing `db.sqlite3`, `.venv`, migrations, or backups. The instructions above are for a **fresh clone**. A fresh clone intentionally starts without other people's records.

## Validation

```powershell
& ".\.venv\Scripts\python.exe" manage.py check
& ".\.venv\Scripts\python.exe" manage.py makemigrations --check --dry-run
& ".\.venv\Scripts\python.exe" manage.py test --verbosity 1
& ".\.venv\Scripts\python.exe" check_github_safety.py
```

To check deployment readiness in a separately configured production-like environment, run `python manage.py check --deploy` and `python manage.py cargo_audit --strict`. These are expected to warn or fail under local development settings.

## Important design notes

- Public tracking is intentionally limited. Private staff APIs and management pages require staff authentication.
- Warehouse scan activity and shipment delivery status are separate histories.
- Billing records are informational. **Do not** interpret them as a verified payment gateway or accounting system.
- The staff activity log is best-effort, not an immutable regulatory audit log.
- The installer-derived migrations are committed to support reproducible setup.

## Security and deployment

Never commit databases, credentials, private exports, locally generated secrets, `.venv/`, or backup directories. Review [the release checklist](docs/RELEASE_CHECKLIST.md) before publishing. Production hosting requires a separate deployment process, HTTPS, proper secrets management, database backups, and a real security review.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Operations and troubleshooting](docs/OPERATIONS.md)

## License

No license has been selected. Add an appropriate `LICENSE` file after reviewing your intended terms before inviting contributions or reuse.
