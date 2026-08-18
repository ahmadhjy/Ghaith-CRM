from datetime import date, datetime

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from display.models import Lead, MonthlyTarget, UserMonthlyTarget
from display.stats_service import build_stats_dashboard_context
from tasks.models import LeadTask, Service


class StatsDashboardTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = User.objects.create_user("Sara", is_staff=True)
        self.sales_a = User.objects.create_user("sales_a")
        self.sales_b = User.objects.create_user("sales_b")
        User.objects.filter(pk__in=[self.sales_a.pk, self.sales_b.pk]).update(is_sales=True)
        self.lead_a = self._sold_order(self.sales_a, "A", "1000", "600")
        self.lead_b = self._sold_order(self.sales_b, "B", "500", "300")
        MonthlyTarget.objects.create(month=date(2026, 7, 1), target_profit=1000)
        UserMonthlyTarget.objects.create(
            user=self.sales_a, month=date(2026, 7, 1), target_profit=500
        )

    def _sold_order(self, user, name, selling, net):
        lead = Lead.objects.create(
            name=name,
            phone=f"70{name}00000",
            assigned_to=user,
            selling_price=selling,
            sold=False,
        )
        order = LeadTask.objects.create(lead=lead, assigned_to=user, status="progress")
        Service.objects.create(leadtask=order, service_name="Hotel", net=net)
        lead.sold = True
        lead.save(update_fields=["sold", "last_modified"])
        # created_at is the sold date (invoice created when lead marked sold)
        stamp = timezone.make_aware(datetime(2026, 7, 18, 12))
        LeadTask.objects.filter(pk=order.pk).update(created_at=stamp)
        return lead

    def _request(self, user):
        request = self.factory.get(
            "/stats_dashboard/",
            {"date_from": "2026-07-15", "date_to": "2026-07-31"},
        )
        request.user = user
        return request

    def test_admin_sees_team_invoice_profit_and_target(self):
        ctx = build_stats_dashboard_context(self._request(self.admin))
        self.assertTrue(ctx["can_view_team"])
        self.assertEqual(ctx["sold_orders"], 2)
        self.assertEqual(ctx["achieved_profit"], 600)
        self.assertEqual(ctx["monthly_target"], 1000)
        self.assertEqual(len(ctx["employee_stats"]), 2)

    def test_non_staff_sees_only_own_stats_and_target(self):
        ctx = build_stats_dashboard_context(self._request(self.sales_a))
        self.assertFalse(ctx["can_view_team"])
        self.assertEqual(ctx["sold_orders"], 1)
        self.assertEqual(ctx["achieved_profit"], 400)
        self.assertEqual(ctx["monthly_target"], 500)
        self.assertEqual(len(ctx["employee_stats"]), 2)
        self_row = next(stat for stat in ctx["employee_stats"] if stat["is_self"])
        other_row = next(stat for stat in ctx["employee_stats"] if not stat["is_self"])
        self.assertFalse(self_row["blurred"])
        self.assertEqual(self_row["profit"], 400)
        self.assertTrue(other_row["blurred"])
        self.assertIsNone(other_row["profit"])

    def test_staff_without_management_access_cannot_see_team_totals(self):
        staff = User.objects.create_user("staff_only", is_staff=True)
        User.objects.filter(pk=staff.pk).update(is_sales=True)
        ctx = build_stats_dashboard_context(self._request(staff))
        self.assertFalse(ctx["can_view_team"])
        self.assertEqual(ctx["sold_orders"], 0)
        self.assertTrue(any(stat["blurred"] for stat in ctx["employee_stats"]))
