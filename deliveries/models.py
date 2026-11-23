import secrets
from datetime import date

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


def make_tracking_number():
    """Unpredictable, short reference suitable for sharing with a customer."""
    return f"CF-{date.today():%Y%m%d}-{secrets.token_hex(5).upper()}"


class Driver(models.Model):
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    vehicle_registration = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name", "id"]

    def __str__(self):
        return self.full_name


class Shipment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PICKED_UP = "picked_up", "Picked up"
        IN_TRANSIT = "in_transit", "In transit"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Delivery failed"
        CANCELLED = "cancelled", "Cancelled"

    tracking_number = models.CharField(max_length=40, unique=True, default=make_tracking_number, editable=False)
    sender_name = models.CharField(max_length=120)
    recipient_name = models.CharField(max_length=120)
    recipient_phone = models.CharField(max_length=30)
    recipient_email = models.EmailField(blank=True)
    origin = models.CharField(max_length=120)
    destination = models.CharField(max_length=120)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0.01)])
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name="shipments")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
    expected_delivery = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cargo_shipments")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.tracking_number

    def save(self, *args, **kwargs):
        with transaction.atomic():
            old_status = None
            if self.pk:
                old_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if self.status == self.Status.DELIVERED and self.delivered_at is None:
                self.delivered_at = timezone.now()
            elif self.status != self.Status.DELIVERED:
                self.delivered_at = None
            super().save(*args, **kwargs)
            if old_status != self.status:
                TrackingEvent.objects.create(
                    shipment=self, status=self.status,
                    location=self.origin if old_status is None else "",
                    note="Shipment created" if old_status is None else "Status updated",
                )


class TrackingEvent(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=24, choices=Shipment.Status.choices)
    location = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=255, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.shipment.tracking_number} – {self.get_status_display()}"
