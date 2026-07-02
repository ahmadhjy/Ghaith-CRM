"""Tests for Babylon hotel spreadsheet sync and portal."""

import json
from datetime import date

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from display.models import Lead
from tasks.babylon_sync import is_babylon_supplier, sync_entry_from_service
from tasks.models import BabylonHotelEntry, LeadTask, Service


@override_settings(BABYLON_PORTAL_PASSCODE='test-babylon-pass')
class BabylonHotelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sales1', password='pass')
        self.client = Client()
        self.lead = Lead.objects.create(
            name='Sara Haddad',
            phone='+96170111111',
            channel='Whatsapp',
            status='finalized',
            assigned_to=self.user,
        )
        self.leadtask = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status='progress',
        )
        self.service = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='BABYLON',
            details='Alindra Villa — 3 nights pool villa',
            net='220',
            due_time=None,
        )

    def test_is_babylon_supplier(self):
        self.assertTrue(is_babylon_supplier('BABYLON'))
        self.assertTrue(is_babylon_supplier('babylon'))
        self.assertFalse(is_babylon_supplier('YARDS'))

    def test_service_creates_babylon_row(self):
        entry = BabylonHotelEntry.objects.get(service=self.service)
        self.assertEqual(entry.client_name, 'Sara Haddad')
        self.assertEqual(entry.details, 'Alindra Villa — 3 nights pool villa')
        self.assertEqual(entry.price, '220')

    @patch('accounting_bridge.signals._master_sync_enabled', return_value=False)
    def test_non_babylon_supplier_removes_row(self, _mock_sync):
        sync_entry_from_service(self.service)
        self.assertEqual(BabylonHotelEntry.objects.count(), 1)
        self.service.supplier = 'YARDS'
        self.service.save()
        self.assertEqual(BabylonHotelEntry.objects.count(), 0)

    @patch('accounting_bridge.signals._master_sync_enabled', return_value=False)
    def test_portal_login_and_update_price(self, _mock_sync):
        session = self.client.session
        session.save()

        response = self.client.post('/babylon/', {'passcode': 'test-babylon-pass'})
        self.assertEqual(response.status_code, 302)

        entry = BabylonHotelEntry.objects.get(service=self.service)
        response = self.client.post(
            f'/tasks/babylon-hotels/row/{entry.id}/update/',
            data=json.dumps({'field': 'price', 'value': '250'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.service.refresh_from_db()
        self.assertEqual(self.service.net, '250')

    def test_portal_cannot_access_staff_sheet_without_login(self):
        self.client.post('/babylon/', {'passcode': 'test-babylon-pass'})
        response = self.client.get('/tasks/babylon-hotels/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

    def test_staff_sheet_requires_login(self):
        response = self.client.get('/tasks/babylon-hotels/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

    def test_staff_sheet_lists_entries(self):
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/babylon-hotels/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sara Haddad')
        self.assertNotContains(response, 'selling')
