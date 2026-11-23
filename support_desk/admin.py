from django.contrib import admin

from .models import CaseUpdate, SupportCase


class CaseUpdateInline(admin.TabularInline):
    model = CaseUpdate
    extra = 0
    can_delete = False
    readonly_fields = ("status", "note", "recorded_by", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SupportCase)
class SupportCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "shipment", "category", "priority", "status", "created_at")
    list_filter = ("status", "category", "priority")
    search_fields = ("subject", "shipment__tracking_number", "shipment__recipient_name")
    readonly_fields = ("created_by", "created_at", "updated_at", "resolved_at")
    inlines = (CaseUpdateInline,)


@admin.register(CaseUpdate)
class CaseUpdateAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "status", "recorded_by", "created_at")
    readonly_fields = ("case", "status", "note", "recorded_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
