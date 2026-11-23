from django.contrib import admin
from .models import ServiceRecord, Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration", "make", "model_name", "status", "assigned_driver", "next_service_date")
    list_filter = ("kind", "status", "next_service_date")
    search_fields = ("registration", "make", "model_name", "assigned_driver__full_name")
    list_select_related = ("assigned_driver",)


@admin.register(ServiceRecord)
class ServiceRecordAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "service_date", "service_type", "cost", "next_due_date", "recorded_by")
    list_filter = ("service_type", "service_date")
    search_fields = ("vehicle__registration", "description")
    list_select_related = ("vehicle", "recorded_by")
