import csv
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from deliveries.models import Shipment

from .models import CaseUpdate, SupportCase


class SupportDeskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user("support_staff", password="SafeTestPass238!", is_staff=True)
        cls.visitor = User.objects.create_user("support_visitor", password="SafeTestPass238!")
        cls.shipment = Shipment.objects.create(
            sender_name="Someone", recipient_name="Recipient Name", recipient_phone="0712345678",
            origin="Nairobi", destination="Nakuru", weight_kg="2.50",
            expected_delivery=timezone.localdate() - timedelta(days=2),
        )

    def create_case(self, **fields):
        values = dict(shipment=self.shipment, category="delay", subject="Follow up urgently",
                      description="Expected delivery did not arrive", priority="normal", created_by=self.staff)
        values.update(fields)
        return SupportCase.objects.create(**values)

    def test_all_support_views_reject_non_staff(self):
        case = self.create_case()
        urls = [reverse("support-desk-list"), reverse("support-desk-overdue"),
                reverse("support-desk-export"), reverse("support-desk-create", args=[self.shipment.pk]),
                reverse("support-desk-detail", args=[case.pk]),
                reverse("support-desk-update", args=[case.pk])]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
        self.client.force_login(self.visitor)
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, url)
        self.assertEqual(self.client.post(reverse("support-desk-update", args=[case.pk]), {"status": "resolved"}).status_code, 403)
        self.assertEqual(SupportCase.objects.count(), 1)

    def test_create_case_and_initial_audit(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("support-desk-create", args=[self.shipment.pk]), {
            "category": "delay", "priority": "urgent", "subject": "Late package",
            "description": "Customer wants an update", "due_date": "2026-12-24",
        })
        self.assertEqual(response.status_code, 302)
        case = SupportCase.objects.get(subject="Late package")
        self.assertEqual(case.shipment_id, self.shipment.pk)
        self.assertEqual(case.created_by, self.staff)
        self.assertEqual(case.updates.count(), 1)
        self.assertEqual(case.updates.first().recorded_by, self.staff)

    def test_blank_case_is_rejected(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("support-desk-create", args=[self.shipment.pk]), {
            "category": "delay", "priority": "normal", "subject": "  ", "description": "  ",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SupportCase.objects.count(), 0)

    def test_resolve_and_reopen_preserve_activity_history(self):
        case = self.create_case()
        self.client.force_login(self.staff)
        url = reverse("support-desk-update", args=[case.pk])
        response = self.client.post(url, {"status": "resolved", "note": "Customer contacted"})
        self.assertEqual(response.status_code, 302)
        case.refresh_from_db()
        self.assertEqual(case.status, "resolved")
        self.assertIsNotNone(case.resolved_at)
        self.assertEqual(CaseUpdate.objects.filter(case=case).count(), 1)
        self.client.post(url, {"status": "in_progress", "note": "Opened again"})
        case.refresh_from_db()
        self.assertIsNone(case.resolved_at)
        self.assertEqual(CaseUpdate.objects.filter(case=case).count(), 2)
        self.assertEqual(case.updates.first().note, "Opened again")

    def test_noop_and_bad_status_do_not_create_audit(self):
        case = self.create_case()
        self.client.force_login(self.staff)
        url = reverse("support-desk-update", args=[case.pk])
        self.client.post(url, {"status": "open", "note": "   "})
        self.client.post(url, {"status": "made-up-value", "note": "Should not save"})
        self.assertEqual(case.updates.count(), 0)
        case.refresh_from_db()
        self.assertEqual(case.status, "open")

    def test_private_case_notes_absent_from_customer_tracking(self):
        case = self.create_case(description="private company-only support detail")
        CaseUpdate.objects.create(case=case, status="open", note="internal escalation note", recorded_by=self.staff)
        self.client.force_login(self.staff)
        detail = self.client.get(reverse("support-desk-detail", args=[case.pk]))
        self.assertContains(detail, "internal escalation note")
        self.client.logout()
        customer = self.client.get(reverse("track-shipment"), {"code": self.shipment.tracking_number})
        self.assertEqual(customer.status_code, 200)
        self.assertNotIn(b"internal escalation note", customer.content)
        self.assertNotIn(b"private company-only support detail", customer.content)

    def test_overdue_filters_closed_shipments(self):
        Shipment.objects.create(sender_name="S", recipient_name="Completed", recipient_phone="0700000000",
            origin="Nairobi", destination="Nakuru", weight_kg="1.00",
            expected_delivery=timezone.localdate() - timedelta(days=5), status=Shipment.Status.DELIVERED)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("support-desk-overdue"))
        self.assertContains(response, self.shipment.tracking_number)
        self.assertNotContains(response, "Completed")

    def test_search_and_export_sanitize_spreadsheet_cells(self):
        case = self.create_case(subject='=HYPERLINK("bad")', priority="urgent")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("support-desk-list"), {"priority": "urgent"})
        self.assertContains(response, "HYPERLINK")
        response = self.client.get(reverse("support-desk-export"), {"priority": "urgent"})
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1][2].startswith("'="))
        other = self.client.get(reverse("support-desk-export"), {"priority": "low"})
        self.assertEqual(len(list(csv.reader(StringIO(other.content.decode("utf-8-sig"))))), 1)

    def test_no_support_case_for_missing_shipment(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("support-desk-create", args=[999999])).status_code, 404)
