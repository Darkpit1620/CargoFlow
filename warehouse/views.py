"""Warehouse operations for staff, independent of delivery status changes."""
import csv
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from deliveries.models import Shipment
from deliveries.views import staff_required
from .forms import WarehouseForm, StorageBinForm, ParcelScanForm
from .models import Warehouse, StorageBin, ParcelPosition, ParcelScan


def _position_query(request):
    query = request.GET.get('q', '').strip()[:100]
    selection = request.GET.get('state', '').strip()
    qs = ParcelPosition.objects.select_related('shipment', 'warehouse', 'bin', 'updated_by')
    if query:
        qs = qs.filter(Q(shipment__tracking_number__icontains=query) |
                       Q(shipment__recipient_name__icontains=query) |
                       Q(warehouse__code__icontains=query) |
                       Q(bin__code__icontains=query))
    if selection in ParcelPosition.State.values:
        qs = qs.filter(state=selection)
    else:
        selection = ''
    return qs.order_by('-updated_at', '-pk'), query, selection


@staff_required
def dashboard(request):
    qs, query, selection = _position_query(request)
    return render(request, 'warehouse/dashboard.html', {
        'page_obj': Paginator(qs, 20).get_page(request.GET.get('page')),
        'hubs': Warehouse.objects.prefetch_related('bins').all(),
        'recent_scans': ParcelScan.objects.select_related('shipment', 'warehouse', 'scanned_by')[:10],
        'hub_count': Warehouse.objects.filter(is_active=True).count(),
        'stored_count': ParcelPosition.objects.filter(state=ParcelPosition.State.STORED).count(),
        'hold_count': ParcelPosition.objects.filter(state=ParcelPosition.State.HELD).count(),
        'query': query, 'selection': selection, 'states': ParcelPosition.State.choices,
    })


@staff_required
@require_http_methods(['GET', 'POST'])
def new_hub(request):
    form = WarehouseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Warehouse created.')
        return redirect('warehouse-dashboard')
    return render(request, 'warehouse/form.html', {
        'title': 'Add warehouse', 'form': form, 'submit': 'Create warehouse',
    })


@staff_required
@require_http_methods(['GET', 'POST'])
def new_bin(request):
    form = StorageBinForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Storage bin created.')
        return redirect('warehouse-dashboard')
    return render(request, 'warehouse/form.html', {
        'title': 'Add storage bin', 'form': form, 'submit': 'Create bin',
    })


@staff_required
@require_http_methods(['GET', 'POST'])
def scan_parcel(request):
    initial = {}
    sid = request.GET.get('shipment', '')
    if sid.isdecimal() and Shipment.objects.filter(pk=int(sid)).exists():
        initial['shipment'] = int(sid)
    form = ParcelScanForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        values = form.cleaned_data
        with transaction.atomic():
            # Revalidate against the latest physical position inside the transaction.
            shipment = Shipment.objects.select_for_update().get(pk=values['shipment'].pk)
            position = ParcelPosition.objects.select_for_update().filter(shipment=shipment).first()
            action = values['action']
            hub = values['warehouse']
            storage_bin = values['bin']
            if action == ParcelScan.Action.CHECK_IN:
                allowed = position is None or position.state == ParcelPosition.State.RELEASED
            else:
                allowed = position is not None and position.state != ParcelPosition.State.RELEASED
            if action == ParcelScan.Action.CHECK_OUT and position and position.warehouse_id != hub.pk:
                allowed = False
            if action == ParcelScan.Action.HOLD and position and position.warehouse_id != hub.pk:
                allowed = False
            if action == ParcelScan.Action.HOLD and position and position.state == ParcelPosition.State.HELD:
                allowed = False
            if action != ParcelScan.Action.CHECK_OUT and shipment.status in (Shipment.Status.DELIVERED, Shipment.Status.CANCELLED):
                allowed = False
            if not allowed:
                form.add_error('action', 'This parcel changed location or status. Refresh and try again.')
            else:
                state = {
                    ParcelScan.Action.CHECK_IN: ParcelPosition.State.STORED,
                    ParcelScan.Action.MOVE: ParcelPosition.State.STORED,
                    ParcelScan.Action.HOLD: ParcelPosition.State.HELD,
                    ParcelScan.Action.CHECK_OUT: ParcelPosition.State.RELEASED,
                }[action]
                # Checked-out parcel retains its last warehouse, but never occupies a bin.
                position, _ = ParcelPosition.objects.update_or_create(
                    shipment=shipment,
                    defaults={'warehouse': hub, 'bin': None if state == ParcelPosition.State.RELEASED else storage_bin,
                              'state': state, 'updated_by': request.user},
                )
                ParcelScan.objects.create(
                    shipment=shipment, warehouse=hub,
                    bin=None if state == ParcelPosition.State.RELEASED else storage_bin,
                    action=action, note=values['note'].strip(), scanned_by=request.user,
                )
        if not form.errors:
            messages.success(request, f'{shipment.tracking_number}: warehouse scan recorded.')
            return redirect('warehouse-dashboard')
    return render(request, 'warehouse/form.html', {
        'title': 'Record parcel scan', 'form': form, 'submit': 'Save scan',
        'help_text': 'Warehouse scans do not update delivery status. Check in before moving, holding, or checking out.',
    })


def csv_safe(value):
    cell = str(value if value is not None else '')
    if cell.lstrip().startswith(('=', '+', '-', '@')) or cell.startswith(('\r', '\n', '\t')):
        return "'" + cell
    return cell


@staff_required
def export_positions(request):
    qs, _, _ = _position_query(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="cargoflow_warehouse_positions.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Tracking number', 'Recipient', 'Warehouse', 'Bin', 'State', 'Last updated', 'Updated by'])
    for item in qs.iterator():
        writer.writerow([
            csv_safe(item.shipment.tracking_number), csv_safe(item.shipment.recipient_name),
            csv_safe(item.warehouse.code), csv_safe(item.bin.code if item.bin else ''),
            item.get_state_display(), item.updated_at.isoformat(),
            csv_safe(item.updated_by.username if item.updated_by else ''),
        ])
    return response
