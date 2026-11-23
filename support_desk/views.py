"""Staff-only support desk: exceptions, case history and overdue deliveries."""
import csv
from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from deliveries.models import Shipment
from deliveries.views import staff_required

from .forms import CaseCreateForm, CaseUpdateForm
from .models import CaseUpdate, SupportCase


FINAL_STATUSES = (Shipment.Status.DELIVERED, Shipment.Status.CANCELLED)


def filtered_cases(request):
    queryset = SupportCase.objects.select_related("shipment", "created_by")
    q = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    if q:
        queryset = queryset.filter(Q(subject__icontains=q) | Q(shipment__tracking_number__icontains=q) | Q(shipment__recipient_name__icontains=q))
    if status in SupportCase.Status.values:
        queryset = queryset.filter(status=status)
    if priority in SupportCase.Priority.values:
        queryset = queryset.filter(priority=priority)
    return queryset, {"query": q, "selected_status": status, "selected_priority": priority}


@staff_required
@require_GET
def case_list(request):
    queryset, filters = filtered_cases(request)
    return render(request, "support_desk/case_list.html", {
        **filters,
        "page_obj": Paginator(queryset, 15).get_page(request.GET.get("page")),
        "statuses": SupportCase.Status.choices,
        "priorities": SupportCase.Priority.choices,
        "open_count": SupportCase.objects.exclude(status=SupportCase.Status.RESOLVED).count(),
        "urgent_count": SupportCase.objects.exclude(status=SupportCase.Status.RESOLVED).filter(priority=SupportCase.Priority.URGENT).count(),
        "overdue_count": Shipment.objects.filter(expected_delivery__lt=timezone.localdate()).exclude(status__in=FINAL_STATUSES).count(),
    })


@staff_required
def case_create(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    form = CaseCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            case = form.save(commit=False)
            case.shipment = shipment
            case.created_by = request.user
            case.save()
            CaseUpdate.objects.create(
                case=case, status=case.status,
                note="Support case created", recorded_by=request.user,
            )
        messages.success(request, "Support case opened successfully.")
        return redirect("support-desk-detail", pk=case.pk)
    return render(request, "support_desk/case_form.html", {"form": form, "shipment": shipment})


@staff_required
@require_GET
def case_detail(request, pk):
    case = get_object_or_404(SupportCase.objects.select_related("shipment", "created_by"), pk=pk)
    return render(request, "support_desk/case_detail.html", {
        "case": case,
        "updates": case.updates.select_related("recorded_by"),
        "form": CaseUpdateForm(initial={"status": case.status}),
    })


@staff_required
@require_POST
def case_update(request, pk):
    form = CaseUpdateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a valid status and keep the note under 1,000 characters.")
        return redirect("support-desk-detail", pk=pk)

    with transaction.atomic():
        case = get_object_or_404(SupportCase.objects.select_for_update(), pk=pk)
        new_status = form.cleaned_data["status"]
        note = form.cleaned_data["note"]
        if case.status == new_status and not note:
            messages.info(request, "Nothing changed. Add a note or select a new status.")
            return redirect("support-desk-detail", pk=pk)
        if case.status != new_status:
            case.set_status(new_status)
            case.save(update_fields=["status", "resolved_at", "updated_at"])
        CaseUpdate.objects.create(case=case, status=new_status, note=note, recorded_by=request.user)
    messages.success(request, "Support case updated. The action was recorded in its private history.")
    return redirect("support-desk-detail", pk=pk)


@staff_required
@require_GET
def overdue_deliveries(request):
    shipments = Shipment.objects.select_related("driver").filter(
        expected_delivery__lt=timezone.localdate()
    ).exclude(status__in=FINAL_STATUSES).order_by("expected_delivery", "id")
    return render(request, "support_desk/overdue.html", {
        "page_obj": Paginator(shipments, 20).get_page(request.GET.get("page")),
        "total": shipments.count(),
        "today": timezone.localdate(),
    })


def excel_safe(value):
    cell = str(value if value is not None else "")
    if cell.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + cell
    return cell


@staff_required
@require_GET
def export_cases(request):
    queryset, _ = filtered_cases(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cargoflow_support_cases.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Case ID", "Tracking number", "Subject", "Category", "Priority", "Status", "Created", "Due date", "Resolved at"])
    for case in queryset.iterator():
        values = [case.pk, case.shipment.tracking_number, case.subject,
                  case.get_category_display(), case.get_priority_display(), case.get_status_display(),
                  timezone.localtime(case.created_at).strftime("%Y-%m-%d %H:%M"),
                  case.due_date or "", timezone.localtime(case.resolved_at).strftime("%Y-%m-%d %H:%M") if case.resolved_at else ""]
        writer.writerow([excel_safe(v) for v in values])
    return response
