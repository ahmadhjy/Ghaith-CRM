from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from auditlog.models import AuditEvent
from display.models import Lead, UserMonthlyTarget
from notifications.models import ChatMessage
from tasks.models import LeadTask


class ManagementDashboardPermissionTests(TestCase):
    def test_order_analytics_stays_restricted_to_named_users(self):
        for username in ("Sara", "Developer", "Accounting"):
            user = User.objects.create_user(username)
            self.client.force_login(user)
            self.assertEqual(
                self.client.get("/tasks/orders/analytics/").status_code, 200
            )

        blocked = User.objects.create_superuser(
            "OtherAdmin", email="admin@example.com", password="pass"
        )
        self.client.force_login(blocked)
        orders_response = self.client.get("/tasks/orders/analytics/")
        self.assertEqual(orders_response.status_code, 403)
        self.assertContains(
            orders_response, "Access restricted", status_code=403
        )

    def test_stats_dashboard_is_open_but_team_view_is_named_users_only(self):
        sara = User.objects.create_user("Sara")
        other = User.objects.create_user("rayan", is_staff=True)
        peer = User.objects.create_user("alaa")
        User.objects.filter(pk__in=[other.pk, peer.pk]).update(is_sales=True)

        self.client.force_login(sara)
        sara_response = self.client.get("/stats_dashboard/")
        self.assertEqual(sara_response.status_code, 200)
        self.assertContains(sara_response, "Team Performance")

        self.client.force_login(other)
        other_response = self.client.get("/stats_dashboard/")
        self.assertEqual(other_response.status_code, 200)
        self.assertContains(other_response, "My Performance")
        self.assertContains(other_response, "Personal view")
        self.assertContains(other_response, "Restricted")


class MergeUsersCommandTests(TestCase):
    def test_transfers_mona_records_to_sara_then_deletes_mona(self):
        sara = User.objects.create_user("Sara")
        mona = User.objects.create_user("Mona")
        lead = Lead.objects.create(
            name="Mona client",
            phone="70111111",
            assigned_to=mona,
        )
        order = LeadTask.objects.create(
            lead=lead,
            assigned_to=mona,
            status="progress",
        )
        sent_message = ChatMessage.objects.create(
            sender=mona,
            recipient=sara,
            body="Historical message",
        )
        audit = AuditEvent.objects.create(
            who=mona,
            action="UPDATE",
            model="Lead",
            object_id=str(lead.pk),
        )
        month = date(2026, 7, 1)
        UserMonthlyTarget.objects.create(
            user=sara, month=month, target_profit=3000
        )
        UserMonthlyTarget.objects.create(
            user=mona, month=month, target_profit=2000
        )

        call_command(
            "merge_users_to",
            "--to",
            "Sara",
            "--from",
            "Mona",
            "--execute",
            "--delete-sources",
            stdout=StringIO(),
        )

        self.assertFalse(User.objects.filter(username__iexact="Mona").exists())
        lead.refresh_from_db()
        order.refresh_from_db()
        sent_message.refresh_from_db()
        audit.refresh_from_db()
        self.assertEqual(lead.assigned_to, sara)
        self.assertEqual(order.assigned_to, sara)
        self.assertEqual(sent_message.sender, sara)
        self.assertEqual(audit.who, sara)
        self.assertEqual(
            UserMonthlyTarget.objects.get(user=sara, month=month).target_profit,
            3000,
        )

    def test_default_merge_deactivates_source_without_deleting(self):
        sara = User.objects.create_user("Sara")
        mona = User.objects.create_user("Mona", is_active=True)
        Lead.objects.create(
            name="Mona lead",
            phone="70222222",
            assigned_to=mona,
        )

        call_command(
            "merge_users_to",
            "--to",
            "Sara",
            "--from",
            "Mona",
            "--execute",
            stdout=StringIO(),
        )

        mona.refresh_from_db()
        self.assertFalse(mona.is_active)
        self.assertEqual(Lead.objects.filter(assigned_to=sara).count(), 1)
