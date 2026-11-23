"""Read-only operational insights. No external analytics service or payment gateway."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum, DecimalField, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from billing.models import Invoice, Payment
from deliveries.models import Shipment
from fleet.models import Vehicle
from support_desk.models import SupportCase

ZERO = Decimal('0.00')


def selected_shipments(start, end):
    """Shipments CREATED during the period. Status means CURRENT status."""
    return Shipment.objects.filter(created_at__date__range=(start, end))


def overview(start, end):
    shipments = selected_shipments(start, end)
    shipment_total = shipments.count()
    delivered = shipments.filter(status=Shipment.Status.DELIVERED).count()
    counts = dict(shipments.values_list('status').annotate(n=Count('id')))
    # Build the distribution from declared statuses, including zeros only for populated categories.
    by_status = [
        {'name': label, 'count': counts.get(status, 0),
         'percent': round(counts.get(status, 0) * 100 / shipment_total) if shipment_total else 0}
        for status, label in Shipment.Status.choices if counts.get(status, 0)
    ]
    created_fees = shipments.aggregate(total=Sum('delivery_fee'))['total'] or ZERO
    invoices = Invoice.objects.filter(created_at__date__range=(start, end))
    invoiced = invoices.aggregate(total=Sum('amount'))['total'] or ZERO
    payments = Payment.objects.filter(received_on__range=(start, end))
    received = payments.aggregate(total=Sum('amount'))['total'] or ZERO
    # Outstanding is an ALL-TIME snapshot; independent sums prevent join multiplication.
    all_invoiced = Invoice.objects.aggregate(total=Sum('amount'))['total'] or ZERO
    all_paid = Payment.objects.aggregate(total=Sum('amount'))['total'] or ZERO
    outstanding = max(ZERO, all_invoiced - all_paid)
    paid_by_method = list(payments.values('method').annotate(total=Sum('amount')).order_by('method'))
    method_labels = dict(Payment.Method.choices)
    for row in paid_by_method:
        row['label'] = method_labels.get(row['method'], row['method'])

    # Daily trend intentionally covers only the last 14 dates of the selected period.
    trend_start = max(start, end - timedelta(days=13))
    daily = {
        row['day']: row['count']
        for row in shipments.filter(created_at__date__gte=trend_start)
        .annotate(day=TruncDate('created_at')).values('day')
        .annotate(count=Count('pk')).order_by('day')
    }
    days = [(trend_start + timedelta(days=n)) for n in range((end - trend_start).days + 1)]
    highest = max(daily.values(), default=0)
    trend = [{'date': day, 'count': daily.get(day, 0),
              'width': round(daily.get(day, 0) / highest * 100) if highest else 0}
             for day in days]

    drivers = list(shipments.filter(driver__isnull=False).values('driver_id', 'driver__full_name')
                   .annotate(total=Count('pk'),
                             delivered=Count('pk', filter=Q(status=Shipment.Status.DELIVERED)))
                   .order_by('-delivered', '-total', 'driver__full_name')[:8])
    today = timezone.localdate()
    exceptions = {
        'late_shipments': Shipment.objects.filter(expected_delivery__lt=today)
        .exclude(status__in=[Shipment.Status.DELIVERED, Shipment.Status.CANCELLED]).count(),
        'unresolved_cases': SupportCase.objects.exclude(status=SupportCase.Status.RESOLVED).count(),
        'service_due': Vehicle.objects.filter(next_service_date__lte=today + timedelta(days=7)).count(),
    }
    return {
        'shipment_total': shipment_total, 'delivered': delivered,
        'delivery_rate': round(100 * delivered / shipment_total, 1) if shipment_total else 0,
        'booked_fees': created_fees, 'issued_invoices': invoiced,
        'recorded_payments': received, 'outstanding_all_time': outstanding,
        'status_rows': by_status, 'payment_methods': paid_by_method,
        'trend': trend, 'driver_rows': drivers, **exceptions,
    }


def exceptions_board():
    today = timezone.localdate()
    late = (Shipment.objects.select_related('driver').filter(expected_delivery__lt=today)
            .exclude(status__in=[Shipment.Status.DELIVERED, Shipment.Status.CANCELLED])
            .order_by('expected_delivery', 'pk'))
    failed = (Shipment.objects.select_related('driver').filter(status=Shipment.Status.FAILED)
              .order_by('-updated_at', '-pk'))
    money_field = DecimalField(max_digits=14, decimal_places=2)
    past_due_invoices = (Invoice.objects.select_related('shipment')
                         .filter(due_date__lt=today)
                         .annotate(paid_so_far=Coalesce(Sum('payments__amount'), Value(ZERO), output_field=money_field))
                         .filter(amount__gt=F('paid_so_far'))
                         .order_by('due_date', 'pk'))
    urgent = (SupportCase.objects.select_related('shipment')
              .filter(priority__in=[SupportCase.Priority.HIGH, SupportCase.Priority.URGENT])
              .exclude(status=SupportCase.Status.RESOLVED)
              .order_by('due_date', '-created_at'))
    maintenance = (Vehicle.objects.select_related('assigned_driver')
                   .filter(next_service_date__lte=today + timedelta(days=7))
                   .order_by('next_service_date', 'registration'))
    return {
        'late_rows': late[:25], 'late_count': late.count(),
        'failed_rows': failed[:25], 'failed_count': failed.count(),
        'invoice_rows': past_due_invoices[:25], 'invoice_count': past_due_invoices.count(),
        'case_rows': urgent[:25], 'case_count': urgent.count(),
        'maintenance_rows': maintenance[:25], 'maintenance_count': maintenance.count(),
        'today': today,
    }
