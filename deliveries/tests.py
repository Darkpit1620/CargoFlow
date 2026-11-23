from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from deliveries.models import Driver, Shipment


class CargoFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username="operator", password="SecureTestPass932!", is_staff=True)
        cls.regular = User.objects.create_user(username="guest", password="SecureTestPass932!", is_staff=False)
        cls.shipment = Shipment.objects.create(
            sender_name="Sender One", recipient_name="Private Recipient", recipient_phone="0700000000",
            origin="Nairobi", destination="Mombasa", weight_kg=Decimal("2.50"),
            delivery_fee=Decimal("450.00"), created_by=cls.staff,
        )

    def test_homepage_works(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_health_check_is_public(self):
        response = self.client.get(reverse("api-health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_homepage_and_dashboard_are_different(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_staff_can_access_dashboard(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_non_staff_cannot_access_dashboard(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_tracking_number_and_initial_event_created(self):
        self.assertTrue(self.shipment.tracking_number.startswith("CF-"))
        self.assertEqual(self.shipment.events.count(), 1)

    def test_public_tracking_hides_customer_details(self):
        response = self.client.get(reverse("api-track", kwargs={"tracking_number": self.shipment.tracking_number}))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("recipient_name", response.json())
        self.assertNotContains(response, "Private Recipient")

    def test_anonymous_user_cannot_list_api_shipments(self):
        self.assertIn(self.client.get("/api/shipments/").status_code, [401, 403])

    def test_staff_can_list_api_shipments(self):
        self.client.force_login(self.staff)
        response = self.client.get("/api/shipments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_status_change_records_new_event(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("shipment-status", kwargs={"pk": self.shipment.pk}), {
            "status": Shipment.Status.IN_TRANSIT, "location": "Voi hub", "note": "Arrived at sorting centre",
        })
        self.assertEqual(response.status_code, 302)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, Shipment.Status.IN_TRANSIT)
        self.assertEqual(self.shipment.events.count(), 2)
        self.assertEqual(self.shipment.events.first().location, "Voi hub")

    def test_api_creates_shipment_and_event(self):
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.post("/api/shipments/", {
            "sender_name": "Someone", "recipient_name": "Receiver", "recipient_phone": "0712345678",
            "origin": "Kisumu", "destination": "Eldoret", "weight_kg": "3.00", "delivery_fee": "600.00",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        new_shipment = Shipment.objects.get(pk=response.data["id"])
        self.assertEqual(new_shipment.events.count(), 1)
        self.assertEqual(new_shipment.created_by, self.staff)

    def test_different_status_updates_delivery_time(self):
        self.shipment.status = Shipment.Status.DELIVERED
        self.shipment.save()
        self.assertIsNotNone(self.shipment.delivered_at)
        self.shipment.status = Shipment.Status.IN_TRANSIT
        self.shipment.save()
        self.assertIsNone(self.shipment.delivered_at)
