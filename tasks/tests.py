from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from display.models import Lead
from tasks.models import LeadTask, Service
from tasks.purchases_issued import mark_past_travel_services_issued


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


class PastTravelServicesIssuedTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="purch1", password="test12345")
        self.lead = Lead.objects.create(
            name="Travel Lead",
            phone="70111444",
            country_code="+961",
            assigned_to=self.user,
        )

    def _service(self, travel_year, is_checked=False):
        aware = timezone.make_aware(datetime(travel_year, 6, 15, 12, 0))
        leadtask = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status="progress",
            travel_date=aware,
        )
        return Service.objects.create(
            leadtask=leadtask,
            service_name="Hotel",
            supplier="Test Supplier",
            due_time=aware,
            is_checked=is_checked,
        )

    def test_marks_2024_and_2025_services_issued(self):
        s2024 = self._service(2024)
        s2025 = self._service(2025)
        s2026 = self._service(2026)
        mark_past_travel_services_issued()
        s2024.refresh_from_db()
        s2025.refresh_from_db()
        s2026.refresh_from_db()
        self.assertTrue(s2024.is_checked)
        self.assertTrue(s2025.is_checked)
        self.assertFalse(s2026.is_checked)

    def test_skips_already_issued(self):
        s2024 = self._service(2024, is_checked=True)
        mark_past_travel_services_issued()
        s2024.refresh_from_db()
        self.assertTrue(s2024.is_checked)
