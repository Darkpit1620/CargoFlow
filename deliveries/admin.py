from django.contrib import admin
from .models import Driver, Shipment, TrackingEvent


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "vehicle_registration", "is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name", "phone", "vehicle_registration")


class TrackingEventInline(admin.TabularInline):
    model = TrackingEvent
    extra = 0
    readonly_fields = ("status", "location", "note", "updated_by", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("tracking_number", "recipient_name", "origin", "destination", "status", "driver", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("tracking_number", "recipient_name", "recipient_phone", "origin", "destination")
    readonly_fields = ("tracking_number", "created_at", "updated_at", "delivered_at")
    inlines = [TrackingEventInline]

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ("shipment", "status", "location", "created_at")
    list_filter = ("status",)
    search_fields = ("shipment__tracking_number", "location")
    readonly_fields = ("shipment", "status", "location", "note", "updated_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
