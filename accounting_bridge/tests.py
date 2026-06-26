from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounting_bridge.models import AccountingConfig, InvoiceSyncQueue
from accounting_bridge.services.invoices import (
    approve_queue_item,
    force_sync_crm_leadtask_to_accounting,
    sync_crm_leadtask_to_accounting,
)
from display.models import Lead
from sales.models import SalesInvoice, SalesInvoiceLine
from tasks.models import LeadTask, Service


class CrmInvoiceForceSyncTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user('force_sync', password='test12345')
        config = AccountingConfig.load()
        config.invoice_sync_from = date.today() + timedelta(days=30)
        config.master_data_sync_enabled = True
        config.save()

    def test_force_sync_creates_invoice_before_cutoff(self):
        lead = Lead.objects.create(
            name='Manual Old',
            phone='70999111',
            country_code='+961',
            assigned_to=self.user,
        )
        leadtask = LeadTask.objects.create(lead=lead, assigned_to=self.user, status='progress')
        Service.objects.create(leadtask=leadtask, service_name='Tour', supplier='Agent', selling='120')
        queue = force_sync_crm_leadtask_to_accounting(leadtask)
        self.assertIsNotNone(queue)
        self.assertIsNotNone(queue.sales_invoice_id)
        self.assertEqual(queue.status, InvoiceSyncQueue.Status.APPROVED)


class CrmInvoiceSyncTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user('sync_agent', password='test12345')
        config = AccountingConfig.load()
        config.invoice_sync_from = date(2000, 1, 1)
        config.master_data_sync_enabled = True
        config.save()

        self.lead = Lead.objects.create(
            name='Sync Client',
            phone='70111222',
            country_code='+961',
            destination='Dubai',
            type_of_service='hotel',
            assigned_to=self.user,
        )
        self.leadtask = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status='progress',
        )
        Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='Hilton',
            details='Room 101',
            net='100',
            selling='150',
        )
        self.queue = sync_crm_leadtask_to_accounting(self.leadtask)
        self.assertEqual(self.queue.status, InvoiceSyncQueue.Status.APPROVED)
        self.assertIsNotNone(self.queue.sales_invoice_id)
        self.invoice = self.queue.sales_invoice

    def test_order_before_cutoff_does_not_create_invoice(self):
        config = AccountingConfig.load()
        config.invoice_sync_from = date.today() + timedelta(days=30)
        config.save()

        lead = Lead.objects.create(
            name='Old Order',
            phone='70999000',
            country_code='+961',
            assigned_to=self.user,
        )
        leadtask = LeadTask.objects.create(lead=lead, assigned_to=self.user, status='progress')
        Service.objects.create(leadtask=leadtask, service_name='Visa', supplier='Agent', selling='50')
        queue = sync_crm_leadtask_to_accounting(leadtask)
        self.assertIsNone(queue)

    def test_order_without_services_does_not_create_invoice(self):
        lead = Lead.objects.create(
            name='Empty',
            phone='70999888',
            country_code='+961',
            assigned_to=self.user,
        )
        leadtask = LeadTask.objects.create(lead=lead, assigned_to=self.user, status='progress')
        queue = sync_crm_leadtask_to_accounting(leadtask)
        self.assertIsNone(queue)

    def test_new_service_line_syncs_to_accounting(self):
        Service.objects.create(
            leadtask=self.leadtask,
            service_name='Ticket',
            supplier='MEA',
            selling='200',
            net='180',
        )
        sync_crm_leadtask_to_accounting(self.leadtask)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.lines.count(), 2)
        self.assertTrue(self.invoice.lines.filter(crm_service__service_name='Ticket').exists())

    def test_service_edit_updates_accounting_line(self):
        service = self.leadtask.service_set.get(service_name='Hotel')
        service.selling = '999'
        service.save()
        line = SalesInvoiceLine.objects.get(invoice=self.invoice, crm_service=service)
        self.assertEqual(line.sell_price, Decimal('999'))

    def test_service_flags_sync_to_accounting_line(self):
        service = self.leadtask.service_set.get(service_name='Hotel')
        service.send_to_client = True
        service.is_checked = True
        service.save()
        line = SalesInvoiceLine.objects.get(invoice=self.invoice, crm_service=service)
        self.assertTrue(line.send_to_client)
        self.assertTrue(line.crm_issued)

    def test_crm_refresh_preserves_accounting_issued_flag(self):
        service = self.leadtask.service_set.get(service_name='Hotel')
        line = SalesInvoiceLine.objects.get(invoice=self.invoice, crm_service=service)
        line.crm_issued = True
        line.save(update_fields=['crm_issued'])
        service.selling = '888'
        service.is_checked = False
        service.save()
        line.refresh_from_db()
        self.assertTrue(line.crm_issued)
        self.assertEqual(line.sell_price, Decimal('888'))

    def test_service_delete_removes_accounting_line(self):
        service = self.leadtask.service_set.get(service_name='Hotel')
        service.delete()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.lines.count(), 0)

    def test_reapprove_refreshes_existing_invoice(self):
        service = self.leadtask.service_set.get(service_name='Hotel')
        service.selling = '175'
        service.save()
        refreshed = approve_queue_item(self.queue, self.user, publish=False)
        self.assertEqual(refreshed.pk, self.invoice.pk)
        line = refreshed.lines.get(crm_service=service)
        self.assertEqual(line.sell_price, Decimal('175'))

    def test_crm_lead_selling_price_sets_invoice_grand_total(self):
        self.lead.selling_price = '500'
        self.lead.save()
        sync_crm_leadtask_to_accounting(self.leadtask)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.grand_total, Decimal('500.00'))
        self.assertEqual(self.invoice.grand_total_usd, Decimal('500.00'))

    def test_crm_lead_selling_price_updates_on_resync(self):
        self.lead.selling_price = '320'
        self.lead.save()
        sync_crm_leadtask_to_accounting(self.leadtask)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.grand_total, Decimal('320.00'))
        self.lead.selling_price = '410'
        self.lead.save()
        sync_crm_leadtask_to_accounting(self.leadtask)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.grand_total, Decimal('410.00'))
