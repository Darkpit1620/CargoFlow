import csv
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from deliveries.models import Driver, Shipment, TrackingEvent
from deliveries.views import staff_required
from .forms import AttemptForm, ConfirmationForm, DriverAssignmentForm
from .models import DeliveryAttempt, DeliveryConfirmation


OPEN_STATUSES = (
    Shipment.Status.PENDING, Shipment.Status.PICKED_UP,
    Shipment.Status.IN_TRANSIT, Shipment.Status.OUT_FOR_DELIVERY,
    Shipment.Status.FAILED,
)


@staff_required
def dispatch_board(request):
    driver_id = request.GET.get("driver", "").strip()
    shipments = Shipment.objects.select_related("driver").filter(status__in=OPEN_STATUSES)
    if driver_id == "unassigned":
        shipments = shipments.filter(driver__isnull=True)
    elif driver_id.isdecimal() and Driver.objects.filter(pk=driver_id).exists():
        shipments = shipments.filter(driver_id=int(driver_id))

    shipments = shipments.order_by("expected_delivery", "-created_at", "-id")[:100]
    all_open = Shipment.objects.filter(status__in=OPEN_STATUSES)
    return render(request, "operations/dispatch.html", {
        "shipments": shipments,
        "active_drivers": Driver.objects.filter(is_active=True),
        "drivers_for_filter": Driver.objects.all(),
        "driver_filter": driver_id,
        "unassigned_count": all_open.filter(driver__isnull=True).count(),
        "assigned_count": all_open.filter(driver__isnull=False).count(),
        "today": timezone.localdate(),
    })


@staff_required
@require_POST
def assign_driver(request, pk):
    form = DriverAssignmentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please select an active driver or Unassigned.")
        return redirect("operations-dispatch")
    with transaction.atomic():
        shipment = get_object_or_404(Shipment.objects.select_for_update(), pk=pk)
        if shipment.status not in OPEN_STATUSES:
            messages.error(request, "Delivered and cancelled shipments cannot be reassigned.")
            return redirect("operations-dispatch")
        new_driver = form.cleaned_data["driver"]
        shipment.driver = new_driver
        shipment.save(update_fields=["driver", "updated_at"])
    messages.success(request, f"Driver assignment updated for {shipment.tracking_number}.")
    return redirect("operations-dispatch")


