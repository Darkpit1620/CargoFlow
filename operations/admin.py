from django.contrib import admin
from .models import DeliveryAttempt, DeliveryConfirmation


@admin.register(DeliveryConfirmation)
class DeliveryConfirmationAdmin(admin.ModelAdmin):
    list_display = ("shipment", "received_by", "confirmed_at", "confirmed_by")
    search_fields = ("shipment__tracking_number", "received_by")
    readonly_fields = ("shipment", "received_by", "location", "note", "confirmed_by", "confirmed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = ("shipment", "reason", "recorded_at", "next_attempt_on")
    list_filter = ("reason", "recorded_at")
    search_fields = ("shipment__tracking_number",)
    readonly_fields = ("shipment", "reason", "location", "internal_note", "next_attempt_on", "recorded_by", "recorded_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
