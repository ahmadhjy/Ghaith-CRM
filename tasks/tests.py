from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from display.models import Lead
from tasks.models import LeadTask, Service


class LeadTasksListFilterTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="orders1", password="test12345")
        self.client.login(username="orders1", password="test12345")
        self.lead = Lead.objects.create(
            name="Test Lead",
            phone="70111222",
            country_code="+961",
            assigned_to=self.user,
        )
        self.active = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status="progress",
        )
        self.done = LeadTask.objects.create(
            lead=Lead.objects.create(
                name="Done Lead",
                phone="70111333",
                country_code="+961",
                assigned_to=self.user,
            ),
            assigned_to=self.user,
            status="done",
        )

    def test_default_excludes_done_orders(self):
        response = self.client.get(reverse("current_lead_tasks"))
        self.assertEqual(response.status_code, 200)
        ids = [row.pk for row in response.context["data"]]
        self.assertIn(self.active.pk, ids)
        self.assertNotIn(self.done.pk, ids)

    def test_all_includes_done_orders(self):
        response = self.client.get(reverse("current_lead_tasks"), {"status": "all"})
        ids = [row.pk for row in response.context["data"]]
        self.assertIn(self.active.pk, ids)
        self.assertIn(self.done.pk, ids)

    def test_done_filter_shows_only_done(self):
        response = self.client.get(reverse("current_lead_tasks"), {"status": "done"})
        ids = [row.pk for row in response.context["data"]]
        self.assertNotIn(self.active.pk, ids)
        self.assertIn(self.done.pk, ids)


class MarkPastTravelServicesIssuedTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="purch", password="test12345")
        self.lead = Lead.objects.create(
            name="Travel Lead",
            phone="70111444",
            country_code="+961",
            assigned_to=self.user,
        )

    def _service(self, travel_year, *, due_time=None, is_checked=False):
        travel_date = timezone.make_aware(datetime(travel_year, 6, 15, 10, 0))
        leadtask = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status="progress",
            travel_date=travel_date,
        )
        return Service.objects.create(
            leadtask=leadtask,
            service_name="Hotel",
            supplier="Supplier A",
            due_time=due_time or timezone.now(),
            is_checked=is_checked,
        )

    def test_migration_marks_2024_and_2025_travel_as_issued(self):
        from importlib import import_module

        from django.apps import apps

        old_2024 = self._service(2024)
        old_2025 = self._service(2025)
        current_2026 = self._service(2026)
        already_issued = self._service(2024, is_checked=True)

        mod = import_module("tasks.migrations.0014_mark_past_travel_services_issued")
        mod.mark_past_travel_services_issued(apps, None)

        old_2024.refresh_from_db()
        old_2025.refresh_from_db()
        current_2026.refresh_from_db()
        already_issued.refresh_from_db()

        self.assertTrue(old_2024.is_checked)
        self.assertTrue(old_2025.is_checked)
        self.assertFalse(current_2026.is_checked)
        self.assertTrue(already_issued.is_checked)

    def test_migration_skips_services_without_due_time(self):
        from importlib import import_module

        from django.apps import apps

        travel_date = timezone.make_aware(datetime(2024, 3, 1, 9, 0))
        leadtask = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status="progress",
            travel_date=travel_date,
        )
        service = Service.objects.create(
            leadtask=leadtask,
            service_name="Visa",
            supplier="Supplier B",
            due_time=None,
            is_checked=False,
        )

        mod = import_module("tasks.migrations.0014_mark_past_travel_services_issued")
        mod.mark_past_travel_services_issued(apps, None)

        service.refresh_from_db()
        self.assertFalse(service.is_checked)
