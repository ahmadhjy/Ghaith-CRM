"""CRM pipeline metrics shown on the accounting dashboard (orders/leads, not financial GL)."""

from __future__ import annotations

from django.db.models import Count

from display.models import Lead
from tasks.models import LeadTask

try:
    from accounting_bridge.models import InvoiceSyncQueue
except ImportError:
    InvoiceSyncQueue = None

ORDER_STATUS_LABELS = {
    'onhold': 'On hold',
    'progress': 'In progress',
    'done': 'Done',
    'cancelled': 'Cancelled',
}

LEAD_STATUS_LABELS = {
    'processing': 'Processing',
    'negotiation': 'Negotiation',
    'done': 'Done',
    'finalized': 'Finalized',
    'onhold': 'On hold',
}


def _orders_in_period(date_from=None, date_to=None):
    qs = LeadTask.objects.select_related('lead', 'assigned_to')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs


def build_crm_pipeline_stats(date_from=None, date_to=None, *, sales_employee_id=None):
    orders_qs = _orders_in_period(date_from, date_to)
    if sales_employee_id:
        orders_qs = orders_qs.filter(assigned_to_id=sales_employee_id)

    order_status_rows = list(
        orders_qs.values('status').annotate(c=Count('id')).order_by('-c')
    )
    chart_order_status_labels = [
        ORDER_STATUS_LABELS.get(row['status'], row['status'] or 'Unknown') for row in order_status_rows
    ]
    chart_order_status_values = [row['c'] for row in order_status_rows]

    lead_ids = orders_qs.values_list('lead_id', flat=True).distinct()
    leads_qs = Lead.objects.filter(pk__in=lead_ids)
    lead_status_rows = list(
        leads_qs.values('status').annotate(c=Count('id')).order_by('-c')
    )
    chart_lead_status_labels = [
        LEAD_STATUS_LABELS.get(row['status'], row['status'] or 'Unknown') for row in lead_status_rows
    ]
    chart_lead_status_values = [row['c'] for row in lead_status_rows]

    synced_invoices = 0
    if InvoiceSyncQueue is not None:
        synced_qs = InvoiceSyncQueue.objects.filter(sales_invoice__isnull=False)
        if date_from:
            synced_qs = synced_qs.filter(created_at__date__gte=date_from)
        if date_to:
            synced_qs = synced_qs.filter(created_at__date__lte=date_to)
        synced_invoices = synced_qs.count()

    return {
        'crm_orders_total': orders_qs.count(),
        'crm_orders_active': orders_qs.exclude(status__in=['done', 'cancelled']).count(),
        'crm_orders_done': orders_qs.filter(status='done').count(),
        'crm_orders_cancelled': orders_qs.filter(status='cancelled').count(),
        'crm_leads_with_orders': leads_qs.count(),
        'crm_synced_invoices': synced_invoices,
        'chart_order_status_labels': chart_order_status_labels,
        'chart_order_status_values': chart_order_status_values,
        'chart_lead_status_labels': chart_lead_status_labels,
        'chart_lead_status_values': chart_lead_status_values,
    }
