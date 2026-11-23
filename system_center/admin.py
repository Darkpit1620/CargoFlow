from django.contrib import admin
from .models import StaffAction


@admin.register(StaffAction)
class StaffActionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "http_method", "view_name", "response_status")
    list_filter = ("http_method", "created_at")
    search_fields = ("view_name", "actor__username")
    readonly_fields = ("actor", "http_method", "view_name", "response_status", "created_at")
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
