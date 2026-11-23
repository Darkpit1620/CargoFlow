"""Internal billing ledger. Payment records are entered by staff, not processed here."""
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from deliveries.models import Shipment


def new_invoice_number():
    return f"CFI-{timezone.localdate():%Y%m%d}-{secrets.token_hex(5).upper()}"


def default_due_date():
    return timezone.localdate() + timedelta(days=14)


class Invoice(models.Model):
    shipment = models.OneToOneField(Shipment, on_delete=models.PROTECT, related_name="billing_invoice")
    invoice_number = models.CharField(max_length=40, unique=True, default=new_invoice_number, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    due_date = models.DateField(default=default_due_date)
    notes = models.TextField(max_length=500, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.invoice_number

    @property
    def total_paid(self):
        return self.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    @property
    def balance(self):
        return max(Decimal("0.00"), self.amount - self.total_paid)

    @property
    def payment_status(self):
        paid = self.total_paid
        if paid >= self.amount:
            return "Paid"
        return "Part paid" if paid else "Unpaid"

    @property
    def overdue(self):
        return self.due_date < timezone.localdate() and self.balance > 0


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa (record only)"
        BANK = "bank", "Bank transfer (record only)"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField(max_length=12, choices=Method.choices)
    reference = models.CharField(max_length=80, blank=True, help_text="Transaction reference for M-Pesa or bank payment")
    notes = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    received_on = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["method", "reference"], condition=~Q(reference=""), name="billing_unique_method_reference"),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number}: {self.amount} ({self.get_method_display()})"

    def clean(self):
        super().clean()
        errors = {}
        self.reference = (self.reference or "").strip().upper()
        if self.method in (self.Method.MPESA, self.Method.BANK) and not self.reference:
            errors["reference"] = "Enter the payment reference for this method."
        if self.received_on and self.received_on > timezone.localdate():
            errors["received_on"] = "Payments cannot have a future receipt date."
        if self.invoice_id and self.amount is not None and self.amount > 0:
            existing = Payment.objects.filter(invoice_id=self.invoice_id)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            paid = existing.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            # This check complements a row lock in the view for concurrent updates.
            if self.amount > self.invoice.amount - paid:
                errors["amount"] = "Amount exceeds the outstanding invoice balance."
        if errors:
            raise ValidationError(errors)
