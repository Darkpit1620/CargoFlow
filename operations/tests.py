import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from deliveries.models import Driver, Shipment
from .models import DeliveryAttempt, DeliveryConfirmation


class CargoFlowOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user("dispatcher", password="TestSecurePassword55!", is_staff=True)
        cls.other = User.objects.create_user("visitor", password="TestSecurePassword55!")
        cls.driver = Driver.objects.create(full_name="Driver A", phone="0712345678", is_active=True)
        cls.inactive = Driver.objects.create(full_name="Driver B", phone="0712340000", is_active=False)
        cls.shipment = Shipment.objects.create(
            sender_name="Sender", recipient_name="Customer", recipient_phone="0700000000",
            origin="Nairobi", destination="Mombasa", weight_kg=Decimal("1.50"),
            delivery_fee=Decimal("400.00"), expected_delivery=timezone.localdate() - timedelta(days=1),
        )

    def test_dispatch_requires_staff(self):
        self.assertEqual(self.client.get(reverse("operations-dispatch")).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("operations-dispatch")).status_code, 403)

    def test_staff_sees_unassigned_shipment(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("operations-dispatch"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.shipment.tracking_number)
        self.assertContains(response, "Waiting for a driver")

    def test_assign_driver_post_and_unassign(self):
        self.client.force_login(self.staff)
        route = reverse("operations-assign", args=[self.shipment.pk])
        self.assertEqual(self.client.get(route).status_code, 405)
        self.assertEqual(self.client.post(route, {"driver": self.driver.pk}).status_code, 302)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.driver, self.driver)
        self.client.post(route, {"driver": ""})
        self.shipment.refresh_from_db()
        self.assertIsNone(self.shipment.driver)

    def test_inactive_driver_rejected(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("operations-assign", args=[self.shipment.pk]), {"driver": self.inactive.pk})
        self.assertEqual(response.status_code, 302)
        self.shipment.refresh_from_db()
        self.assertIsNone(self.shipment.driver)

    def test_delivered_shipment_cannot_be_assigned(self):
        self.shipment.status = Shipment.Status.DELIVERED
        self.shipment.save()
        self.client.force_login(self.staff)
        self.client.post(reverse("operations-assign", args=[self.shipment.pk]), {"driver": self.driver.pk})
        self.shipment.refresh_from_db()
        self.assertIsNone(self.shipment.driver)

    def test_delivery_confirmation_adds_proof_and_event(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("operations-confirm", args=[self.shipment.pk]), {
            "received_by": "Reception desk", "location": "Mombasa", "note": "Signed in person",
        })
        self.assertEqual(response.status_code, 302)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, Shipment.Status.DELIVERED)
        self.assertIsNotNone(self.shipment.delivered_at)
        proof = DeliveryConfirmation.objects.get(shipment=self.shipment)
        self.assertEqual(proof.confirmed_by, self.staff)
        self.assertEqual(proof.received_by, "Reception desk")
        self.assertEqual(self.shipment.events.count(), 2)

    def test_repeat_delivery_confirmation_does_not_duplicate(self):
        self.client.force_login(self.staff)
        route = reverse("operations-confirm", args=[self.shipment.pk])
        data = {"received_by": "Recipient", "location": "Mombasa"}
        self.client.post(route, data)
        self.client.post(route, data)
        self.assertEqual(DeliveryConfirmation.objects.filter(shipment=self.shipment).count(), 1)

    def test_record_failure_and_retry_adds_events(self):
        self.client.force_login(self.staff)
        route = reverse("operations-attempt", args=[self.shipment.pk])
        data = {"reason": "unreachable", "location": "Mombasa", "internal_note": "Private note"}
        self.assertEqual(self.client.post(route, data).status_code, 302)
        self.assertEqual(self.client.post(route, data).status_code, 302)
        self.assertEqual(DeliveryAttempt.objects.filter(shipment=self.shipment).count(), 2)
        self.assertEqual(self.shipment.events.count(), 3)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, Shipment.Status.FAILED)
        self.assertNotContains(self.client.get(reverse("api-track", args=[self.shipment.tracking_number])), "Private note")

    def test_cannot_record_failure_on_delivered(self):
        self.shipment.status = Shipment.Status.DELIVERED
        self.shipment.save()
        self.client.force_login(self.staff)
        self.client.post(reverse("operations-attempt", args=[self.shipment.pk]), {"reason": "other"})
        self.assertFalse(DeliveryAttempt.objects.filter(shipment=self.shipment).exists())

    def test_reports_require_staff(self):
        self.assertEqual(self.client.get(reverse("operations-reports")).status_code, 302)
        self.assertEqual(self.client.get(reverse("operations-export")).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("operations-reports")).status_code, 403)
        self.assertEqual(self.client.get(reverse("operations-export")).status_code, 403)

    def test_reports_totals_and_csv(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("operations-reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Overdue open deliveries")
        csv_response = self.client.get(reverse("operations-export"))
        self.assertEqual(csv_response.status_code, 200)
        rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], self.shipment.tracking_number)

    def test_date_filter_and_invalid_date(self):
        self.client.force_login(self.staff)
        future = timezone.localdate() + timedelta(days=30)
        filtered = self.client.get(reverse("operations-reports"), {"from": future.isoformat()})
        self.assertEqual(filtered.context["total"], 0)
        invalid = self.client.get(reverse("operations-export"), {"from": "wrong"})
        self.assertEqual(invalid.status_code, 400)

    def test_csv_formula_injection_is_escaped(self):
        self.shipment.sender_name = "=HYPERLINK(\"evil\")"
        self.shipment.save()
        self.client.force_login(self.staff)
        response = self.client.get(reverse("operations-export"))
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertTrue(rows[1][2].startswith("'="))
