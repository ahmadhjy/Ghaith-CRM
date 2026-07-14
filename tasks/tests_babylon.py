"""Tests for Babylon hotel spreadsheet sync and portal."""

import json
from datetime import date, timedelta

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from display.models import Lead
from tasks.babylon_sheet import OTHER_HOTELS_DESTINATION, babylon_entries_queryset, other_hotels_queryset
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
        self.assertEqual(entry.service_type, 'Hotel')
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

    def test_portal_sheet_shows_other_hotels_link(self):
        self.client.post('/babylon/', {'passcode': 'test-babylon-pass'})
        response = self.client.get('/babylon/sheet/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'View Other Hotels')
        self.assertContains(response, '/babylon/other-hotels/')

    def test_portal_sheet_defaults_to_hotel_service_type(self):
        Service.objects.create(
            leadtask=self.leadtask,
            service_name='Visa',
            supplier='BABYLON',
            details='Visa processing',
            net='50',
        )
        self.client.post('/babylon/', {'passcode': 'test-babylon-pass'})
        response = self.client.get('/babylon/sheet/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alindra Villa')
        self.assertNotContains(response, 'Visa processing')
        self.assertEqual(response.context['service_type'], 'Hotel')

        response_all = self.client.get('/babylon/sheet/', {'service_type': ''})
        self.assertContains(response_all, 'Visa processing')

    def test_portal_other_hotels_page(self):
        self.lead.destination = OTHER_HOTELS_DESTINATION
        self.lead.save(update_fields=['destination'])
        self.leadtask.travel_date = timezone.now() + timedelta(days=14)
        self.leadtask.save(update_fields=['travel_date'])
        Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='YARDS',
            details='Bali resort',
            net='300',
            due_time=timezone.now() + timedelta(days=3),
        )
        self.client.post('/babylon/', {'passcode': 'test-babylon-pass'})
        response = self.client.get('/babylon/other-hotels/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bali resort')
        self.assertContains(response, 'Babylon Hotels')
        self.assertNotContains(response, 'Conf #')
        self.assertNotContains(response, '<th>Issued</th>')

    def test_staff_sheet_lists_entries(self):
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/babylon-hotels/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sara Haddad')
        self.assertContains(response, 'Hotel')
        self.assertContains(response, 'Travel date')
        self.assertContains(response, 'Other Hotels')
        self.assertEqual(response.context['service_type'], 'Hotel')
        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'selling')

    def test_staff_sheet_defaults_to_hotel_service_type(self):
        Service.objects.create(
            leadtask=self.leadtask,
            service_name='Visa',
            supplier='BABYLON',
            details='Visa processing',
            net='50',
        )
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/babylon-hotels/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alindra Villa')
        self.assertNotContains(response, 'Visa processing')
        self.assertEqual(response.context['service_type'], 'Hotel')

        response_all = self.client.get('/tasks/babylon-hotels/', {'service_type': ''})
        self.assertContains(response_all, 'Visa processing')

    def test_babylon_search_filters_client_and_details(self):
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/babylon-hotels/', {'service_type': 'Hotel', 'q': 'Alindra'})
        self.assertContains(response, 'Sara Haddad')
        response = self.client.get('/tasks/babylon-hotels/', {'service_type': 'Hotel', 'q': 'NoMatchXYZ'})
        self.assertNotContains(response, 'Sara Haddad')

    @patch('accounting_bridge.signals._master_sync_enabled', return_value=False)
    def test_babylon_sheet_excludes_issued_services(self, _mock_sync):
        self.service.is_checked = True
        self.service.save(update_fields=['is_checked'])
        self.assertEqual(babylon_entries_queryset({}).count(), 0)
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/babylon-hotels/')
        self.assertNotContains(response, 'Sara Haddad')

    @patch('accounting_bridge.signals._master_sync_enabled', return_value=False)
    def test_marking_issued_removes_row_from_babylon_sheet(self, _mock_sync):
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/babylon-hotels/')
        self.assertContains(response, 'Sara Haddad')
        mark_url = reverse('service_mark_done', args=[self.service.pk])
        response = self.client.post(
            f'{mark_url}?next=/tasks/babylon-hotels/',
            {'is_checked': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        self.service.refresh_from_db()
        self.assertTrue(self.service.is_checked)
        response = self.client.get('/tasks/babylon-hotels/')
        self.assertNotContains(response, 'Sara Haddad')

    def test_service_type_filter_on_staff_sheet(self):
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/babylon-hotels/', {'service_type': 'Visa'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Sara Haddad')

    def test_staff_export_pdf(self):
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/babylon-hotels/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_other_hotels_lists_bali_non_babylon_hotel(self):
        self.lead.destination = OTHER_HOTELS_DESTINATION
        self.lead.save(update_fields=['destination'])
        self.leadtask.travel_date = timezone.now() + timedelta(days=14)
        self.leadtask.save(update_fields=['travel_date'])
        other = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='YARDS',
            details='Bali resort',
            net='300',
            due_time=timezone.now() + timedelta(days=3),
        )
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/other-hotels/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bali resort')
        self.assertContains(response, 'Other Hotels')
        self.assertNotContains(response, 'Conf #')
        self.assertNotContains(response, '<th>Issued</th>')
        self.assertEqual(other_hotels_queryset({}).filter(pk=other.pk).count(), 1)

    def test_other_hotels_excludes_babylon_supplier(self):
        self.lead.destination = OTHER_HOTELS_DESTINATION
        self.lead.save(update_fields=['destination'])
        self.leadtask.travel_date = timezone.now() + timedelta(days=14)
        self.leadtask.save(update_fields=['travel_date'])
        self.service.due_time = timezone.now() + timedelta(days=2)
        self.service.save(update_fields=['due_time'])
        self.assertEqual(other_hotels_queryset({}).count(), 0)

    def test_other_hotels_excludes_issued_services(self):
        self.lead.destination = OTHER_HOTELS_DESTINATION
        self.lead.save(update_fields=['destination'])
        self.leadtask.travel_date = timezone.now() + timedelta(days=14)
        self.leadtask.save(update_fields=['travel_date'])
        issued = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='YARDS',
            details='Issued Bali stay',
            net='400',
            due_time=timezone.now() + timedelta(days=3),
            is_checked=True,
        )
        unissued = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='YARDS',
            details='Open Bali stay',
            net='350',
            due_time=timezone.now() + timedelta(days=4),
            is_checked=False,
        )
        qs = other_hotels_queryset({})
        self.assertEqual(qs.filter(pk=issued.pk).count(), 0)
        self.assertEqual(qs.filter(pk=unissued.pk).count(), 1)
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/other-hotels/')
        self.assertNotContains(response, 'Issued Bali stay')
        self.assertContains(response, 'Open Bali stay')

    def test_portal_other_hotels_shows_takeover_not_supplier_dropdown(self):
        self.lead.destination = OTHER_HOTELS_DESTINATION
        self.lead.save(update_fields=['destination'])
        self.leadtask.travel_date = timezone.now() + timedelta(days=14)
        self.leadtask.save(update_fields=['travel_date'])
        pending = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='',
            details='Pending Bali hotel',
            net='280',
            due_time=timezone.now() + timedelta(days=2),
        )
        self.client.post('/babylon/', {'passcode': 'test-babylon-pass'})
        response = self.client.get('/babylon/other-hotels/')
        self.assertContains(response, 'Takeover')
        self.assertContains(response, 'Pending supplier')
        self.assertNotContains(response, 'cell-input--select')

    def test_portal_takeover_assigns_babylon(self):
        self.lead.destination = OTHER_HOTELS_DESTINATION
        self.lead.save(update_fields=['destination'])
        self.leadtask.travel_date = timezone.now() + timedelta(days=14)
        self.leadtask.save(update_fields=['travel_date'])
        pending = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='',
            details='Takeover Bali hotel',
            net='280',
            due_time=timezone.now() + timedelta(days=2),
        )
        self.client.post('/babylon/', {'passcode': 'test-babylon-pass'})
        response = self.client.post(
            f'/tasks/other-hotels/service/{pending.pk}/takeover/',
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.supplier.upper(), 'BABYLON')
        self.assertEqual(other_hotels_queryset({}).filter(pk=pending.pk).count(), 0)

    def test_staff_other_hotels_has_supplier_dropdown(self):
        self.lead.destination = OTHER_HOTELS_DESTINATION
        self.lead.save(update_fields=['destination'])
        self.leadtask.travel_date = timezone.now() + timedelta(days=14)
        self.leadtask.save(update_fields=['travel_date'])
        Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='',
            details='Staff assign hotel',
            net='280',
            due_time=timezone.now() + timedelta(days=2),
        )
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/tasks/other-hotels/')
        self.assertContains(response, 'cell-input--select')
        self.assertNotContains(response, 'class="babylon-btn babylon-btn--primary babylon-takeover-btn"')

    @override_settings(BABYLON_PORTAL_PASSCODE='')
    def test_default_passcode_when_setting_empty(self):
        response = self.client.post('/babylon/', {'passcode': 'Babylon-Ghaith-2026'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/babylon/sheet', response.url)
