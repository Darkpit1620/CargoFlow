"""Staff-only internal task board, with POST-only changes and event tracking."""
import csv
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from deliveries.models import Shipment
from deliveries.views import staff_required
from .forms import WorkNoteForm, WorkTaskForm
from .models import WorkEvent, WorkTask


def filtered_tasks(request):
    qs = WorkTask.objects.select_related("assigned_to", "shipment", "created_by")
    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "").strip()
    ownership = request.GET.get("owner", "").strip()
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(shipment__tracking_number__icontains=query))
    if status in WorkTask.Status.values:
        qs = qs.filter(status=status)
    else:
        status = ""
    if ownership == "mine":
        qs = qs.filter(assigned_to=request.user)
    elif ownership != "all":
        ownership = "all"
    return qs, query, status, ownership


@staff_required
def task_list(request):
    qs, query, status, ownership = filtered_tasks(request)
    return render(request, "workboard/list.html", {
        "page_obj": Paginator(qs, 20).get_page(request.GET.get("page")),
        "query": query, "status": status, "ownership": ownership,
        "statuses": WorkTask.Status.choices,
        "open_count": WorkTask.objects.exclude(status=WorkTask.Status.DONE).count(),
        "my_count": WorkTask.objects.filter(assigned_to=request.user).exclude(status=WorkTask.Status.DONE).count(),
        "late_count": WorkTask.objects.filter(due_date__lt=timezone.localdate()).exclude(status=WorkTask.Status.DONE).count(),
    })


@staff_required
def task_create(request):
    form = WorkTaskForm(request.POST or None)
    if request.method == "GET":
        shipment_id = request.GET.get("shipment", "")
        if shipment_id.isdecimal() and Shipment.objects.filter(pk=int(shipment_id)).exists():
            form.fields["shipment"].initial = int(shipment_id)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            WorkEvent.objects.create(task=task, actor=request.user, action="created", note="Task created")
        messages.success(request, "Task created.")
        return redirect("workboard-detail", pk=task.pk)
    return render(request, "workboard/form.html", {"form": form, "heading": "Create team task", "action": "Create task"})


@staff_required
def task_detail(request, pk):
    task = get_object_or_404(WorkTask.objects.select_related("shipment", "assigned_to", "created_by"), pk=pk)
    return render(request, "workboard/detail.html", {
        "task": task,
        "events": task.events.select_related("actor"),
        "note_form": WorkNoteForm(),
        "statuses": WorkTask.Status.choices,
    })


@staff_required
def task_edit(request, pk):
    task = get_object_or_404(WorkTask, pk=pk)
    form = WorkTaskForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            WorkEvent.objects.create(task=task, actor=request.user, action="edited", note="Task details updated")
        messages.success(request, "Task updated.")
        return redirect("workboard-detail", pk=task.pk)
    return render(request, "workboard/form.html", {"form": form, "heading": "Edit team task", "action": "Save changes", "task": task})


@staff_required
@require_POST
def task_status(request, pk):
    new_status = request.POST.get("status", "")
    if new_status not in WorkTask.Status.values:
        return HttpResponseBadRequest("Invalid task status")
    with transaction.atomic():
        task = get_object_or_404(WorkTask.objects.select_for_update(), pk=pk)
        if task.status == new_status:
            messages.info(request, "Status is unchanged.")
        else:
            old = task.status
            task.status = new_status
            task.completed_at = timezone.now() if new_status == WorkTask.Status.DONE else None
            task.save(update_fields=["status", "completed_at", "updated_at"])
            WorkEvent.objects.create(
                task=task, actor=request.user, action="status", note=f"{old} -> {new_status}",
            )
            messages.success(request, "Task status updated.")
    return redirect("workboard-detail", pk=pk)


@staff_required
@require_POST
def task_note(request, pk):
    task = get_object_or_404(WorkTask, pk=pk)
    form = WorkNoteForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a note of 1000 characters or fewer.")
    else:
        WorkEvent.objects.create(task=task, actor=request.user, action="note", note=form.cleaned_data["note"])
        messages.success(request, "Private note saved.")
    return redirect("workboard-detail", pk=pk)


def safe_csv(value):
    cell = str(value if value is not None else "")
    if cell.lstrip().startswith(("=", "+", "-", "@")) or cell.startswith(("\t", "\r", "\n")):
        return "'" + cell
    return cell


@staff_required
def task_export(request):
    qs, _, _, _ = filtered_tasks(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cargoflow_team_tasks.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["ID", "Task title", "Tracking number", "Priority", "Status", "Assigned staff", "Due date", "Created date", "Completed date"])
    for task in qs.iterator():
        writer.writerow([
            task.pk, safe_csv(task.title), safe_csv(task.shipment.tracking_number if task.shipment else ""),
            task.get_priority_display(), task.get_status_display(),
            safe_csv(task.assigned_to.username if task.assigned_to else ""),
            task.due_date.isoformat() if task.due_date else "",
            timezone.localtime(task.created_at).date().isoformat(),
            timezone.localtime(task.completed_at).date().isoformat() if task.completed_at else "",
        ])
    return response
