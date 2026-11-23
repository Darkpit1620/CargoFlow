"""Best-effort staff write-activity trail for CargoFlow screens and API.

Only records authenticated staff writes that returned a successful response
code commonly used for writes. Does not store customer data, request bodies,
or query strings. This trail is intentionally NOT tamper-proof or complete.
"""
import logging

from django.db import DatabaseError

from .models import StaffAction

logger = logging.getLogger(__name__)

# Names are from Django's URL resolver, not from arbitrary request input.
# We only cover CargoFlow screens; login, logout and Django admin are excluded.
PREFIXES = (
    "shipment-", "driver-", "api-shipments-", "api-drivers-",
    "operations-", "shipping-", "support-", "fleet-", "billing-",
    "insights-", "workboard-", "warehouse-",
)
# Stage modules have different route-name styles. Resolved path segments are
# fixed server-side, without storing numeric IDs or other URL parameters.
PATH_PREFIXES = (
    "/shipments/", "/drivers/", "/operations/", "/shipping/",
    "/support/", "/fleet/", "/billing/", "/workboard/", "/warehouse/",
    "/api/shipments/", "/api/drivers/",
)


class StaffActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.is_staff):
            return response
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return response
        # POST forms typically redirect on success; API creates return 201.
        # For other mutation methods, a 2xx success is enough.
        status = response.status_code
        if request.method == "POST" and status not in (201, 202, 204, 301, 302, 303, 307, 308):
            return response
        if request.method != "POST" and not 200 <= status < 300:
            return response
        if not request.path.startswith(PATH_PREFIXES):
            return response
        resolved = getattr(request, "resolver_match", None)
        view_name = getattr(resolved, "view_name", "") if resolved else ""
        # Only store a stable URL route name, never a full URL or a route arg.
        if not view_name:
            return response
        try:
            StaffAction.objects.create(
                actor=user, http_method=request.method,
                view_name=view_name[:140], response_status=status,
            )
        except DatabaseError:
            # Do not turn a successful shipment operation into an HTTP 500
            # if the activity table is temporarily unavailable.
            logger.warning("Could not store an operational activity record.")
        return response
