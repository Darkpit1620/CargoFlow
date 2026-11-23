import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from deliveries.models import Shipment
from .forms import PaymentForm
from .models import Invoice, Payment


class BillingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username="billingstaff", password="test-only", is_staff=True)
        cls.user = User.objects.create_user(username="otheruser", password="test-only")
        cls.shipment = Shipment.objects.create(sender_name="Sender", recipient_name="Recipient", recipient_phone="0700000000", origin="Nairobi", destination="Mombasa", weight_kg=Decimal("4.00"), delivery_fee=Decimal("400.00"))

    def staff_login(self):
        self.client.force_login(self.staff)

    def issue(self):
        return Invoice.objects.create(shipment=self.shipment, amount=self.shipment.delivery_fee, due_date=timezone.localdate() + timedelta(days=10), issued_by=self.staff)

    def post_payment(self, invoice, amount="100.00", method="mpesa", reference="AB1234"):
        return self.client.post(reverse("billing-payment-create", args=[invoice.pk]), {
            "amount": amount, "method": method, "reference": reference,
            "received_on": timezone.localdate().isoformat(), "notes": "Verified",
        })

    def test_staff_permissions_and_anonymous_login(self):
        invoice = self.issue()
        urls = [reverse("billing-list"), reverse("billing-export"), reverse("billing-create", args=[self.shipment.pk]), reverse("billing-detail", args=[invoice.pk]), reverse("billing-payment-create", args=[invoice.pk])]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("billing-payment-create", args=[invoice.pk]), {}).status_code, 403)

    def test_creates_invoice_for_shipment_fee_only_once(self):
        self.staff_login()
        url = reverse("billing-create", args=[self.shipment.pk])
        result = self.client.post(url, {"due_date": timezone.localdate().isoformat(), "notes": "Cash on delivery"})
        self.assertEqual(result.status_code, 302)
        inv = Invoice.objects.get()
        self.assertEqual(inv.amount, Decimal("400.00"))
        self.assertEqual(inv.issued_by, self.staff)
        self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_zero_fee_cannot_be_invoiced(self):
        self.shipment.delivery_fee = Decimal("0.00")
        self.shipment.save()
        self.staff_login()
        self.assertEqual(self.client.post(reverse("billing-create", args=[self.shipment.pk]), {}).status_code, 302)
        self.assertFalse(Invoice.objects.exists())

    def test_payment_receipt_and_balance(self):
        invoice = self.issue()
        self.staff_login()
        self.assertEqual(self.post_payment(invoice, "120.00").status_code, 302)
        self.assertEqual(invoice.total_paid, Decimal("120.00"))
        self.assertEqual(invoice.balance, Decimal("280.00"))
        self.assertEqual(invoice.payment_status, "Part paid")
        self.assertContains(self.client.get(reverse("billing-detail", args=[invoice.pk])), "AB1234")
        self.assertEqual(self.post_payment(invoice, "280.00", reference="CD7890").status_code, 302)
        self.assertEqual(invoice.payment_status, "Paid")
        self.assertEqual(invoice.balance, 0)

    def test_overpayment_rejected(self):
        invoice = self.issue()
        self.staff_login()
        response = self.post_payment(invoice, "500.00")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "outstanding invoice balance")
        self.assertFalse(Payment.objects.exists())

    def test_duplicate_mpesa_reference_rejected(self):
        invoice = self.issue()
        Payment.objects.create(invoice=invoice, amount=Decimal("100.00"), method="mpesa", reference="AB1234")
        self.staff_login()
        result = self.post_payment(invoice, "50.00", reference="AB1234")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)

    def test_mpesa_reference_required(self):
        invoice = self.issue()
        self.staff_login()
        response = self.post_payment(invoice, "100.00", reference="")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "payment reference")
        self.assertEqual(Payment.objects.count(), 0)

    def test_future_date_rejected(self):
        invoice = self.issue()
        self.staff_login()
        result = self.client.post(reverse("billing-payment-create", args=[invoice.pk]), {
            "amount": "20.00", "method": "cash", "received_on": (timezone.localdate() + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "future receipt date")
        self.assertEqual(Payment.objects.count(), 0)

    def test_invoice_overdue(self):
        invoice = Invoice.objects.create(shipment=self.shipment, amount=Decimal("400.00"), due_date=timezone.localdate() - timedelta(days=1))
        self.assertTrue(invoice.overdue)
        Payment.objects.create(invoice=invoice, amount=Decimal("400.00"), method="cash")
        self.assertFalse(invoice.overdue)

    def test_csv_export_escapes_formulas(self):
        invoice = self.issue()
        self.shipment.recipient_name = "=2+3"
        self.shipment.save()
        self.staff_login()
        response = self.client.get(reverse("billing-export"))
        self.assertEqual(response.status_code, 200)
        lines = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(lines[1][2], "'=2+3")
        self.assertEqual(lines[1][3], "400.00")

    def test_nav_includes_billing_for_staff(self):
        self.staff_login()
        self.assertContains(self.client.get(reverse("billing-list")), "Billing")
