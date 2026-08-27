"""Tests for the Sophia WhatsApp lead-sync integration (pull + Sold webhook)."""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from display.lead_errors import LeadSyncError
from display.models import CrmUserProfile, Department, Lead
from display.services.sophia_sync import apply_sophia_chat
from tasks.models import LeadTask

WEBHOOK_SECRET = "test-webhook-secret"


@override_settings(SOPHIA_WEBHOOK_SECRET=WEBHOOK_SECRET)
class SophiaSyncTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.turkey = Department.objects.get(code="turkey")
        self.sharm = Department.objects.get(code="sharm")
        self.agent = User.objects.create_user(username="lina", password="pass12345")
        CrmUserProfile.objects.filter(user=self.agent).update(
            department=self.turkey,
            receives_lead_assignments=True,
            sophia_agent_id="sophia-agent-99",
        )

    def _chat(self, **overrides):
        chat = {
            "external_id": "wa_abc123",
            "name": "Sara Haddad",
            "phone": "+96170123456",
            "department": "turkey",
            "status": "progress",
            "status_changed_at": "2026-07-31T14:05:00+03:00",
            "destination": "Antalya",
            "chat_summary": "Asked about a 7-night package.",
            "assigned_agent": None,
        }
        chat.update(overrides)
        return chat

    def test_status_mapping_and_create(self):
        result = apply_sophia_chat(self._chat(status="offer_sent"))
        self.assertTrue(result["created"])
        self.assertTrue(result["applied"])
        lead = result["lead"]
        self.assertEqual(lead.status, "negotiation")
        self.assertFalse(lead.sold)
        self.assertIsNotNone(lead.last_sync_at)

    def test_invalid_status_rejected(self):
        with self.assertRaises(LeadSyncError) as ctx:
            apply_sophia_chat(self._chat(status="banana"))
        self.assertEqual(ctx.exception.code, "INVALID_STATUS")

    def test_missing_offset_date_rejected(self):
        with self.assertRaises(LeadSyncError) as ctx:
            apply_sophia_chat(self._chat(status_changed_at=""))
        self.assertEqual(ctx.exception.code, "INVALID_DATE")

    def test_idempotent_skip_when_not_newer(self):
        first = apply_sophia_chat(self._chat())
        self.assertTrue(first["applied"])
        # Same timestamp again → skipped.
        again = apply_sophia_chat(self._chat(chat_summary="changed"))
        self.assertFalse(again["applied"])
        self.assertEqual(again["skipped_reason"], "not_newer")
        again["lead"].refresh_from_db()
        self.assertEqual(again["lead"].chat_summary, "Asked about a 7-night package.")
        # Newer timestamp → applied.
        newer = apply_sophia_chat(
            self._chat(chat_summary="now newer", status_changed_at="2026-08-01T09:00:00+03:00")
        )
        self.assertTrue(newer["applied"])

    def test_agent_assignment_derives_department(self):
        # Payload department says sharm, but the agent's profile is turkey → profile wins.
        result = apply_sophia_chat(
            self._chat(assigned_agent="sophia-agent-99", department="sharm")
        )
        lead = result["lead"]
        self.assertEqual(lead.assigned_to_id, self.agent.id)
        self.assertEqual(lead.department_id, self.turkey.id)

    def test_last_assigned_agent_wins_after_transfer(self):
        other = User.objects.create_user(username="noura", password="pass12345")
        CrmUserProfile.objects.filter(user=other).update(
            department=self.sharm,
            receives_lead_assignments=True,
            sophia_agent_id="sophia-agent-12",
        )
        result = apply_sophia_chat(
            self._chat(
                assigned_agent=["sophia-agent-12", "sophia-agent-99"],
                department="sharm",
            )
        )
        lead = result["lead"]
        self.assertEqual(lead.assigned_to_id, self.agent.id)
        self.assertEqual(lead.department_id, self.turkey.id)

    def test_sold_webhook_requires_secret(self):
        response = self.client.post(
            "/api/whatsapp/sync/sold/",
            data=json.dumps(self._chat(status="sold")),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_sold_webhook_creates_sold_lead(self):
        response = self.client.post(
            "/api/whatsapp/sync/sold/",
            data=json.dumps(
                self._chat(status="sold", status_changed_at="2026-07-31T21:40:00+03:00")
            ),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET=WEBHOOK_SECRET,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["created"])
        lead = Lead.objects.get(external_id="wa_abc123")
        self.assertTrue(lead.sold)
        self.assertEqual(lead.status, "finalized")
        # Marking a lead sold spins up an order (LeadTask).
        self.assertTrue(LeadTask.objects.filter(lead=lead).exists())

    def test_sold_webhook_is_idempotent(self):
        payload = self._chat(status="sold", status_changed_at="2026-07-31T21:40:00+03:00")
        for _ in range(2):
            response = self.client.post(
                "/api/whatsapp/sync/sold/",
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_WEBHOOK_SECRET=WEBHOOK_SECRET,
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Lead.objects.filter(external_id="wa_abc123").count(), 1)
        self.assertEqual(LeadTask.objects.filter(lead__external_id="wa_abc123").count(), 1)


class LastSevenAmCutoffTests(TestCase):
    def test_afternoon_uses_today_seven(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from display.services.sophia_pull import last_seven_am_beirut

        beirut = ZoneInfo("Asia/Beirut")
        now = datetime(2026, 8, 24, 13, 25, tzinfo=beirut)
        self.assertTrue(last_seven_am_beirut(now).startswith("2026-08-24T07:00:00"))

    def test_exactly_seven_uses_yesterday(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from display.services.sophia_pull import last_seven_am_beirut

        beirut = ZoneInfo("Asia/Beirut")
        now = datetime(2026, 8, 24, 7, 0, tzinfo=beirut)
        self.assertTrue(last_seven_am_beirut(now).startswith("2026-08-23T07:00:00"))


class SophiaClientHeaderTests(TestCase):
    @override_settings(
        SOPHIA_BASE_URL="https://example.test/v1/consumer",
        SOPHIA_API_TOKEN="tok",
    )
    def test_get_sends_sophia_user_agent(self):
        from unittest.mock import MagicMock, patch

        from display.services.sophia_client import SophiaClient

        resp = MagicMock()
        resp.headers = {"Content-Type": "application/json"}
        resp.read.return_value = b'{"departments": []}'
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False

        with patch("display.services.sophia_client.urllib.request.urlopen", return_value=resp) as mock_urlopen:
            SophiaClient().fetch_departments()

        request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request.get_header("User-agent"),
            "SofiiaAI-CRM-Sync/1.0 (+https://ucheed.dev)",
        )
