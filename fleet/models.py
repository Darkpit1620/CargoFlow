from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from deliveries.models import Driver


class Vehicle(models.Model):
    class Kind(models.TextChoices):
        VAN = "van", "Van"
        TRUCK = "truck", "Truck"
        CAR = "car", "Car"
        MOTORCYCLE = "motorcycle", "Motorcycle"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ON_ROUTE = "on_route", "On route"
        MAINTENANCE = "maintenance", "Under maintenance"
        INACTIVE = "inactive", "Inactive"

    registration = models.CharField(max_length=30, unique=True)
    make = models.CharField(max_length=80)
    model_name = models.CharField("Model", max_length=80)
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.VAN)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.AVAILABLE)
    capacity_kg = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    mileage_km = models.PositiveIntegerField(default=0)
    assigned_driver = models.OneToOneField(
        Driver, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fleet_vehicle",
        help_text="Fleet assignment only. Dispatch assignments remain managed separately.",
    )
    last_service_date = models.DateField(null=True, blank=True)
    next_service_date = models.DateField(null=True, blank=True)
    notes = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["registration", "id"]

    def __str__(self):
        return self.registration

    def clean(self):
        super().clean()
        errors = {}
        if self.last_service_date and self.next_service_date and self.next_service_date <= self.last_service_date:
            errors["next_service_date"] = "Next service date must be after the last service date."
        if self.assigned_driver_id and not self.assigned_driver.is_active:
            errors["assigned_driver"] = "Choose an active driver."
        if errors:
            raise ValidationError(errors)

    @property
    def service_overdue(self):
        return bool(self.next_service_date and self.next_service_date < timezone.localdate())

    @property
    def service_due_soon(self):
        return bool(self.next_service_date and self.next_service_date <= timezone.localdate() + timedelta(days=30))


class ServiceRecord(models.Model):
    class Type(models.TextChoices):
        ROUTINE = "routine", "Routine service"
        REPAIR = "repair", "Repair"
        INSPECTION = "inspection", "Inspection"
        OTHER = "other", "Other"

    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="service_records")
    service_date = models.DateField(default=timezone.localdate)
    service_type = models.CharField(max_length=15, choices=Type.choices, default=Type.ROUTINE)
    description = models.TextField(max_length=1500)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    mileage_km = models.PositiveIntegerField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-service_date", "-id"]

    def __str__(self):
        return f"{self.vehicle.registration}: {self.get_service_type_display()} on {self.service_date}"

    def clean(self):
        super().clean()
        errors = {}
        if self.service_date and self.service_date > timezone.localdate():
            errors["service_date"] = "Record completed services only. Future appointments are not service records."
        if self.next_due_date and self.service_date and self.next_due_date <= self.service_date:
            errors["next_due_date"] = "The next service must be after this service date."
        if errors:
            raise ValidationError(errors)
