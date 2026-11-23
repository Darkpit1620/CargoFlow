import csv
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from deliveries.views import staff_required
from .forms import ServiceRecordForm, VehicleForm
from .models import ServiceRecord, Vehicle


def _filtered_vehicles(request):
    queryset = Vehicle.objects.select_related("assigned_driver")
    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "").strip()
    if query:
        queryset = queryset.filter(
            Q(registration__icontains=query) | Q(make__icontains=query)
            | Q(model_name__icontains=query) | Q(assigned_driver__full_name__icontains=query)
        )
    if status in Vehicle.Status.values:
        queryset = queryset.filter(status=status)
    else:
        status = ""
    return queryset, query, status


def _csv_cell(value):
    """Stop user-supplied vehicle fields being interpreted as formulas in Excel."""
    text = str(value if value is not None else "")
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


@staff_required
def vehicle_list(request):
    qs, query, status = _filtered_vehicles(request)
    today = timezone.localdate()
    all_vehicles = Vehicle.objects.all()
    return render(request, "fleet/vehicle_list.html", {
        "page_obj": Paginator(qs, 20).get_page(request.GET.get("page")),
        "query": query, "selected_status": status, "statuses": Vehicle.Status.choices,
        "total_count": all_vehicles.count(),
        "active_count": all_vehicles.filter(status__in=[Vehicle.Status.AVAILABLE, Vehicle.Status.ON_ROUTE]).count(),
        "maintenance_count": all_vehicles.filter(status=Vehicle.Status.MAINTENANCE).count(),
        "service_due_count": all_vehicles.filter(next_service_date__lte=today + timedelta(days=30)).count(),
    })


@staff_required
def vehicle_create(request):
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save()
        messages.success(request, f"Vehicle {vehicle.registration} added.")
        return redirect("fleet-detail", pk=vehicle.pk)
    return render(request, "fleet/vehicle_form.html", {"form": form, "heading": "Add a vehicle", "action": "Save vehicle"})


@staff_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    form = VehicleForm(request.POST or None, instance=vehicle)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vehicle details updated.")
        return redirect("fleet-detail", pk=vehicle.pk)
    return render(request, "fleet/vehicle_form.html", {
        "form": form, "heading": f"Edit {vehicle.registration}", "action": "Save changes", "vehicle": vehicle,
    })


@staff_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle.objects.select_related("assigned_driver"), pk=pk)
    service_history = vehicle.service_records.select_related("recorded_by")[:100]
    totals = vehicle.service_records.aggregate(total=Sum("cost"))
    return render(request, "fleet/vehicle_detail.html", {
        "vehicle": vehicle, "service_history": service_history, "service_cost_total": totals["total"] or 0,
    })


@staff_required
def service_create(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    form = ServiceRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Lock the selected vehicle before updating the service summary.
            vehicle = Vehicle.objects.select_for_update().get(pk=vehicle.pk)
            record = form.save(commit=False)
            record.vehicle = vehicle
            record.recorded_by = request.user
            record.save()
            if vehicle.last_service_date is None or record.service_date >= vehicle.last_service_date:
                vehicle.last_service_date = record.service_date
                vehicle.next_service_date = record.next_due_date
                if record.mileage_km is not None:
                    vehicle.mileage_km = max(vehicle.mileage_km, record.mileage_km)
                vehicle.save(update_fields=["last_service_date", "next_service_date", "mileage_km", "updated_at"])
        messages.success(request, "Maintenance record saved.")
        return redirect("fleet-detail", pk=pk)
    return render(request, "fleet/service_form.html", {"form": form, "vehicle": vehicle})


@staff_required
def service_due(request):
    today = timezone.localdate()
    cutoff = today + timedelta(days=30)
    qs = Vehicle.objects.select_related("assigned_driver").filter(next_service_date__lte=cutoff).order_by("next_service_date", "registration")
    return render(request, "fleet/service_due.html", {
        "page_obj": Paginator(qs, 30).get_page(request.GET.get("page")),
        "today": today, "cutoff": cutoff, "overdue_count": qs.filter(next_service_date__lt=today).count(),
        "due_count": qs.count(),
    })


@staff_required
def vehicle_export(request):
    qs, _, _ = _filtered_vehicles(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cargoflow_fleet.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Registration", "Make", "Model", "Type", "Status", "Capacity (kg)", "Mileage (km)", "Assigned driver", "Last service", "Next service"])
    for vehicle in qs.iterator():
        writer.writerow([
            _csv_cell(vehicle.registration), _csv_cell(vehicle.make), _csv_cell(vehicle.model_name),
            vehicle.get_kind_display(), vehicle.get_status_display(), vehicle.capacity_kg, vehicle.mileage_km,
            _csv_cell(vehicle.assigned_driver.full_name if vehicle.assigned_driver else ""),
            vehicle.last_service_date or "", vehicle.next_service_date or "",
        ])
    return response
