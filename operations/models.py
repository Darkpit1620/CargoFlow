from django.conf import settings
from django.db import models
from deliveries.models import Shipment


class DeliveryConfirmation(models.Model):
    """Internal proof-of-delivery record. Never displayed on public tracking."""
    shipment = models.OneToOneField(Shipment, on_delete=models.CASCADE, related_name="delivery_confirmation")
    received_by = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=255, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    confirmed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-confirmed_at", "-id"]

    def __str__(self):
        return f"Delivered: {self.shipment.tracking_number}"


class DeliveryAttempt(models.Model):
    class Reason(models.TextChoices):
        RECIPIENT_UNAVAILABLE = "recipient_unavailable", "Recipient unavailable"
        ADDRESS_ISSUE = "address_issue", "Address issue"
        UNREACHABLE = "unreachable", "Could not contact recipient"
        REFUSED = "refused", "Delivery refused"
        OTHER = "other", "Other"

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="delivery_attempts")
    reason = models.CharField(max_length=25, choices=Reason.choices)
    location = models.CharField(max_length=120, blank=True)
    internal_note = models.CharField(max_length=255, blank=True)
    next_attempt_on = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at", "-id"]

    def __str__(self):
        return f"Attempt {self.id}: {self.shipment.tracking_number}"
