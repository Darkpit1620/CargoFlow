import csv
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from deliveries.models import Shipment
from .models import WorkEvent, WorkTask


class WorkboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username="workstaff", password="test-password", is_staff=True)
        cls.assignee = User.objects.create_user(username="assignee", password="test-password", is_staff=True)
        cls.nonstaff = User.objects.create_user(username="nonstaff", password="test-password")
        cls.shipment = Shipment.objects.create(
            sender_name="Warehouse", recipient_name="Customer", recipient_phone="0700000000",
            origin="Nairobi", destination="Kisumu", weight_kg="1.25", delivery_fee="300.00",
        )

    def make_task(self, **kwargs):
        data = {"title": "Follow up delivery", "shipment": self.shipment,
                "assigned_to": self.assignee, "created_by": self.staff}
        data.update(kwargs)
        return WorkTask.objects.create(**data)

    def staff_login(self):
        self.client.force_login(self.staff)

    def test_all_pages_require_staff(self):
        task = self.make_task()
        urls = [
            reverse("workboard-list"), reverse("workboard-create"),
            reverse("workboard-export"), reverse("workboard-detail", args=[task.pk]),
            reverse("workboard-edit", args=[task.pk]), reverse("workboard-status", args=[task.pk]),
            reverse("workboard-note", args=[task.pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.client.force_login(self.nonstaff)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.client.post(reverse("workboard-status", args=[task.pk]), {"status": "done"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("workboard-note", args=[task.pk]), {"note": "secret"}).status_code, 403)
        task.refresh_from_db()
        self.assertEqual(task.status, WorkTask.Status.OPEN)

    def test_create_task_with_staff_and_shipment_link(self):
        self.staff_login()
        response = self.client.post(reverse("workboard-create"), {
            "title": "  Confirm unloading  ", "description": "Call warehouse",
            "shipment": str(self.shipment.pk), "assigned_to": str(self.assignee.pk),
            "priority": "urgent", "due_date": timezone.localdate().isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        task = WorkTask.objects.get(title="Confirm unloading")
        self.assertEqual(task.assigned_to, self.assignee)
        self.assertEqual(task.shipment, self.shipment)
        self.assertEqual(task.created_by, self.staff)
        self.assertEqual(task.events.filter(action="created", actor=self.staff).count(), 1)

    def test_form_rejects_nonstaff_or_inactive_assignee(self):
        self.staff_login()
        for bad_user in [self.nonstaff, self.assignee]:
            if bad_user == self.assignee:
                bad_user.is_active = False
                bad_user.save(update_fields=["is_active"])
            response = self.client.post(reverse("workboard-create"), {
                "title": "Don't assign", "assigned_to": str(bad_user.pk),
                "priority": "normal", "shipment": "", "due_date": "",
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Select a valid choice")
        self.assertEqual(WorkTask.objects.count(), 0)

    def test_form_rejects_blank_title(self):
        self.staff_login()
        response = self.client.post(reverse("workboard-create"), {
            "title": "   ", "assigned_to": "", "priority": "normal", "shipment": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WorkTask.objects.count(), 0)

    def test_edit_and_activity_record(self):
        task = self.make_task()
        self.staff_login()
        response = self.client.post(reverse("workboard-edit", args=[task.pk]), {
            "title": "Updated follow-up", "description": "A new reminder", "shipment": "",
            "assigned_to": str(self.staff.pk), "priority": "high", "due_date": "",
        })
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "Updated follow-up")
        self.assertEqual(task.priority, "high")
        self.assertIsNone(task.shipment)
        self.assertEqual(task.events.filter(action="edited").count(), 1)

    def test_status_changes_use_post_and_track_completion(self):
        task = self.make_task()
        self.staff_login()
        url = reverse("workboard-status", args=[task.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {"status": "forged"}).status_code, 400)
        task.refresh_from_db()
        self.assertEqual(task.status, WorkTask.Status.OPEN)
        self.assertEqual(self.client.post(url, {"status": "done"}).status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, WorkTask.Status.DONE)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(task.events.filter(action="status").count(), 1)
        self.assertEqual(self.client.post(url, {"status": "done"}).status_code, 302)
        self.assertEqual(task.events.filter(action="status").count(), 1)
        self.assertEqual(self.client.post(url, {"status": "in_progress"}).status_code, 302)
        task.refresh_from_db()
        self.assertIsNone(task.completed_at)
        self.assertEqual(task.events.filter(action="status").count(), 2)

    def test_task_note_uses_post_and_does_not_accept_blank(self):
        task = self.make_task()
        self.staff_login()
        url = reverse("workboard-note", args=[task.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {"note": "  "}).status_code, 302)
        self.assertFalse(WorkEvent.objects.filter(action="note").exists())
        self.assertEqual(self.client.post(url, {"note": "  Check GPS  "}).status_code, 302)
        event = WorkEvent.objects.get(action="note")
        self.assertEqual(event.note, "Check GPS")
        self.assertEqual(event.actor, self.staff)

    def test_task_search_status_and_my_assignment(self):
        self.make_task(title="Alpha shipment", assigned_to=self.staff)
        self.make_task(title="Beta warehouse", assigned_to=self.assignee, status=WorkTask.Status.DONE)
        self.staff_login()
        response = self.client.get(reverse("workboard-list"), {"q": "Alpha", "owner": "mine"})
        self.assertContains(response, "Alpha shipment")
        self.assertNotContains(response, "Beta warehouse")
        response = self.client.get(reverse("workboard-list"), {"status": "done"})
        self.assertNotContains(response, "Alpha shipment")
        self.assertContains(response, "Beta warehouse")

    def test_overdue_status_excludes_completed_tasks(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        overdue = self.make_task(due_date=yesterday)
        complete = self.make_task(title="Finished", due_date=yesterday, status=WorkTask.Status.DONE)
        self.assertTrue(overdue.overdue)
        self.assertFalse(complete.overdue)
        self.staff_login()
        response = self.client.get(reverse("workboard-list"))
        self.assertEqual(response.context["late_count"], 1)

    def test_csv_export_filters_and_neutralizes_formulas(self):
        self.make_task(title="=HYPERLINK(\"bad\")", assigned_to=self.staff)
        self.make_task(title="Other task", assigned_to=self.assignee)
        self.staff_login()
        response = self.client.get(reverse("workboard-export"), {"owner": "mine"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], "'=HYPERLINK(\"bad\")")
        self.assertEqual(rows[1][5], self.staff.username)

    def test_notes_are_html_escaped(self):
        task = self.make_task()
        WorkEvent.objects.create(task=task, actor=self.staff, action="note", note="<script>alert(1)</script>")
        self.staff_login()
        response = self.client.get(reverse("workboard-detail", args=[task.pk]))
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;", html=False)
