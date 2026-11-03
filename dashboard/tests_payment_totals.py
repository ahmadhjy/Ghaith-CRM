from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import TestCase, override_settings
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

    @override_settings(USE_TZ=True, TIME_ZONE="Asia/Beirut")
    def test_client_payment_pdf_matches_local_dates_at_month_boundary(self):
        Payment.objects.create(
            leadtask=self.order, amount=1080,
            date=datetime(2026, 10, 31, 22, tzinfo=datetime_timezone.utc),
        )
        Payment.objects.create(
            leadtask=self.order, amount=1400,
            date=datetime(2026, 11, 3, 22, tzinfo=datetime_timezone.utc),
        )
        Payment.objects.create(
            leadtask=self.order, amount=1500,
            date=datetime(2026, 11, 30, 22, tzinfo=datetime_timezone.utc),
        )
        for filters, expected_dates in (
            ({"month": "2026-11"}, ["1 Nov 2026", "4 Nov 2026"]),
            ({"date": "2026-11-04"}, ["4 Nov 2026"]),
        ):
            with self.subTest(filters=filters), timezone.override("Asia/Beirut"):
                page = self.client.get(reverse("client_payments_list"), filters)
                self.assertEqual(page.context["filtered_count"], len(expected_dates))
                for date_label in expected_dates:
                    self.assertContains(page, date_label)
                # Verify the exact date cells passed to the PDF renderer.
                with patch("dashboard.views._build_modern_pdf", return_value=HttpResponse()) as render_pdf:
                    response = self.client.get(reverse("client_payments_pdf"), filters)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row[0] for row in render_pdf.call_args.args[2]], expected_dates)

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

    def test_supplier_totals_groups_amounts_by_supplier(self):
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
            supplier="Babylon",
            net="80",
            due_time=due,
        )
        Service.objects.create(
            leadtask=self.order,
            service_name="Visa",
            supplier="Yards",
            net="50",
            due_time=due,
            is_checked=True,
        )

        response = self.client.get(
            reverse("supplier_totals_list"),
            {"issued": "unissued"},
        )

        self.assertEqual(response.status_code, 200)
        rows = {row["supplier"]: row for row in response.context["supplier_rows"]}
        self.assertIn("Babylon", rows)
        self.assertNotIn("Yards", rows)
        self.assertEqual(rows["Babylon"]["count"], 2)
        self.assertEqual(rows["Babylon"]["unissued"], 200)
        self.assertEqual(rows["Babylon"]["issued"], 0)
        self.assertEqual(rows["Babylon"]["total"], 200)
        self.assertEqual(response.context["filtered_total"], 200)
        self.assertContains(response, "Supplier Totals")
        self.assertContains(response, "name=\"due_from\"")
        self.assertContains(response, "name=\"travel_from\"")

    def test_purchase_and_supplier_totals_filter_by_order_destination(self):
        self.order.lead.destination = 'Bali'
        self.order.lead.save(update_fields=['destination'])
        Service.objects.create(
            leadtask=self.order, service_name='Hotel', supplier='Babylon', net='125',
        )
        for url_name in ('supplier_payments_list', 'supplier_totals_list'):
            response = self.client.get(reverse(url_name), {'destination': 'Bali'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['filtered_count'], 1)
            self.assertEqual(response.context['filtered_total'], 125)
            self.assertEqual(response.context['destination_filter'], 'Bali')
            self.assertContains(response, 'name="destination"')
            excluded = self.client.get(reverse(url_name), {'destination': 'Turkey'})
            self.assertEqual(excluded.context['filtered_count'], 0)
            self.assertEqual(excluded.context['filtered_total'], 0)

    def test_supplier_totals_pdf_exports(self):
        due = timezone.now() + timedelta(days=5)
        Service.objects.create(
            leadtask=self.order,
            service_name="Hotel",
            supplier="Babylon",
            net="100",
            due_time=due,
        )
        response = self.client.get(reverse("supplier_totals_pdf"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

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
