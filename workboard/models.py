"""Internal shipment-related work tasks. No messages are sent externally."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class WorkTask(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    title = models.CharField(max_length=180)
    description = models.TextField(max_length=2000, blank=True)
    shipment = models.ForeignKey(
        "deliveries.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="work_tasks",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cargoflow_assigned_tasks", limit_choices_to={"is_staff": True, "is_active": True},
    )
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cargoflow_created_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.title

    @property
    def overdue(self):
        return bool(self.due_date and self.due_date < timezone.localdate() and self.status != self.Status.DONE)


class WorkEvent(models.Model):
    """Simple immutable audit trail for actions performed through the workboard UI."""
    task = models.ForeignKey(WorkTask, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=32)
    note = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.task_id}: {self.action}"
