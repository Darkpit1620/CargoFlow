from django.conf import settings
from django.db import models
from django.utils import timezone

from deliveries.models import Shipment


class SupportCase(models.Model):
    """Internal customer-support case linked to an existing shipment."""

    class Category(models.TextChoices):
        DELAY = "delay", "Delayed shipment"
        ADDRESS = "address", "Wrong or incomplete address"
        DAMAGE = "damage", "Damaged parcel"
        MISSING = "missing", "Missing parcel"
        CUSTOMER = "customer", "Customer enquiry"
        OTHER = "other", "Other"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="support_cases")
    category = models.CharField(max_length=15, choices=Category.choices)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    subject = models.CharField(max_length=140)
    description = models.TextField(max_length=2000)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="support_cases_created")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Case #{self.pk}: {self.subject}"

    def set_status(self, value):
        self.status = value
        self.resolved_at = timezone.now() if value == self.Status.RESOLVED else None


class CaseUpdate(models.Model):
    """Private, append-only support activity history."""

    case = models.ForeignKey(SupportCase, on_delete=models.CASCADE, related_name="updates")
    status = models.CharField(max_length=15, choices=SupportCase.Status.choices)
    note = models.TextField(max_length=1000, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Case #{self.case_id} updated ({self.status})"
