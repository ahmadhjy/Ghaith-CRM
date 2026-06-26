from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from display.models import Lead
from tasks.models import LeadTask


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
