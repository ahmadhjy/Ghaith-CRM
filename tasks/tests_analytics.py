from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from display.models import Lead
from tasks.models import LeadTask, Payment, Service
from tasks.order_analytics import build_order_analytics_context


class OrderAnalyticsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "Accounting", password="pass", is_staff=True
        )
        self.sales = User.objects.create_user("sales", password="pass")
        self.lead = Lead.objects.create(
            name="Sold client",
            phone="70123456",
            assigned_to=self.sales,
            sold=False,
            selling_price="1000",
        )
        self.order = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.sales,
            status="progress",
        )
        self.lead.sold = True
        self.lead.save(update_fields=["sold", "last_modified"])
        Service.objects.create(
            leadtask=self.order,
            service_name="Hotel",
            supplier="YARDS",
            net="600",
            issue_price="650",
            selling="1000",
            is_checked=True,
            processed=False,
            due_time=timezone.make_aware(datetime(2026, 7, 20)),
        )
        Payment.objects.create(
            leadtask=self.order,
            amount=700,
            date=timezone.make_aware(datetime(2026, 7, 19)),
            is_checked=False,
        )
        LeadTask.objects.filter(pk=self.order.pk).update(
            created_at=timezone.make_aware(datetime(2026, 7, 18))
        )

    def test_profit_definitions_and_payment_totals(self):
        ctx = build_order_analytics_context({
            "date_from": "2026-07-15",
            "date_to": "2026-07-31",
        })
        self.assertEqual(ctx["sold_invoice_count"], 1)
        self.assertEqual(ctx["revenue"], 1000)
        self.assertEqual(ctx["booking_purchase"], 600)
        self.assertEqual(ctx["booking_profit"], 400)
        self.assertEqual(ctx["actual_purchase"], 650)
        self.assertEqual(ctx["post_issue_profit"], 350)
        self.assertEqual(ctx["supplier_payable"], 650)
        self.assertEqual(ctx["client_receivable"], 700)
        supplier = ctx["supplier_rows"][0]
        self.assertEqual(supplier["count"], 1)
        self.assertEqual(supplier["booking"], 600)
        self.assertEqual(supplier["actual"], 650)
        self.assertNotIn("profit", supplier)

    def test_service_and_supplier_filters_use_admin_values(self):
        ctx = build_order_analytics_context({
            "date_from": "2026-07-15",
            "date_to": "2026-07-31",
            "supplier": "YARDS",
            "service": "Hotel",
        })
        self.assertEqual(ctx["sold_invoice_count"], 1)
        no_match = build_order_analytics_context({
            "date_from": "2026-07-15",
            "date_to": "2026-07-31",
            "supplier": "BABYLON",
        })
        self.assertEqual(no_match["sold_invoice_count"], 0)

    def test_orders_analytics_is_restricted_to_named_users(self):
        self.client.login(username="sales", password="pass")
        self.assertEqual(self.client.get("/tasks/orders/analytics/").status_code, 403)
        self.client.login(username="Accounting", password="pass")
        self.assertEqual(self.client.get("/tasks/orders/analytics/").status_code, 200)

    def test_default_period_is_current_month(self):
        ctx = build_order_analytics_context({})
        today = timezone.localdate()
        self.assertEqual(ctx["date_from"], today.replace(day=1).isoformat())
        self.assertTrue(ctx["date_to"].startswith(today.strftime("%Y-%m")))

    def test_supplier_rows_expose_drilldown_link_value(self):
        Service.objects.create(
            leadtask=self.order,
            service_name="Transfer",
            supplier="",
            net="100",
        )
        ctx = build_order_analytics_context({
            "date_from": "2026-07-15",
            "date_to": "2026-07-31",
        })
        by_name = {row["name"]: row for row in ctx["supplier_rows"]}
        self.assertEqual(by_name["YARDS"]["link_value"], "YARDS")
        self.assertEqual(by_name["No supplier"]["link_value"], "none")

    def test_orders_list_supplier_and_sold_date_drilldown(self):
        other_lead = Lead.objects.create(
            name="Other client",
            phone="70999999",
            assigned_to=self.sales,
        )
        other_order = LeadTask.objects.create(
            lead=other_lead,
            assigned_to=self.sales,
            status="progress",
        )
        Service.objects.create(
            leadtask=other_order,
            service_name="Visa",
            supplier="",
            net="50",
        )
        LeadTask.objects.filter(pk=other_order.pk).update(
            created_at=timezone.make_aware(datetime(2026, 7, 19))
        )

        self.client.login(username="Accounting", password="pass")
        base = "/tasks/leads/current/"

        by_supplier = self.client.get(base, {
            "status": "all",
            "supplier": "YARDS",
            "sold_from": "2026-07-15",
            "sold_to": "2026-07-31",
        })
        ids = [task.pk for task in by_supplier.context["data"]]
        self.assertEqual(ids, [self.order.pk])

        no_supplier = self.client.get(base, {
            "status": "all",
            "supplier": "none",
            "sold_from": "2026-07-15",
            "sold_to": "2026-07-31",
        })
        ids = [task.pk for task in no_supplier.context["data"]]
        self.assertEqual(ids, [other_order.pk])

        out_of_range = self.client.get(base, {
            "status": "all",
            "supplier": "YARDS",
            "sold_from": "2026-08-01",
            "sold_to": "2026-08-31",
        })
        self.assertEqual(len(out_of_range.context["data"]), 0)

    def test_paid_supplier_service_is_removed_from_payable_total(self):
        service = self.order.service_set.get()
        self.client.login(username="Accounting", password="pass")
        response = self.client.post(
            f"/tasks/services/mark_processed/{service.pk}/",
            {"processed": "on"},
        )
        self.assertEqual(response.status_code, 302)
        service.refresh_from_db()
        self.assertTrue(service.processed)
        ctx = build_order_analytics_context({
            "date_from": "2026-07-15",
            "date_to": "2026-07-31",
        })
        self.assertEqual(ctx["supplier_payable"], 0)
