import csv
from io import StringIO
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from deliveries.models import Shipment
from .models import ParcelPosition, ParcelScan, StorageBin, Warehouse


class WarehouseWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username='warehouse_staff', password='localtest', is_staff=True)
        cls.user = User.objects.create_user(username='warehouse_customer', password='localtest')
        cls.hub = Warehouse.objects.create(code='NBO', name='Nairobi hub', city='Nairobi')
        cls.second_hub = Warehouse.objects.create(code='MBA', name='Mombasa hub', city='Mombasa')
        cls.bin = StorageBin.objects.create(warehouse=cls.hub, code='A1')
        cls.second_bin = StorageBin.objects.create(warehouse=cls.second_hub, code='B1')
        cls.shipment = Shipment.objects.create(
            sender_name='Sender', recipient_name='Alice', recipient_phone='0700111222',
            origin='Nairobi', destination='Mombasa', weight_kg='2.00', delivery_fee='350.00',
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def scan(self, action, hub=None, bin_obj=None, shipment=None, note=''):
        return self.client.post(reverse('warehouse-scan'), {
            'shipment': (shipment or self.shipment).pk,
            'action': action,
            'warehouse': (hub or self.hub).pk,
            'bin': bin_obj.pk if bin_obj else '',
            'note': note,
        })

    def test_all_paths_require_staff(self):
        urls = [reverse('warehouse-dashboard'), reverse('warehouse-new-hub'),
                reverse('warehouse-new-bin'), reverse('warehouse-scan'), reverse('warehouse-export')]
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.client.force_login(self.user)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.client.post(reverse('warehouse-scan'), {
            'shipment': self.shipment.pk, 'action': 'check_in', 'warehouse': self.hub.pk,
        }).status_code, 403)
        self.assertFalse(ParcelPosition.objects.exists())

    def test_dashboard_and_forms_render(self):
        for url in [reverse('warehouse-dashboard'), reverse('warehouse-new-hub'),
                    reverse('warehouse-new-bin'), reverse('warehouse-scan')]:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertFalse(ParcelScan.objects.exists())

    def test_new_warehouse_and_bin(self):
        result = self.client.post(reverse('warehouse-new-hub'), {
            'code': '  ksm  ', 'name': 'Kisumu store', 'city': 'Kisumu', 'address': 'Warehouse Street', 'is_active': 'on',
        })
        self.assertEqual(result.status_code, 302)
        hub = Warehouse.objects.get(code='KSM')
        result = self.client.post(reverse('warehouse-new-bin'), {
            'warehouse': hub.pk, 'code': ' d4 ', 'description': 'Upper rack', 'is_active': 'on',
        })
        self.assertEqual(result.status_code, 302)
        self.assertTrue(StorageBin.objects.filter(warehouse=hub, code='D4').exists())

    def test_check_in_creates_position_and_history_without_delivery_change(self):
        before = self.shipment.status
        response = self.scan('check_in', bin_obj=self.bin, note='Shelf 1')
        self.assertEqual(response.status_code, 302)
        position = ParcelPosition.objects.get(shipment=self.shipment)
        self.assertEqual(position.state, ParcelPosition.State.STORED)
        self.assertEqual(position.bin, self.bin)
        self.assertEqual(position.updated_by, self.staff)
        scan = ParcelScan.objects.get(shipment=self.shipment)
        self.assertEqual(scan.note, 'Shelf 1')
        self.assertEqual(scan.scanned_by, self.staff)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, before)

    def test_move_hold_checkout_then_recheckin(self):
        self.assertEqual(self.scan('check_in', bin_obj=self.bin).status_code, 302)
        self.assertEqual(self.scan('move', hub=self.second_hub, bin_obj=self.second_bin).status_code, 302)
        self.assertEqual(self.scan('hold', hub=self.second_hub, note='Awaiting inspection').status_code, 302)
        self.assertEqual(ParcelPosition.objects.get(shipment=self.shipment).state, 'held')
        self.assertEqual(self.scan('check_out', hub=self.second_hub).status_code, 302)
        current = ParcelPosition.objects.get(shipment=self.shipment)
        self.assertEqual(current.state, 'released')
        self.assertIsNone(current.bin)
        self.assertEqual(self.scan('check_in', hub=self.hub).status_code, 302)
        self.assertEqual(ParcelPosition.objects.get(shipment=self.shipment).state, 'stored')
        self.assertEqual(ParcelScan.objects.filter(shipment=self.shipment).count(), 5)

    def test_invalid_move_without_checkin(self):
        response = self.scan('move', bin_obj=self.bin)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Check this parcel in')
        self.assertEqual(ParcelScan.objects.count(), 0)

    def test_double_check_in_is_rejected(self):
        self.scan('check_in')
        response = self.scan('check_in')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ParcelScan.objects.count(), 1)

    def test_invalid_bin_warehouse_combo_rejected(self):
        response = self.scan('check_in', hub=self.hub, bin_obj=self.second_bin)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bin must belong')
        self.assertFalse(ParcelPosition.objects.exists())

    def test_checkout_wrong_hub_and_bin_rejected(self):
        self.scan('check_in', bin_obj=self.bin)
        self.assertEqual(self.scan('check_out', hub=self.second_hub).status_code, 200)
        self.assertEqual(self.scan('check_out', bin_obj=self.bin).status_code, 200)
        self.assertEqual(ParcelPosition.objects.get(shipment=self.shipment).state, 'stored')

    def test_delivered_shipment_cannot_be_checked_in(self):
        self.shipment.status = Shipment.Status.DELIVERED
        self.shipment.save()
        response = self.scan('check_in')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ParcelPosition.objects.exists())

    def test_csv_exports_filters_and_escapes_spreadsheet_formulas(self):
        self.shipment.recipient_name = '=HYPERLINK("http://example.invalid")'
        self.shipment.save()
        self.scan('check_in', bin_obj=self.bin)
        response = self.client.get(reverse('warehouse-export'), {'state': 'stored'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], "'=HYPERLINK(\"http://example.invalid\")")
        response = self.client.get(reverse('warehouse-export'), {'state': 'held'})
        self.assertEqual(len(list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))), 1)

    def test_notes_are_escaped_in_dashboard(self):
        self.scan('check_in', note='<script>alert(1)</script>')
        response = self.client.get(reverse('warehouse-dashboard'))
        self.assertNotContains(response, '<script>')
        self.assertContains(response, '&lt;script&gt;', html=False)

    def test_csrf_protects_scan_form(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(reverse('warehouse-scan'), {
            'shipment': self.shipment.pk, 'action': 'check_in', 'warehouse': self.hub.pk,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ParcelPosition.objects.exists())
