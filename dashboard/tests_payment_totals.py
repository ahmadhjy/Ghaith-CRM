from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from display.models import Lead
from tasks.models import LeadTask, Payment, Service


class FilteredPaymentTotalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "payments_admin", password="pass", is_staff=True
        )
        lead = Lead.objects.create(
            name="Payment client",
            phone="70123456",
            assigned_to=self.user,
        )
        self.order = LeadTask.objects.create(
            lead=lead,
            assigned_to=self.user,
            status="progress",
            travel_date=timezone.now() + timedelta(days=10),
        )
        self.client.force_login(self.user)

    def test_purchases_total_uses_issue_price_and_applied_filters(self):
        due = timezone.now() + timedelta(days=5)
        Service.objects.create(
            leadtask=self.order,
            service_name="Hotel",
            supplier="Babylon",
            net="100",
            issue_price="USD 120",
            due_time=due,
        )
        Service.objects.create(
            leadtask=self.order,
            service_name="Transfer",
            supplier="Other",
            net="50",
            due_time=due,
        )

        response = self.client.get(
            reverse("supplier_payments_list"),
            {"supplier": "Babylon", "issued": "unissued"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filtered_count"], 1)
        self.assertEqual(response.context["filtered_total"], 120)

    def test_client_payment_total_uses_applied_status_filter(self):
        due = timezone.now() + timedelta(days=5)
        Payment.objects.create(
            leadtask=self.order,
            amount=700,
            date=due,
            is_checked=False,
        )
        Payment.objects.create(
            leadtask=self.order,
            amount=300,
            date=due,
            is_checked=True,
        )

        response = self.client.get(
            reverse("client_payments_list"),
            {"issued": "unissued"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filtered_count"], 1)
        self.assertEqual(response.context["filtered_total"], 700)
