from django.contrib import admin
from .models import Warehouse, StorageBin, ParcelPosition, ParcelScan


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'city', 'is_active')
    search_fields = ('code', 'name', 'city')


@admin.register(StorageBin)
class StorageBinAdmin(admin.ModelAdmin):
    list_display = ('code', 'warehouse', 'is_active')
    list_filter = ('warehouse', 'is_active')


@admin.register(ParcelPosition)
class ParcelPositionAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'warehouse', 'bin', 'state', 'updated_at')
    list_filter = ('state', 'warehouse')
    readonly_fields = ('shipment', 'warehouse', 'bin', 'state', 'updated_by', 'updated_at')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ParcelScan)
class ParcelScanAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'action', 'warehouse', 'bin', 'scanned_by', 'created_at')
    list_filter = ('action', 'warehouse')
    readonly_fields = ('shipment', 'warehouse', 'bin', 'action', 'note', 'scanned_by', 'created_at')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
