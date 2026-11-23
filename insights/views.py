"""Staff-only, read-only reports. Money shown is ledger data, not bank verification."""
import csv
from datetime import timedelta

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone

from deliveries.views import staff_required
from .forms import ReportDateForm
from .services import exceptions_board, overview, selected_shipments


def date_range_form(request):
    today = timezone.localdate()
    default = {'start': today - timedelta(days=29), 'end': today}
    if 'start' not in request.GET and 'end' not in request.GET:
        return ReportDateForm(initial=default), default
    form = ReportDateForm(request.GET)
    if form.is_valid():
        return form, form.cleaned_data
    return form, None


def csv_safe(value):
    """Prevent Excel/Sheets formula execution for cells containing user input."""
    cell = str(value if value is not None else '')
    if cell.lstrip().startswith(('=', '+', '-', '@')) or cell.startswith(('\t', '\r', '\n')):
        return "'" + cell
    return cell


@staff_required
def insights_dashboard(request):
    form, period = date_range_form(request)
    data = overview(period['start'], period['end']) if period else None
    return render(request, 'insights/dashboard.html', {'filter_form': form, 'period': period, 'summary': data})


@staff_required
def insights_exceptions(request):
    return render(request, 'insights/exceptions.html', exceptions_board())


@staff_required
def insights_export(request):
    form, period = date_range_form(request)
    if not period:
        return HttpResponseBadRequest('Invalid reporting period. Use valid dates up to 366 days.')
    result = HttpResponse(content_type='text/csv; charset=utf-8')
    result['Content-Disposition'] = 'attachment; filename="cargoflow_shipments_analytics.csv"'
    result.write('\ufeff')
    writer = csv.writer(result)
    writer.writerow(['Tracking number', 'Created date', 'Current status', 'Sender', 'Recipient', 'Origin',
                     'Destination', 'Driver', 'Expected delivery', 'Delivered date', 'Booked fee (KES)'])
    for shipment in selected_shipments(period['start'], period['end']).select_related('driver').order_by('created_at', 'pk').iterator():
        writer.writerow([
            csv_safe(shipment.tracking_number), timezone.localtime(shipment.created_at).date().isoformat(),
            shipment.get_status_display(), csv_safe(shipment.sender_name), csv_safe(shipment.recipient_name),
            csv_safe(shipment.origin), csv_safe(shipment.destination),
            csv_safe(shipment.driver.full_name if shipment.driver else ''),
            shipment.expected_delivery.isoformat() if shipment.expected_delivery else '',
            timezone.localtime(shipment.delivered_at).date().isoformat() if shipment.delivered_at else '',
            shipment.delivery_fee,
        ])
    return result
