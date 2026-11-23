import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from deliveries.models import Driver
from .forms import VehicleForm
from .models import ServiceRecord, Vehicle


class FleetStage5Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username="fleet_staff", password="safe-password", is_staff=True)
        cls.customer = User.objects.create_user(username="fleet_customer", password="safe-password")
        cls.driver = Driver.objects.create(full_name="Amina Driver", phone="0700000000")
        cls.vehicle = Vehicle.objects.create(
            registration="KDA 123A", make="Toyota", model_name="Hiace", kind=Vehicle.Kind.VAN,
            status=Vehicle.Status.AVAILABLE, capacity_kg=Decimal("1000.00"), mileage_km=45000,
            next_service_date=timezone.localdate() + timedelta(days=8),
        )

    def login(self):
        self.client.force_login(self.staff)

    def test_anonymous_redirected_from_all_fleet_pages(self):
        pages = [reverse("fleet-list"), reverse("fleet-create"), reverse("fleet-due"),
                 reverse("fleet-export"), reverse("fleet-detail", args=[self.vehicle.pk]),
                 reverse("fleet-edit", args=[self.vehicle.pk]),
                 reverse("fleet-service-create", args=[self.vehicle.pk])]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_nonstaff_cannot_read_or_write_fleet(self):
        self.client.force_login(self.customer)
        for url in [reverse("fleet-list"), reverse("fleet-due"), reverse("fleet-export"),
                    reverse("fleet-detail", args=[self.vehicle.pk]),
                    reverse("fleet-create"), reverse("fleet-edit", args=[self.vehicle.pk]),
                    reverse("fleet-service-create", args=[self.vehicle.pk])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("fleet-create"), {}).status_code, 403)
        self.assertEqual(ServiceRecord.objects.count(), 0)

    def test_fleet_list_search_and_status(self):
        self.login()
        self.assertContains(self.client.get(reverse("fleet-list")), "KDA 123A")
        self.assertContains(self.client.get(reverse("fleet-list"), {"q": "toyota"}), "KDA 123A")
        self.assertNotContains(self.client.get(reverse("fleet-list"), {"q": "nonexistent"}), "KDA 123A")
        self.assertNotContains(self.client.get(reverse("fleet-list"), {"status": "inactive"}), "KDA 123A")

    def test_create_vehicle_and_link_active_driver(self):
        self.login()
        response = self.client.post(reverse("fleet-create"), {
            "registration": "kbb 456b", "make": "Isuzu", "model_name": "NPR",
            "kind": "truck", "status": "available", "capacity_kg": "5000.00",
            "mileage_km": "200", "assigned_driver": self.driver.pk,
            "last_service_date": "", "next_service_date": "", "notes": "Ready",
        })
        self.assertEqual(response.status_code, 302)
        vehicle = Vehicle.objects.get(registration="KBB 456B")
        self.assertEqual(vehicle.assigned_driver, self.driver)
        self.assertEqual(response.url, reverse("fleet-detail", args=[vehicle.pk]))

    def test_duplicate_registration_case_insensitive(self):
        self.login()
        response = self.client.post(reverse("fleet-create"), {
            "registration": "kda 123a", "make": "Isuzu", "model_name": "NPR",
            "kind": "truck", "status": "available", "capacity_kg": "5000.00",
            "mileage_km": "200", "assigned_driver": "",
            "last_service_date": "", "next_service_date": "", "notes": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already recorded")
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_driver_cannot_be_assigned_to_two_vehicles(self):
        self.vehicle.assigned_driver = self.driver
        self.vehicle.save(update_fields=["assigned_driver"])
        form = VehicleForm(data={
            "registration": "KZZ 999Z", "make": "Mercedes", "model_name": "Sprinter",
            "kind": "van", "status": "available", "capacity_kg": "800", "mileage_km": "1",
            "assigned_driver": self.driver.pk,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("assigned_driver", form.errors)

    def test_inactive_driver_not_assignable(self):
        self.driver.is_active = False
        self.driver.save(update_fields=["is_active"])
        form = VehicleForm(data={
            "registration": "KZX 321X", "make": "Ford", "model_name": "Transit",
            "kind": "van", "status": "available", "capacity_kg": "800", "mileage_km": "1",
            "assigned_driver": self.driver.pk,
        })
        self.assertFalse(form.is_valid())

    def test_edit_updates_vehicle(self):
        self.login()
        response = self.client.post(reverse("fleet-edit", args=[self.vehicle.pk]), {
            "registration": "KDA 123A", "make": "Toyota", "model_name": "Hiace",
            "kind": "van", "status": "maintenance", "capacity_kg": "1000.00",
            "mileage_km": "45005", "assigned_driver": "", "last_service_date": "",
            "next_service_date": "", "notes": "In workshop",
        })
        self.assertEqual(response.status_code, 302)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, Vehicle.Status.MAINTENANCE)

    def test_service_creates_record_and_updates_vehicle(self):
        self.login()
        yesterday = timezone.localdate() - timedelta(days=1)
        next_due = timezone.localdate() + timedelta(days=90)
        response = self.client.post(reverse("fleet-service-create", args=[self.vehicle.pk]), {
            "service_date": yesterday.isoformat(), "service_type": "routine",
            "description": "Oil and filters changed", "cost": "2500.50",
            "mileage_km": "46000", "next_due_date": next_due.isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ServiceRecord.objects.count(), 1)
        record = ServiceRecord.objects.get()
        self.assertEqual(record.recorded_by, self.staff)
        self.assertEqual(record.vehicle_id, self.vehicle.pk)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.mileage_km, 46000)
        self.assertEqual(self.vehicle.next_service_date, next_due)
        self.assertEqual(self.vehicle.last_service_date, yesterday)
        self.assertContains(self.client.get(reverse("fleet-detail", args=[self.vehicle.pk])), "Oil and filters changed")

    def test_older_service_does_not_overwrite_latest_service(self):
        self.login()
        self.vehicle.last_service_date = timezone.localdate() - timedelta(days=3)
        self.vehicle.next_service_date = timezone.localdate() + timedelta(days=100)
        self.vehicle.save(update_fields=["last_service_date", "next_service_date"])
        old_service = timezone.localdate() - timedelta(days=40)
        response = self.client.post(reverse("fleet-service-create", args=[self.vehicle.pk]), {
            "service_date": old_service.isoformat(), "service_type": "repair",
            "description": "Old repair", "cost": "100", "mileage_km": "1000",
            "next_due_date": (timezone.localdate() - timedelta(days=20)).isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.next_service_date, timezone.localdate() + timedelta(days=100))
        self.assertEqual(self.vehicle.mileage_km, 45000)

    def test_service_cannot_have_future_completion_date(self):
        self.login()
        response = self.client.post(reverse("fleet-service-create", args=[self.vehicle.pk]), {
            "service_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
            "service_type": "routine", "description": "Tomorrow", "cost": "100",
            "mileage_km": "", "next_due_date": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Record completed services only")
        self.assertEqual(ServiceRecord.objects.count(), 0)

    def test_due_board_has_overdue_and_upcoming_but_not_distant(self):
        self.login()
        Vehicle.objects.create(registration="OLD-01", make="Ford", model_name="Transit", capacity_kg="100", next_service_date=timezone.localdate() - timedelta(days=1))
        Vehicle.objects.create(registration="FAR-01", make="Ford", model_name="Courier", capacity_kg="200", next_service_date=timezone.localdate() + timedelta(days=55))
        response = self.client.get(reverse("fleet-due"))
        self.assertContains(response, "KDA 123A")
        self.assertContains(response, "OLD-01")
        self.assertNotContains(response, "FAR-01")
        self.assertContains(response, "Overdue")

    def test_csv_export_is_filtered_and_formula_safe(self):
        self.login()
        Vehicle.objects.create(registration="XYZ-123", make="=2+3", model_name="Test", capacity_kg="100")
        response = self.client.get(reverse("fleet-export"), {"q": "XYZ"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "XYZ-123")
        self.assertEqual(rows[1][1], "'=2+3")

    def test_missing_vehicle_not_found(self):
        self.login()
        self.assertEqual(self.client.get(reverse("fleet-detail", args=[123456])).status_code, 404)
        self.assertEqual(self.client.get(reverse("fleet-service-create", args=[123456])).status_code, 404)

    def test_service_next_due_must_follow_service_date(self):
        self.login()
        today = timezone.localdate()
        response = self.client.post(reverse("fleet-service-create", args=[self.vehicle.pk]), {
            "service_date": today.isoformat(), "service_type": "routine",
            "description": "Attempt", "cost": "0", "mileage_km": "",
            "next_due_date": today.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The next service must be after")
        self.assertEqual(ServiceRecord.objects.count(), 0)
