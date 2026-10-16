"""Pausing Sophia must block every import path without touching existing data."""

import json
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from display.lead_errors import LeadSyncError
from display.models import Department, Lead, SophiaSyncState
from display.services.lead_sync import (
    create_or_update_lead_from_dashboard, update_lead_from_dashboard,
)
from display.services.sophia_control import PAUSED_CODE, sophia_sync_enabled
from display.services.sophia_pull import run_sophia_pull
from display.services.sophia_sync import apply_sophia_chat
from tasks.models import LeadTask


class SophiaPauseDefaultTests(SimpleTestCase):
    def test_preserved_production_settings_without_flag_are_paused(self):
        with override_settings():
            del settings.SOPHIA_SYNC_ENABLED
            self.assertFalse(sophia_sync_enabled())
            result = run_sophia_pull()
            self.assertTrue(result["paused"])

    def test_only_explicit_enable_values_allow_sync(self):
        for value in (False, None, "false", "0", "", "unexpected"):
            with self.subTest(value=value), override_settings(SOPHIA_SYNC_ENABLED=value):
                self.assertFalse(sophia_sync_enabled())
        for value in (True, "true", "1", "on", "YES"):
            with self.subTest(value=value), override_settings(SOPHIA_SYNC_ENABLED=value):
                self.assertTrue(sophia_sync_enabled())


@override_settings(
    SOPHIA_SYNC_ENABLED=False,
    SOPHIA_WEBHOOK_SECRET="pause-test-secret",
    EXTERNAL_API_KEY="pause-test-api-key",
)
class SophiaPausedSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pause_test", password="test")
        self.lead = Lead.objects.create(
            name="Existing client", phone="+96170111111",
            assigned_to=self.user, external_id="existing-chat", status="onhold",
        )
        self.state = SophiaSyncState.load()
        self.state.last_pull_at = timezone.now()
        self.state.last_status = "ok"
        self.state.last_message = "Last successful sync"
        self.state.save()
        self.snapshot = self._snapshot()
        self.chat = {
            "external_id": self.lead.external_id, "phone": self.lead.phone,
            "name": "Must not overwrite", "status": "sold",
            "status_changed_at": timezone.now().isoformat(),
        }

    def _snapshot(self):
        return {
            "leads": list(Lead.objects.order_by("pk").values()),
            "orders": list(LeadTask.objects.order_by("pk").values()),
            "departments": list(Department.objects.order_by("pk").values()),
            "state": list(SophiaSyncState.objects.order_by("pk").values()),
        }

    def assert_unchanged(self):
        self.assertEqual(self._snapshot(), self.snapshot)

    def test_scheduled_and_manual_pulls_never_start_client_or_change_state(self):
        with patch("display.services.sophia_pull.SophiaClient") as client:
            with self.assertNumQueries(0):
                result = run_sophia_pull(
                    since="2000-01-01T00:00:00+03:00",
                    dry_run=True, assigned_agent="reservation-agent",
                )
            self.assertTrue(result["paused"])
            self.assertEqual(result["code"], PAUSED_CODE)
            client.assert_not_called()
        self.assert_unchanged()

    def test_scheduled_command_exits_cleanly_without_syncing(self):
        stdout, stderr = StringIO(), StringIO()
        with patch("display.services.sophia_pull.SophiaClient") as client:
            call_command("sync_sophia_leads", stdout=stdout, stderr=stderr)
            client.assert_not_called()
        self.assertIn("paused", stdout.getvalue())
        self.assertNotIn("sync done", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assert_unchanged()

    def test_service_functions_cannot_bypass_pause(self):
        for invoke in (
            lambda: apply_sophia_chat(self.chat, source="webhook"),
            lambda: apply_sophia_chat(self.chat, source="pull"),
            lambda: create_or_update_lead_from_dashboard(self.chat),
            lambda: update_lead_from_dashboard(self.lead, self.chat),
        ):
            with self.assertNumQueries(0), self.assertRaises(LeadSyncError) as caught:
                invoke()
            self.assertEqual(caught.exception.code, PAUSED_CODE)
        self.assert_unchanged()

    def test_sold_webhook_returns_retryable_pause_without_applying_sold(self):
        for payload in (self.chat, {**self.chat, "external_id": "new-chat", "phone": "+96170999999"}):
            with patch("display.services.sophia_sync.apply_sophia_chat") as apply_chat:
                response = self.client.post(
                    "/api/whatsapp/sync/sold/", data=json.dumps(payload),
                    content_type="application/json",
                    HTTP_X_WEBHOOK_SECRET="pause-test-secret",
                )
                apply_chat.assert_not_called()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["code"], PAUSED_CODE)
            self.assertFalse(response.json()["ok"])
            self.assertEqual(response["Retry-After"], "3600")
        self.assert_unchanged()

    def test_manual_json_import_and_get_run_are_blocked(self):
        for method, url in (
            ("post", "/api/whatsapp/sync/now/"),
            ("get", "/api/whatsapp/sync/now/?run=1"),
        ):
            with patch("display.services.sophia_pull.run_sophia_pull") as pull:
                response = getattr(self.client, method)(
                    url, HTTP_X_WEBHOOK_SECRET="pause-test-secret",
                    HTTP_ACCEPT="application/json",
                )
                pull.assert_not_called()
            self.assertEqual(response.status_code, 503)
            self.assertTrue(response.json()["paused"])
        self.assert_unchanged()

    def test_manual_page_explains_pause_and_disables_button(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/whatsapp/sync/now/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sync paused")
        self.assertContains(response, 'disabled aria-disabled="true"')
        self.assert_unchanged()

    def test_legacy_dashboard_write_routes_are_also_blocked(self):
        for method, url in (
            ("post", "/api/leads/"),
            ("post", "/api/contacts/"),
            ("patch", f"/api/leads/{self.lead.pk}/"),
            ("put", f"/api/leads/{self.lead.pk}/update/"),
            ("post", f"/api/leads/{self.lead.pk}/qualify/"),
            ("post", f"/api/leads/{self.lead.pk}/close-deal/"),
            ("post", f"/api/contacts/{self.lead.pk}/follow-up/"),
            ("post", "/api/crm/notifications/"),
        ):
            with self.subTest(url=url):
                response = getattr(self.client, method)(
                    url, data=json.dumps(self.chat), content_type="application/json",
                    HTTP_X_API_KEY="pause-test-api-key",
                )
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["code"], PAUSED_CODE)
        self.assert_unchanged()

    def test_pausing_does_not_remove_authentication(self):
        self.assertEqual(
            self.client.post("/api/whatsapp/sync/sold/").status_code, 401,
        )
        self.assertEqual(self.client.post("/api/whatsapp/sync/now/").status_code, 401)
        self.assertEqual(self.client.post("/api/leads/").status_code, 401)

    def test_read_only_api_and_manual_crm_edits_still_work(self):
        response = self.client.get(
            f"/api/leads/{self.lead.pk}/", HTTP_X_API_KEY="pause-test-api-key",
        )
        self.assertEqual(response.status_code, 200)
        self.lead.name = "Updated manually"
        self.lead.save()
        order = LeadTask.objects.create(
            lead=self.lead, assigned_to=self.user, status="progress",
        )
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.name, "Updated manually")
        self.assertTrue(LeadTask.objects.filter(pk=order.pk).exists())
