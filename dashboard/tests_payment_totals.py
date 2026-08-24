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

    def test_received_refund_hidden_by_default_and_net_total(self):
        due = timezone.now() + timedelta(days=5)
        # Outstanding client payment (money in).
        Payment.objects.create(leadtask=self.order, amount=1000, date=due, is_checked=False)
        # Outstanding refund we still owe the client (money out).
        Payment.objects.create(leadtask=self.order, amount=200, date=due, is_checked=False, is_refund=True)
        # Refund already paid back to the client — settled, must not show by default.
        Payment.objects.create(leadtask=self.order, amount=150, date=due, is_checked=True, is_refund=True)

        response = self.client.get(reverse("client_payments_list"))

        self.assertEqual(response.status_code, 200)
        # Received refund is excluded; only the two outstanding rows remain.
        self.assertEqual(response.context["filtered_count"], 2)
        self.assertEqual(response.context["payments_in_total"], 1000)
        self.assertEqual(response.context["refunds_out_total"], 200)
        # Net receivable nets the outstanding refund against the incoming payment.
        self.assertEqual(response.context["filtered_total"], 800)
