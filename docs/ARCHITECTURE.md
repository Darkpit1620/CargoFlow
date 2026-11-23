# CargoFlow: Architecture

CargoFlow is a Django web application using Django templates for pages and Django REST Framework for selected endpoints. Authentication and staff permissions are managed by Django. There is no live payment gateway in this version.

## Apps and responsibilities

| Django app | Responsibility |
| --- | --- |
| `deliveries` | Shipment, driver and tracking models; staff management; public tracking and REST endpoints |
| `operations` | Dispatch, delivery confirmation, failed attempts and operations reporting |
| `shipping_tools` | QR label rendering, CSV import and driver manifests |
| `support_desk` | Support cases, follow-up history and overdue-work views |
| `fleet` | Fleet vehicles and maintenance records |
| `billing` | Invoice and payment bookkeeping records |
| `insights` | Read-only analytics and operational attention views |
| `workboard` | Staff tasks and progress tracking |
| `warehouse` | Hub, bin and parcel movement records |
| `system_center` | Staff operations summary, selected activity logging and settings checks |

## Request and data flow

1. A browser requests a Django route or a DRF endpoint.
2. Django authenticates the user where required and applies staff permissions on sensitive operations.
3. A view validates input through Django forms or DRF serializers and uses Django ORM models.
4. Models persist to local SQLite by default. A separately provisioned PostgreSQL database may be used through environment configuration.
5. Views render HTML or restricted API responses. Public shipment tracking returns limited information.

## Important boundaries

- A scan in `warehouse` does not itself transition a shipment to a delivered state.
- Cash/M-Pesa/bank entries in `billing` are staff-recorded bookkeeping, **not** bank confirmations.
- Some records in `system_center` are best-effort write observations and should not be treated as immutable audit evidence.
- In production, add access control review, throttling for public tracking, robust logging, error monitoring, retention rules, secure backups, and deployment testing.
