import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import Invoice, Payment
from deliveries.models import Driver, Shipment
from fleet.models import Vehicle
from support_desk.models import SupportCase

from .forms import ReportDateForm
from .services import exceptions_board, overview


class InsightsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username='insights_staff', password='strong-example-123', is_staff=True)
        cls.viewer = User.objects.create_user(username='insights_viewer', password='strong-example-123')
        cls.today = timezone.localdate()
        cls.driver = Driver.objects.create(full_name='Test Driver', phone='0700000000')
        cls.shipment = Shipment.objects.create(
            sender_name='Test Sender', recipient_name='=2+3', recipient_phone='0700000001',
            origin='Nairobi', destination='Kisumu', weight_kg=Decimal('2.00'),
            delivery_fee=Decimal('400.00'), driver=cls.driver,
            expected_delivery=cls.today - timedelta(days=1), created_by=cls.staff,
        )
        cls.invoice = Invoice.objects.create(shipment=cls.shipment, amount=Decimal('400.00'),
                                            due_date=cls.today - timedelta(days=2))
        Payment.objects.create(invoice=cls.invoice, amount=Decimal('100.00'),
                               method=Payment.Method.MPESA, reference='TEST-MP-001', received_on=cls.today)

    def login_staff(self):
        self.client.force_login(self.staff)

    def test_all_insights_pages_restrict_nonstaff_and_anonymous(self):
        for name in ['insights-dashboard', 'insights-attention', 'insights-export']:
            url = reverse(name)
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.viewer)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.logout()

    def test_default_dashboard_and_date_filter(self):
        self.login_staff()
        response = self.client.get(reverse('insights-dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Operations insights')
        self.assertContains(response, '400.00')
        self.assertEqual(response.context['summary']['shipment_total'], 1)
        self.assertEqual(response.context['summary']['recorded_payments'], Decimal('100.00'))
        self.assertEqual(response.context['summary']['outstanding_all_time'], Decimal('300.00'))
        url = reverse('insights-dashboard') + '?start={}&end={}'.format(
            (self.today - timedelta(days=1)).isoformat(), self.today.isoformat())
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_empty_report_is_safe_and_outstanding_still_all_time(self):
        self.login_staff()
        date = (self.today - timedelta(days=40)).isoformat()
        response = self.client.get(reverse('insights-dashboard'), {'start': date, 'end': date})
        self.assertEqual(response.context['summary']['shipment_total'], 0)
        self.assertEqual(response.context['summary']['delivery_rate'], 0)
        self.assertEqual(response.context['summary']['outstanding_all_time'], Decimal('300.00'))

    def test_invalid_date_ranges_rejected_without_export(self):
        self.login_staff()
        earlier = (self.today - timedelta(days=7)).isoformat()
        now = self.today.isoformat()
        tomorrow = (self.today + timedelta(days=1)).isoformat()
        for values in [
            {'start': now, 'end': earlier},
            {'start': earlier, 'end': tomorrow},
            {'start': (self.today - timedelta(days=367)).isoformat(), 'end': now},
            {'start': 'not-a-date', 'end': now},
            {'start': now},
        ]:
            response = self.client.get(reverse('insights-dashboard'), values)
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.context['summary'])
            self.assertEqual(self.client.get(reverse('insights-export'), values).status_code, 400)

    def test_csv_is_staff_only_and_escapes_formulas(self):
        self.login_staff()
        response = self.client.get(reverse('insights-export'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][4], "'=2+3")
        self.assertEqual(rows[1][-1], '400.00')
        self.assertNotIn('0700000001', response.content.decode('utf-8-sig'))

    def test_report_driver_and_current_status_metrics(self):
        self.shipment.status = Shipment.Status.DELIVERED
        self.shipment.save()
        report = overview(self.today - timedelta(days=29), self.today)
        self.assertEqual(report['shipment_total'], 1)
        self.assertEqual(report['delivered'], 1)
        self.assertEqual(report['delivery_rate'], 100)
        self.assertEqual(report['driver_rows'][0]['delivered'], 1)
        self.assertEqual(report['payment_methods'][0]['method'], 'mpesa')
        self.assertEqual(report['late_shipments'], 0)

    def test_attention_board_partial_invoice_and_overdue_items(self):
        SupportCase.objects.create(shipment=self.shipment, category=SupportCase.Category.DELAY,
                                   priority=SupportCase.Priority.URGENT, subject='Late parcel',
                                   description='Follow up with driver')
        Vehicle.objects.create(registration='KDA123X', make='Ford', model_name='Transit',
                               capacity_kg=Decimal('350.00'), next_service_date=self.today)
        self.login_staff()
        response = self.client.get(reverse('insights-attention'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['late_count'], 1)
        self.assertEqual(response.context['invoice_count'], 1)
        self.assertEqual(response.context['case_count'], 1)
        self.assertEqual(response.context['maintenance_count'], 1)
        self.assertContains(response, 'Late parcel')
        self.assertContains(response, 'KDA123X')
        Payment.objects.create(invoice=self.invoice, amount=Decimal('300.00'), method=Payment.Method.CASH)
        self.assertEqual(exceptions_board()['invoice_count'], 0)

    def test_delivered_or_cancelled_shipment_not_overdue(self):
        self.shipment.status = Shipment.Status.DELIVERED
        self.shipment.save()
        self.assertEqual(exceptions_board()['late_count'], 0)
        self.shipment.status = Shipment.Status.CANCELLED
        self.shipment.save()
        self.assertEqual(exceptions_board()['late_count'], 0)
