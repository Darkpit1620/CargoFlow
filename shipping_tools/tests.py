import csv
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from deliveries.models import Driver, Shipment


class ShippingToolsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user('shipping_staff', password='TestPass23444!', is_staff=True)
        cls.other = User.objects.create_user('not_staff', password='TestPass23444!')
        cls.driver = Driver.objects.create(full_name='Test Driver', phone='0712345678')
        cls.shipment = Shipment.objects.create(
            sender_name='Sender', recipient_name='Recipient Secret',
            recipient_phone='0711111111', origin='Nairobi', destination='Mombasa',
            weight_kg=Decimal('3.00'), delivery_fee=Decimal('600.00'),
            driver=cls.driver, created_by=cls.staff,
        )

    def file(self, text, name='shipments.csv'):
        return SimpleUploadedFile(name, text.encode('utf-8'), content_type='text/csv')

    def example_csv(self, recipient='New Recipient', weight='2.5'):
        return ("sender_name,recipient_name,recipient_phone,origin,destination,weight_kg,delivery_fee\n"
                f"Some sender,{recipient},0700000000,Nairobi,Kisumu,{weight},250.00\n")

    def test_staff_can_print_label_and_qr_svg(self):
        self.client.force_login(self.staff)
        label = self.client.get(reverse('shipping-label', args=[self.shipment.pk]))
        self.assertEqual(label.status_code, 200)
        self.assertContains(label, self.shipment.tracking_number)
        self.assertContains(label, 'Recipient Secret')
        qr = self.client.get(reverse('shipping-qr', args=[self.shipment.pk]))
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr['Content-Type'], 'image/svg+xml')
        self.assertIn(b'<svg', qr.content)
        self.assertNotIn(b'Recipient Secret', qr.content)

    def test_all_shipping_pages_require_staff(self):
        paths = [
            reverse('shipping-label', args=[self.shipment.pk]),
            reverse('shipping-qr', args=[self.shipment.pk]),
            reverse('shipping-bulk-import'),
            reverse('shipping-import-template'),
            reverse('shipping-manifest'),
            reverse('shipping-manifest-export') + '?driver=' + str(self.driver.pk),
        ]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302, path)
        self.client.force_login(self.other)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 403, path)

    def test_missing_shipment_returns_404(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('shipping-label', args=[99999])).status_code, 404)
        self.assertEqual(self.client.get(reverse('shipping-qr', args=[99999])).status_code, 404)

    def test_template_is_csv_with_required_headers(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('shipping-import-template'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('sender_name', resp.content.decode('utf-8-sig'))

    def test_valid_bulk_import_creates_tracking_events(self):
        self.client.force_login(self.staff)
        before = Shipment.objects.count()
        resp = self.client.post(reverse('shipping-bulk-import'), {
            'file': self.file(self.example_csv()),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Shipment.objects.count(), before + 1)
        new = Shipment.objects.get(recipient_name='New Recipient')
        self.assertEqual(new.created_by, self.staff)
        self.assertEqual(new.events.count(), 1)
        self.assertEqual(new.events.first().updated_by, self.staff)
        self.assertTrue(new.tracking_number.startswith('CF-'))

    def test_invalid_bulk_import_is_all_or_nothing(self):
        self.client.force_login(self.staff)
        text = self.example_csv() + 'Sender,Second,0712345678,Nairobi,Mombasa,not-a-number,100\n'
        before = Shipment.objects.count()
        resp = self.client.post(reverse('shipping-bulk-import'), {'file': self.file(text)})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Nothing was imported')
        self.assertEqual(Shipment.objects.count(), before)

    def test_bad_csv_and_too_large_file_rejected(self):
        self.client.force_login(self.staff)
        bad = self.client.post(reverse('shipping-bulk-import'), {'file': self.file('weird,field\na,b\n')})
        self.assertContains(bad, 'Missing required columns')
        self.assertEqual(Shipment.objects.count(), 1)
        large = SimpleUploadedFile('shipments.csv', b'x' * (1024*1024+1))
        resp = self.client.post(reverse('shipping-bulk-import'), {'file': large})
        self.assertContains(resp, 'too large')
        self.assertEqual(Shipment.objects.count(), 1)

    def test_csv_formula_injection_is_protected_in_manifest(self):
        self.shipment.recipient_name = '=HYPERLINK("bad")'
        self.shipment.save()
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('shipping-manifest-export'), {'driver': self.driver.pk})
        self.assertEqual(resp.status_code, 200)
        rows = list(csv.reader(StringIO(resp.content.decode('utf-8-sig'))))
        self.assertTrue(rows[1][1].startswith("'="))

    def test_manifest_has_only_driver_open_shipments(self):
        other_driver = Driver.objects.create(full_name='Other driver', phone='0700000000')
        Shipment.objects.create(sender_name='Two', recipient_name='Another', recipient_phone='0700000000',
                                origin='Nairobi', destination='Eldoret', weight_kg='1.00', driver=other_driver)
        delivered = Shipment.objects.create(sender_name='Two', recipient_name='Completed', recipient_phone='0700000000',
                                            origin='Nairobi', destination='Kisumu', weight_kg='1.00', driver=self.driver)
        delivered.status = Shipment.Status.DELIVERED
        delivered.save()
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('shipping-manifest'), {'driver': self.driver.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.shipment.tracking_number)
        self.assertNotContains(resp, 'Another')
        self.assertNotContains(resp, 'Completed')
        exported = self.client.get(reverse('shipping-manifest-export'), {'driver': self.driver.pk})
        self.assertEqual(exported.status_code, 200)
        rows = list(csv.reader(StringIO(exported.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 2)

    def test_manifest_requires_valid_driver(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('shipping-manifest-export')).status_code, 400)
        self.assertEqual(self.client.get(reverse('shipping-manifest-export'), {'driver': 'not-a-number'}).status_code, 400)
        self.assertEqual(self.client.get(reverse('shipping-manifest-export'), {'driver': '987654'}).status_code, 400)

    def test_import_get_does_not_change_database(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('shipping-bulk-import')).status_code, 200)
        self.assertEqual(Shipment.objects.count(), 1)
