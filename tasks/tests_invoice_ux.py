from django.contrib.auth.models import User
from django.test import TestCase

from display.models import Lead
from tasks.models import LeadTask, Payment, Service


class InvoiceInlineActionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("invoice_user", password="pass")
        self.client.login(username="invoice_user", password="pass")
        lead = Lead.objects.create(
            name="Inline actions",
            phone="70111111",
            assigned_to=self.user,
        )
        self.order = LeadTask.objects.create(
            lead=lead, assigned_to=self.user, status="progress"
        )
        self.service = Service.objects.create(
            leadtask=self.order,
            service_name="Hotel",
            supplier="BABYLON",
            net="100",
        )

    def test_service_modal_can_save_as_json_without_page_redirect(self):
        response = self.client.post(
            f"/tasks/services/update/{self.service.pk}/",
            {
                "service_name": "Hotel",
                "supplier": "BABYLON",
                "details": "Updated inline",
                "net": "120",
                "issue_price": "",
                "selling": "180",
                "due_time": "",
                "voucher_id": "",
                "is_checked": "",
                "send_to_client": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.service.refresh_from_db()
        self.assertEqual(self.service.details, "Updated inline")

    def test_payment_can_be_added_as_json_without_page_redirect(self):
        response = self.client.post(
            f"/tasks/payment/{self.order.pk}/",
            {"amount": "250", "date": "2026-07-21"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(
            Payment.objects.filter(leadtask=self.order, amount=250).exists()
        )
