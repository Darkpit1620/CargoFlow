from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import DriverForm, ShipmentForm, StatusForm
from .models import Driver, Shipment


def staff_required(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            return HttpResponseForbidden("Staff access required.")
        return view(request, *args, **kwargs)
    return _wrapped


def home(request):
    return render(request, "deliveries/home.html")


@staff_required
def dashboard(request):
    queryset = Shipment.objects.all()
    context = {
        "total_shipments": queryset.count(),
        "pending_shipments": queryset.filter(status=Shipment.Status.PENDING).count(),
        "active_shipments": queryset.filter(status__in=[Shipment.Status.PICKED_UP, Shipment.Status.IN_TRANSIT, Shipment.Status.OUT_FOR_DELIVERY]).count(),
        "delivered_shipments": queryset.filter(status=Shipment.Status.DELIVERED).count(),
        "booked_fees": queryset.aggregate(total=Sum("delivery_fee"))["total"] or 0,
        "active_drivers": Driver.objects.filter(is_active=True).count(),
        "recent_shipments": queryset.select_related("driver")[:8],
    }
    return render(request, "deliveries/dashboard.html", context)


@staff_required
def shipment_list(request):
    shipments = Shipment.objects.select_related("driver")
    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "").strip()
    if query:
        shipments = shipments.filter(Q(tracking_number__icontains=query) | Q(recipient_name__icontains=query) | Q(origin__icontains=query) | Q(destination__icontains=query))
    if status in Shipment.Status.values:
        shipments = shipments.filter(status=status)
    context = {
        "page_obj": Paginator(shipments, 15).get_page(request.GET.get("page")),
        "query": query,
        "status": status,
        "statuses": Shipment.Status.choices,
    }
    return render(request, "deliveries/shipment_list.html", context)


@staff_required
def shipment_create(request):
    form = ShipmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        shipment = form.save(commit=False)
        shipment.created_by = request.user
        shipment.save()
        event = shipment.events.first()
        if event:
            event.updated_by = request.user
            event.save(update_fields=["updated_by"])
        messages.success(request, f"Shipment {shipment.tracking_number} created.")
        return redirect("shipment-detail", pk=shipment.pk)
    return render(request, "deliveries/shipment_form.html", {"form": form, "title": "New shipment", "action": "Create shipment"})


@staff_required
def shipment_edit(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    form = ShipmentForm(request.POST or None, instance=shipment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shipment details updated.")
        return redirect("shipment-detail", pk=pk)
    return render(request, "deliveries/shipment_form.html", {"form": form, "title": "Edit shipment", "action": "Save changes", "shipment": shipment})


@staff_required
def shipment_detail(request, pk):
    shipment = get_object_or_404(Shipment.objects.select_related("driver", "created_by"), pk=pk)
    form = StatusForm(initial={"status": shipment.status})
    return render(request, "deliveries/shipment_detail.html", {"shipment": shipment, "events": shipment.events.select_related("updated_by"), "status_form": form})


@staff_required
@require_POST
def shipment_change_status(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    form = StatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please choose a valid status.")
        return redirect("shipment-detail", pk=pk)
    new_status = form.cleaned_data["status"]
    if new_status == shipment.status:
        messages.info(request, "Status is unchanged. Choose a different status to add a tracking update.")
        return redirect("shipment-detail", pk=pk)
    shipment.status = new_status
    shipment.save()
    event = shipment.events.first()
    event.location = form.cleaned_data["location"]
    event.note = form.cleaned_data["note"] or "Status updated"
    event.updated_by = request.user
    event.save(update_fields=["location", "note", "updated_by"])
    messages.success(request, "Shipment status updated and tracking event recorded.")
    return redirect("shipment-detail", pk=pk)


@staff_required
def driver_list(request):
    return render(request, "deliveries/driver_list.html", {"drivers": Driver.objects.all()})


@staff_required
def driver_create(request):
    form = DriverForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Driver added successfully.")
        return redirect("driver-list")
    return render(request, "deliveries/shipment_form.html", {"form": form, "title": "Add driver", "action": "Save driver"})


@staff_required
def driver_edit(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    form = DriverForm(request.POST or None, instance=driver)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Driver updated successfully.")
        return redirect("driver-list")
    return render(request, "deliveries/shipment_form.html", {"form": form, "title": "Edit driver", "action": "Save changes"})


def track_shipment(request):
    tracking_number = request.GET.get("code", "").strip()[:60]
    shipment = None
    searched = bool(tracking_number)
    if searched:
        shipment = Shipment.objects.filter(tracking_number__iexact=tracking_number).first()
    return render(request, "deliveries/track.html", {"shipment": shipment, "searched": searched, "code": tracking_number})
