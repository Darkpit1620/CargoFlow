from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from deliveries.models import Shipment
from .models import StaffAction


class SystemCenterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="system_staff", password="LocalTestPassword901!", is_staff=True,
        )
        cls.regular = User.objects.create_user(
            username="system_guest", password="LocalTestPassword901!", is_staff=False,
        )
        cls.shipment = Shipment.objects.create(
            sender_name="Test Sender", recipient_name="Test Customer",
            recipient_phone="0712345678", origin="Nairobi", destination="Kisumu",
            weight_kg=Decimal("1.50"), delivery_fee=Decimal("100.00"),
            created_by=cls.staff,
        )

    def test_system_dashboard_redirects_anonymous_to_login(self):
        response = self.client.get(reverse("system-dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts/login/", response.url)

    def test_nonstaff_cannot_view_sensitive_system_pages(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(reverse("system-dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("system-activity")).status_code, 403)

    def test_staff_can_view_system_pages_and_existing_shipment_total(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("system-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "System Center")
        self.assertContains(response, "Shipments")
        self.assertEqual(self.client.get(reverse("system-activity")).status_code, 200)

    def test_successful_staff_post_records_no_customer_or_post_content(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("shipment-status", kwargs={"pk": self.shipment.pk}),
            {"status": Shipment.Status.IN_TRANSIT,
             "location": "SECRET_FORM_LOCATION_DO_NOT_LOG",
             "note": "SECRET_FORM_NOTE_DO_NOT_LOG"},
        )
        self.assertEqual(response.status_code, 302)
        event = StaffAction.objects.get(actor=self.staff)
        self.assertEqual(event.http_method, "POST")
        self.assertEqual(event.view_name, "shipment-status")
        self.assertEqual(event.response_status, 302)
        self.assertNotIn("SECRET_FORM", repr(event.__dict__))
        self.assertNotIn(str(self.shipment.pk), event.view_name)

    def test_get_and_nonstaff_post_do_not_create_activity(self):
        self.client.force_login(self.staff)
        self.client.get(reverse("shipment-detail", kwargs={"pk": self.shipment.pk}))
        self.client.get(reverse("system-dashboard"))
        self.assertEqual(StaffAction.objects.count(), 0)
        self.client.force_login(self.regular)
        self.client.post(reverse("shipment-status", kwargs={"pk": self.shipment.pk}), {
            "status": Shipment.Status.IN_TRANSIT,
        })
        self.assertEqual(StaffAction.objects.count(), 0)

    def test_public_health_check_does_not_create_activity(self):
        self.assertEqual(self.client.get(reverse("api-health")).status_code, 200)
        self.assertEqual(StaffAction.objects.count(), 0)
