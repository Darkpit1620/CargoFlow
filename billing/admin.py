from django.contrib import admin
from .models import Invoice, Payment


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "shipment", "amount", "due_date", "created_at")
    search_fields = ("invoice_number", "shipment__tracking_number")
    readonly_fields = ("invoice_number", "shipment", "amount", "issued_by", "created_at")

    def has_add_permission(self, request):
        return False  # New invoices must go through shipment billing view.

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "method", "reference", "received_on", "recorded_by")
    search_fields = ("invoice__invoice_number", "reference")
    readonly_fields = ("invoice", "amount", "method", "reference", "notes", "received_on", "recorded_by", "created_at")

    def has_add_permission(self, request):
        return False  # Require the locked balance-validation payment form.

    def has_delete_permission(self, request, obj=None):
        return False
