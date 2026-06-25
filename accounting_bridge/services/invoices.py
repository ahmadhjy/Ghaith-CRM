"""Map CRM LeadTask invoices into accounting SalesInvoice drafts and keep them in sync."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from sales.invoice_numbers import next_temp_invoice_no
from sales.models import SalesInvoice, SalesInvoiceLine
from tasks.models import LeadTask

from accounting_bridge.crm_service_map import crm_service_to_line_kwargs
from accounting_bridge.models import AccountingConfig, InvoiceSyncQueue
from accounting_bridge.services.master_data import (
    sync_destination,
    sync_employee_from_user,
    sync_master_data_from_leadtask,
)
from accounting_bridge.utils import CRM_PACKAGE_TYPE_MAP

logger = logging.getLogger(__name__)

# Linked accounting invoices that should track CRM edits.
SYNCABLE_QUEUE_STATUSES = (
    InvoiceSyncQueue.Status.APPROVED,
    InvoiceSyncQueue.Status.PUBLISHED,
    InvoiceSyncQueue.Status.PENDING_REVIEW,
)


def leadtask_order_date(leadtask: LeadTask):
    if getattr(leadtask, 'created_at', None):
        return leadtask.created_at.date()
    first_service_at = (
        leadtask.service_set.order_by('created_at', 'pk')
        .values_list('created_at', flat=True)
        .first()
    )
    if first_service_at:
        return timezone.localtime(first_service_at).date()
    return timezone.localdate()


def _has_linked_accounting_invoice(leadtask: LeadTask) -> bool:
    return InvoiceSyncQueue.objects.filter(
        leadtask=leadtask,
        sales_invoice__isnull=False,
    ).exists()


def leadtask_eligible_for_invoice_sync(leadtask: LeadTask) -> bool:
    """Only CRM orders on/after the go-live cutoff (not unqualified leads)."""
    config = AccountingConfig.load()
    if leadtask_order_date(leadtask) < config.invoice_sync_from:
        return False
    if leadtask.service_set.exists():
        return True
    return _has_linked_accounting_invoice(leadtask)


def _issue_date_for_leadtask(leadtask: LeadTask):
    if leadtask.travel_date:
        return leadtask.travel_date.date()
    return timezone.localdate()


def _update_invoice_header(invoice: SalesInvoice, leadtask: LeadTask) -> None:
    from accounting_bridge.services.master_data import sync_client_from_lead

    lead = leadtask.lead
    client = sync_client_from_lead(lead)
    employee = sync_employee_from_user(leadtask.assigned_to)
    destination = sync_destination(lead.destination)
    package_type = CRM_PACKAGE_TYPE_MAP.get((lead.type_of_service or '').strip().lower(), '')
    issue_date = _issue_date_for_leadtask(leadtask)

    invoice.client = client
    invoice.sales_employee = employee
    invoice.main_destination = destination
    invoice.package_type = package_type
    invoice.issue_date = issue_date
    invoice.due_date = issue_date


def _sync_invoice_lines_from_crm(invoice: SalesInvoice, leadtask: LeadTask) -> None:
    """Mirror CRM service rows onto accounting lines (add / update / remove by crm_service link)."""
    employee = sync_employee_from_user(leadtask.assigned_to)
    destination = sync_destination(leadtask.lead.destination)
    issue_date = _issue_date_for_leadtask(leadtask)

    crm_services = list(leadtask.service_set.all().order_by('pk'))
    crm_ids = {service.pk for service in crm_services}

    linked_lines = {
        line.crm_service_id: line
        for line in invoice.lines.filter(crm_service_id__isnull=False).select_related('crm_service')
    }
    unlinked_lines = list(
        invoice.lines.filter(crm_service__isnull=True).order_by('sort_order', 'pk')
    )

    sort_order = 0
    for service in crm_services:
        sort_order += 1
        line = linked_lines.get(service.pk)
        line_kwargs = crm_service_to_line_kwargs(
            service,
            employee=employee,
            header_destination=destination,
            issue_date=issue_date,
            sort_order=sort_order,
            existing_line=line,
        )
        if line is None and unlinked_lines:
            line = unlinked_lines.pop(0)
            line.crm_service = service
        if line is None:
            SalesInvoiceLine.objects.create(
                invoice=invoice,
                crm_service=service,
                **line_kwargs,
            )
            continue

        for field, value in line_kwargs.items():
            setattr(line, field, value)
        line.crm_service = service
        line.save()

    invoice.lines.filter(crm_service_id__isnull=False).exclude(crm_service_id__in=crm_ids).delete()


@transaction.atomic
def refresh_accounting_invoice_from_crm(queue: InvoiceSyncQueue) -> SalesInvoice | None:
    """Push the latest CRM order onto its linked accounting invoice."""
    invoice = queue.sales_invoice
    if not invoice or invoice.status == SalesInvoice.Status.VOIDED:
        return None

    leadtask = queue.leadtask
    sync_master_data_from_leadtask(leadtask)
    was_posted = invoice.status == SalesInvoice.Status.POSTED

    _update_invoice_header(invoice, leadtask)
    _sync_invoice_lines_from_crm(invoice, leadtask)
    invoice.recalc_usd_amounts()
    invoice.recalc_totals_from_lines()

    if was_posted:
        invoice.publish_changes(None)
    else:
        invoice.save()

    queue.save(update_fields=['last_crm_snapshot_at'])
    return invoice


@transaction.atomic
def build_sales_invoice_from_leadtask(leadtask: LeadTask, actor) -> SalesInvoice:
    from accounting_bridge.services.master_data import sync_client_from_lead

    lead = leadtask.lead
    client = sync_client_from_lead(lead)
    employee = sync_employee_from_user(leadtask.assigned_to)
    destination = sync_destination(lead.destination)
    package_type = CRM_PACKAGE_TYPE_MAP.get((lead.type_of_service or '').strip().lower(), '')
    issue_date = _issue_date_for_leadtask(leadtask)

    invoice = SalesInvoice.objects.create(
        client=client,
        sales_employee=employee,
        main_destination=destination,
        package_type=package_type,
        issue_date=issue_date,
        due_date=issue_date,
        currency='USD',
        exchange_rate_to_usd=Decimal('1'),
        status=SalesInvoice.Status.DRAFT,
        invoice_no=next_temp_invoice_no(),
    )

    sort_order = 0
    for service in leadtask.service_set.all().order_by('pk'):
        sort_order += 1
        line_kwargs = crm_service_to_line_kwargs(
            service,
            employee=employee,
            header_destination=destination,
            issue_date=issue_date,
            sort_order=sort_order,
        )
        SalesInvoiceLine.objects.create(invoice=invoice, crm_service=service, **line_kwargs)

    invoice.recalc_usd_amounts()
    invoice.recalc_totals_from_lines()
    invoice.save()
    return invoice


@transaction.atomic
def sync_crm_leadtask_to_accounting(leadtask: LeadTask, *, force: bool = False) -> InvoiceSyncQueue | None:
    """
    CRM order → accounting integration.

    - Master data (client/supplier/service type/destination) from the order only.
    - New orders after cutoff: auto-create a linked accounting draft invoice.
    - Linked orders: refresh header + service lines on every CRM save.
    - Old orders before cutoff: never create accounting invoices (opening balances cover history).
    - force=True: accountant manual sync from CRM — bypasses cutoff and creates/refreshes the link.
    """
    config = AccountingConfig.load()
    if not config.master_data_sync_enabled and not force:
        return None

    if leadtask.service_set.exists():
        sync_master_data_from_leadtask(leadtask)

    if not force and not leadtask_eligible_for_invoice_sync(leadtask):
        return None

    if force and not leadtask.service_set.exists() and not _has_linked_accounting_invoice(leadtask):
        return None

    queue = InvoiceSyncQueue.objects.filter(leadtask=leadtask).select_related('sales_invoice').first()

    if queue and force and queue.status not in SYNCABLE_QUEUE_STATUSES:
        queue.status = InvoiceSyncQueue.Status.APPROVED
        queue.save(update_fields=['status'])

    if not queue or not queue.sales_invoice_id:
        if not leadtask.service_set.exists():
            return queue
        invoice = build_sales_invoice_from_leadtask(leadtask, None)
        if queue:
            queue.sales_invoice = invoice
            queue.status = InvoiceSyncQueue.Status.APPROVED
            queue.save(update_fields=['sales_invoice', 'status', 'last_crm_snapshot_at'])
        else:
            queue = InvoiceSyncQueue.objects.create(
                leadtask=leadtask,
                sales_invoice=invoice,
                status=InvoiceSyncQueue.Status.APPROVED,
            )
        return queue

    if queue.status in SYNCABLE_QUEUE_STATUSES:
        try:
            refresh_accounting_invoice_from_crm(queue)
        except Exception:
            logger.exception(
                'Failed to refresh accounting invoice for CRM order %s',
                leadtask.pk,
            )
            if force:
                raise
    return queue


def force_sync_crm_leadtask_to_accounting(leadtask: LeadTask) -> InvoiceSyncQueue | None:
    """Manual accountant sync from CRM — includes pre-cutoff orders."""
    return sync_crm_leadtask_to_accounting(leadtask, force=True)


def leadtask_accounting_sync_context(leadtask: LeadTask) -> dict:
    """Template context for CRM invoice ↔ accounting link status."""
    from django.urls import reverse

    queue = InvoiceSyncQueue.objects.filter(leadtask=leadtask).select_related('sales_invoice').first()
    invoice_url = None
    if queue and queue.sales_invoice_id:
        invoice_url = reverse('sales:invoice_edit', kwargs={'invoice_id': queue.sales_invoice_id})
    return {
        'accounting_sync_queue': queue,
        'accounting_invoice_linked': bool(queue and queue.sales_invoice_id),
        'accounting_invoice_url': invoice_url,
        'accounting_invoice_no': queue.sales_invoice.invoice_no if queue and queue.sales_invoice_id else '',
    }


def queue_leadtask_for_review(leadtask: LeadTask) -> InvoiceSyncQueue | None:
    """Backward-compatible alias — now auto-links eligible orders."""
    return sync_crm_leadtask_to_accounting(leadtask)


@transaction.atomic
def approve_queue_item(queue: InvoiceSyncQueue, actor, publish: bool = False) -> SalesInvoice:
    if queue.sales_invoice_id:
        invoice = refresh_accounting_invoice_from_crm(queue) or queue.sales_invoice
    else:
        invoice = build_sales_invoice_from_leadtask(queue.leadtask, actor)
        queue.sales_invoice = invoice

    queue.status = InvoiceSyncQueue.Status.APPROVED
    queue.reviewed_by = actor
    queue.reviewed_at = timezone.now()
    queue.save()

    if publish:
        invoice.publish_changes(actor)
        queue.status = InvoiceSyncQueue.Status.PUBLISHED
        queue.save(update_fields=['status'])

    return invoice