@staff_required
def confirm_delivery(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    if DeliveryConfirmation.objects.filter(shipment=shipment).exists():
        messages.info(request, "Delivery has already been confirmed.")
        return redirect("shipment-detail", pk=pk)
    if shipment.status == Shipment.Status.CANCELLED:
        messages.error(request, "Cancelled shipments cannot be delivered.")
        return redirect("shipment-detail", pk=pk)

    form = ConfirmationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = get_object_or_404(Shipment.objects.select_for_update(), pk=pk)
            if locked.status == Shipment.Status.CANCELLED or DeliveryConfirmation.objects.filter(shipment=locked).exists():
                messages.error(request, "This shipment was cancelled or has already been confirmed.")
                return redirect("shipment-detail", pk=pk)
            confirmation = form.save(commit=False)
            confirmation.shipment = locked
            confirmation.confirmed_by = request.user
            if locked.status != Shipment.Status.DELIVERED:
                locked.status = Shipment.Status.DELIVERED
                locked.save()
                event = locked.events.first()
                event.note = "Delivery confirmed"
                event.location = form.cleaned_data["location"]
                event.updated_by = request.user
                event.save(update_fields=["note", "location", "updated_by"])
            confirmation.save()
        messages.success(request, "Delivery confirmed and proof of delivery saved.")
        return redirect("shipment-detail", pk=pk)
    return render(request, "operations/confirmation_form.html", {"shipment": shipment, "form": form})


@staff_required
def record_attempt(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    if shipment.status in (Shipment.Status.DELIVERED, Shipment.Status.CANCELLED):
        messages.error(request, "Cannot record a failed attempt for a completed or cancelled shipment.")
        return redirect("shipment-detail", pk=pk)

    form = AttemptForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = get_object_or_404(Shipment.objects.select_for_update(), pk=pk)
            if locked.status in (Shipment.Status.DELIVERED, Shipment.Status.CANCELLED):
                messages.error(request, "This shipment is no longer open for delivery.")
                return redirect("shipment-detail", pk=pk)
            attempt = form.save(commit=False)
            attempt.shipment = locked
            attempt.recorded_by = request.user
            attempt.save()
            if locked.status != Shipment.Status.FAILED:
                locked.status = Shipment.Status.FAILED
                locked.save()
                event = locked.events.first()
                event.note = "Delivery attempt unsuccessful"
                event.location = attempt.location
                event.updated_by = request.user
                event.save(update_fields=["note", "location", "updated_by"])
            else:
                TrackingEvent.objects.create(
                    shipment=locked, status=Shipment.Status.FAILED,
                    location=attempt.location, note="Another delivery attempt was unsuccessful",
                    updated_by=request.user,
                )
        messages.success(request, "Delivery attempt recorded. Customer tracking status updated.")
        return redirect("shipment-detail", pk=pk)
    return render(request, "operations/attempt_form.html", {"shipment": shipment, "form": form})


def _filtered_shipments(request):
    """Use the same date filtering in the reports screen and CSV download."""
    shipments = Shipment.objects.select_related("driver").all()
    raw_start = request.GET.get("from", "")[:10]
    raw_end = request.GET.get("to", "")[:10]
    try:
        start = date.fromisoformat(raw_start) if raw_start else None
        end = date.fromisoformat(raw_end) if raw_end else None
    except ValueError:
        return shipments.none(), raw_start, raw_end, "Please enter valid dates."
    if start and end and start > end:
        return shipments.none(), raw_start, raw_end, "Start date cannot be after end date."
    if start:
        shipments = shipments.filter(created_at__date__gte=start)
    if end:
        shipments = shipments.filter(created_at__date__lte=end)
    return shipments, raw_start, raw_end, ""


@staff_required
def reports(request):
    shipments, start, end, error = _filtered_shipments(request)
    total = shipments.count()
    completed = shipments.filter(status=Shipment.Status.DELIVERED).count()
    fee_sum = shipments.aggregate(total=Sum("delivery_fee"))["total"] or Decimal("0")
    breakdown = {item["status"]: item["count"] for item in shipments.values("status").annotate(count=Count("id"))}
    status_rows = [{"label": label, "value": value, "count": breakdown.get(value, 0)} for value, label in Shipment.Status.choices]
    today = timezone.localdate()
    overdue = shipments.filter(expected_delivery__lt=today).exclude(
        status__in=[Shipment.Status.DELIVERED, Shipment.Status.CANCELLED]
    ).count()
    return render(request, "operations/reports.html", {
        "total": total, "completed": completed,
        "delivery_rate": round(completed * 100 / total, 1) if total else 0,
        "fees": fee_sum, "status_rows": status_rows, "overdue": overdue,
        "from_date": start, "to_date": end, "error": error,
    })


def _csv_safe(value):
    """Prevent spreadsheet formula injection in exported user-input fields."""
    cell = str(value if value is not None else "")
    if cell.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + cell
    return cell


@staff_required
def export_report(request):
    shipments, _start, _end, error = _filtered_shipments(request)
    if error:
        return HttpResponse(error, status=400)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cargoflow_shipments.csv"'
    response.write("\ufeff")  # Excel-readable UTF-8
    writer = csv.writer(response)
    writer.writerow([
        "Tracking number", "Created", "Sender", "Recipient", "Recipient phone",
        "Origin", "Destination", "Driver", "Status", "Weight (kg)",
        "Booked fee (KES)", "Expected delivery", "Delivered at",
    ])
    for item in shipments.iterator():
        writer.writerow([_csv_safe(v) for v in [
            item.tracking_number, timezone.localtime(item.created_at).strftime("%Y-%m-%d %H:%M"),
            item.sender_name, item.recipient_name, item.recipient_phone,
            item.origin, item.destination, item.driver.full_name if item.driver else "",
            item.get_status_display(), item.weight_kg, item.delivery_fee,
            item.expected_delivery or "", timezone.localtime(item.delivered_at).strftime("%Y-%m-%d %H:%M") if item.delivered_at else "",
        ]])
    return response
