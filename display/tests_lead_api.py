"""Tests for WhatsApp AI dashboard lead sync API."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from display.models import CrmUserProfile, Department, Lead


@override_settings(EXTERNAL_API_KEY="GhaithDashboard-2026-xK9mP2vL7nQ4wR8sT")
class LeadApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.headers = {
            "HTTP_X_API_KEY": "GhaithDashboard-2026-xK9mP2vL7nQ4wR8sT",
            "content_type": "application/json",
        }
        self.dept = Department.objects.get(code="turkey")
        self.agent = User.objects.create_user(username="agent1", password="pass12345")
        CrmUserProfile.objects.filter(user=self.agent).update(
            department=self.dept,
            receives_lead_assignments=True,
        )

    def test_requires_api_key(self):
        response = self.client.post(
            "/api/leads/",
            data=json.dumps({"name": "Test", "phone": "+96170000001", "department": "turkey"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_create_lead_assigns_department_user(self):
        response = self.client.post(
            "/api/leads/",
            data=json.dumps(
                {
                    "external_id": "dash-001",
                    "name": "Sara Haddad",
                    "phone": "+96170000001",
                    "whatsapp_received_on": "+96171111000",
                    "department": "turkey",
                    "destination": "Antalya",
                    "chat_summary": "Asked about honeymoon package in July.",
                    "status": "onhold",
                    "channel": "Whatsapp",
                }
            ),
            **self.headers,
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["department"], "turkey")
        self.assertEqual(payload["assigned_to"]["username"], "agent1")
        self.assertEqual(payload["chat_summary"], "Asked about honeymoon package in July.")

        lead = Lead.objects.get(external_id="dash-001")
        self.assertEqual(lead.assigned_to_id, self.agent.id)
        self.assertEqual(lead.whatsapp_received_on, "+96171111000")

    def test_upsert_by_external_id(self):
        Lead.objects.create(
            name="Old Name",
            phone="+96170000002",
            external_id="dash-002",
            assigned_to=self.agent,
            department=self.dept,
            channel="Whatsapp",
        )
        response = self.client.post(
            "/api/leads/",
            data=json.dumps(
                {
                    "external_id": "dash-002",
                    "name": "Updated Name",
                    "phone": "+96170000002",
                    "department": "turkey",
                    "status": "processing",
                }
            ),
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Updated Name")
        self.assertEqual(response.json()["status"], "processing")

    def test_list_departments(self):
        response = self.client.get("/api/departments/", **self.headers)
        self.assertEqual(response.status_code, 200)
        codes = {item["code"] for item in response.json()["departments"]}
        self.assertIn("turkey", codes)

    def test_invalid_department_rejected(self):
        response = self.client.post(
            "/api/leads/",
            data=json.dumps(
                {
                    "name": "Test User",
                    "phone": "+96170000003",
                    "department": "unknown_dept",
                }
            ),
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_DEPARTMENT")

    @patch("display.services.lead_sync.assign_user_for_department", return_value=None)
    def test_no_assignable_user_returns_error(self, _mock_assign):
        response = self.client.post(
            "/api/leads/",
            data=json.dumps(
                {
                    "name": "No Agent Lead",
                    "phone": "+96170000004",
                    "department": "turkey",
                }
            ),
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "NO_USER")

    def test_close_deal_sold_calculates_profit(self):
        lead = Lead.objects.create(
            name="Buyer",
            phone="+96170000010",
            assigned_to=self.agent,
            department=self.dept,
            channel="Whatsapp",
            status="negotiation",
        )
        response = self.client.post(
            f"/api/leads/{lead.id}/close-deal/",
            data=json.dumps(
                {
                    "outcome": "sold",
                    "selling_price": "1500",
                    "net": "1200",
                }
            ),
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["sold"])
        self.assertEqual(payload["status"], "finalized")
        self.assertEqual(payload["profit"], "300")

    def test_close_deal_lost_requires_why(self):
        lead = Lead.objects.create(
            name="Lost Lead",
            phone="+96170000011",
            assigned_to=self.agent,
            department=self.dept,
            channel="Whatsapp",
            status="negotiation",
        )
        response = self.client.post(
            f"/api/leads/{lead.id}/close-deal/",
            data=json.dumps({"outcome": "lost"}),
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "MISSING_FIELDS")

    def test_close_deal_postponed_requires_follow_up_date(self):
        lead = Lead.objects.create(
            name="Postpone Lead",
            phone="+96170000012",
            assigned_to=self.agent,
            department=self.dept,
            channel="Whatsapp",
            status="negotiation",
        )
        response = self.client.post(
            f"/api/leads/{lead.id}/close-deal/",
            data=json.dumps(
                {
                    "outcome": "postponed",
                    "follow_up_date": "2026-08-15",
                }
            ),
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "followup")
        self.assertEqual(payload["follow_up_date"], "2026-08-15")

    def test_qualify_advances_to_negotiation(self):
        lead = Lead.objects.create(
            name="Qualify Lead",
            phone="+96170000013",
            assigned_to=self.agent,
            department=self.dept,
            channel="Whatsapp",
            status="processing",
        )
        response = self.client.post(
            f"/api/leads/{lead.id}/qualify/",
            data=json.dumps(
                {
                    "qualification_action": "advance_to_negotiation",
                    "what_happened": "Client confirmed dates and budget.",
                }
            ),
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "negotiation")
