from functools import wraps

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render

from .models import StaffAction


def staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            return HttpResponseForbidden("Staff access required.")
        return view(request, *args, **kwargs)
    return wrapped


def counts():
    specs = [
        ("Shipments", "deliveries", "Shipment"),
        ("Drivers", "deliveries", "Driver"),
        ("Delivery confirmations", "operations", "DeliveryConfirmation"),
        ("Support cases", "support_desk", "SupportCase"),
        ("Fleet vehicles", "fleet", "Vehicle"),
        ("Invoices", "billing", "Invoice"),
        ("Payments recorded", "billing", "Payment"),
        ("Workboard tasks", "workboard", "WorkTask"),
        ("Warehouses", "warehouse", "Warehouse"),
        ("Parcel scans", "warehouse", "ParcelScan"),
    ]
    return [
        {"label": label, "count": apps.get_model(app, model).objects.count()}
        for label, app, model in specs
    ]


def readiness():
    return [
        ("Debug mode turned off", not settings.DEBUG,
         "Development mode is fine locally but must be off when deployed."),
        ("HTTPS redirect enabled", bool(getattr(settings, "SECURE_SSL_REDIRECT", False)),
         "Enable only when HTTPS is properly configured."),
        ("Session cookie sent only over HTTPS", bool(settings.SESSION_COOKIE_SECURE),
         "Required for production HTTPS sessions."),
        ("CSRF cookie sent only over HTTPS", bool(settings.CSRF_COOKIE_SECURE),
         "Required when deployed over HTTPS."),
        ("Clickjacking protection enabled", settings.X_FRAME_OPTIONS == "DENY",
         "Restrict pages from being framed by other websites."),
        ("HTTP Strict Transport Security configured", bool(getattr(settings, "SECURE_HSTS_SECONDS", 0)),
         "Enable only once HTTPS is proven working on your domain."),
    ]


@staff_required
def dashboard(request):
    context = {
        "metrics": counts(),
        "readiness": readiness(),
        "staff_count": get_user_model().objects.filter(is_active=True, is_staff=True).count(),
        "recent_actions": StaffAction.objects.select_related("actor")[:10],
        "development_mode": settings.DEBUG,
    }
    return render(request, "system_center/dashboard.html", context)


@staff_required
def activity(request):
    logs = StaffAction.objects.select_related("actor")
    page = Paginator(logs, 30).get_page(request.GET.get("page"))
    return render(request, "system_center/activity.html", {"page_obj": page})
