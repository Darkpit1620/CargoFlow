"""Warehouse storage locations and a staff-only physical movement audit trail.

This module does not modify the delivery status or send notifications.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Warehouse(models.Model):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=250, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'pk']

    def __str__(self):
        return f'{self.code} · {self.name}'

    def clean(self):
        super().clean()
        self.code = (self.code or '').strip().upper()
        if not self.code:
            raise ValidationError({'code': 'Enter a warehouse code.'})


class StorageBin(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='bins')
    code = models.CharField(max_length=30)
    description = models.CharField(max_length=160, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['warehouse__name', 'code', 'pk']
        constraints = [models.UniqueConstraint(fields=['warehouse', 'code'], name='warehouse_unique_bin_code')]

    def __str__(self):
        return f'{self.warehouse.code} / {self.code}'

    def clean(self):
        super().clean()
        self.code = (self.code or '').strip().upper()
        if not self.code:
            raise ValidationError({'code': 'Enter a bin code.'})
        if self.warehouse_id and not self.warehouse.is_active:
            raise ValidationError({'warehouse': 'Choose an active warehouse.'})


class ParcelPosition(models.Model):
    """Current physical location. Only warehouse scans change these records."""
    class State(models.TextChoices):
        STORED = 'stored', 'Stored'
        HELD = 'held', 'On hold'
        RELEASED = 'released', 'Checked out'

    shipment = models.OneToOneField('deliveries.Shipment', on_delete=models.CASCADE, related_name='warehouse_position')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='parcel_positions')
    bin = models.ForeignKey(StorageBin, on_delete=models.PROTECT, null=True, blank=True, related_name='parcel_positions')
    state = models.CharField(max_length=12, choices=State.choices, default=State.STORED)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.shipment.tracking_number} @ {self.warehouse.code}'

    def clean(self):
        super().clean()
        if self.bin_id and self.warehouse_id and self.bin.warehouse_id != self.warehouse_id:
            raise ValidationError({'bin': 'The selected bin does not belong to this warehouse.'})
        if self.state == self.State.RELEASED and self.bin_id:
            raise ValidationError({'bin': 'Checked-out shipments cannot occupy a storage bin.'})


class ParcelScan(models.Model):
    """Append-only history through CargoFlow's warehouse UI."""
    class Action(models.TextChoices):
        CHECK_IN = 'check_in', 'Check in'
        MOVE = 'move', 'Move / transfer'
        HOLD = 'hold', 'Place on hold'
        CHECK_OUT = 'check_out', 'Check out'

    shipment = models.ForeignKey('deliveries.Shipment', on_delete=models.CASCADE, related_name='warehouse_scans')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='scans')
    bin = models.ForeignKey(StorageBin, on_delete=models.PROTECT, null=True, blank=True)
    action = models.CharField(max_length=12, choices=Action.choices)
    note = models.CharField(max_length=300, blank=True)
    scanned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'{self.shipment.tracking_number}: {self.get_action_display()}'
