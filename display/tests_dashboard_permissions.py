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
    def test_only_named_users_can_open_both_dashboards(self):
        for username in ("Sara", "Developer", "Accounting"):
            user = User.objects.create_user(username)
            self.client.force_login(user)
            self.assertEqual(self.client.get("/stats_dashboard/").status_code, 200)
            self.assertEqual(
                self.client.get("/tasks/orders/analytics/").status_code, 200
            )

        blocked = User.objects.create_superuser(
            "OtherAdmin", email="admin@example.com", password="pass"
        )
        self.client.force_login(blocked)
        stats_response = self.client.get("/stats_dashboard/")
        orders_response = self.client.get("/tasks/orders/analytics/")
        self.assertEqual(stats_response.status_code, 403)
        self.assertEqual(orders_response.status_code, 403)
        self.assertContains(
            stats_response, "Access restricted", status_code=403
        )
        self.assertContains(
            orders_response, "Access restricted", status_code=403
        )


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
