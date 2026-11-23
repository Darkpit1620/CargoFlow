from django.contrib import admin
from .models import WorkEvent, WorkTask


@admin.register(WorkTask)
class WorkTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "priority", "assigned_to", "shipment", "due_date", "created_at")
    list_filter = ("status", "priority", "due_date")
    search_fields = ("title", "shipment__tracking_number", "assigned_to__username")
    readonly_fields = ("created_by", "created_at", "updated_at", "completed_at")


@admin.register(WorkEvent)
class WorkEventAdmin(admin.ModelAdmin):
    list_display = ("task", "action", "actor", "created_at")
    list_filter = ("action",)
    readonly_fields = ("task", "action", "actor", "note", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
