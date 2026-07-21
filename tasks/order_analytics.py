"""Admin-only CRM order analytics calculations."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import datetime, time

from django.utils import timezone

from tasks.constants import get_service_choices, get_supplier_choices, parse_money
from tasks.models import LeadTask, Payment, Service


def _date(value, fallback):
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback


def _range(params):
    # Default period: the current calendar month.
    today = timezone.localdate()
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    start = _date(params.get("date_from"), month_start)
    end = _date(params.get("date_to"), month_end)
    if start > end:
        start, end = end, start
    return (
        start,
        end,
        timezone.make_aware(datetime.combine(start, time.min)),
        timezone.make_aware(datetime.combine(end, time.max)),
    )


def _money(service, *, issued=False):
    raw = service.issue_price if issued and service.issue_price else service.net
    return parse_money(raw)


def build_order_analytics_context(params):
    start, end, start_dt, end_dt = _range(params)
    supplier = (params.get("supplier") or "").strip()
    service_type = (params.get("service") or "").strip()

    # LeadTask.created_at is the sold date: the invoice is auto-created
    # the moment a lead is marked sold.
    orders = LeadTask.objects.filter(
        created_at__range=(start_dt, end_dt),
        lead__sold=True,
    ).select_related("lead", "assigned_to").prefetch_related("service_set").distinct()
    if supplier:
        orders = orders.filter(service__supplier__iexact=supplier)
    if service_type:
        orders = orders.filter(service__service_name__iexact=service_type)
    orders = orders.distinct()

    revenue = booking_purchase = actual_purchase = 0.0
    order_rows = []
    supplier_totals = defaultdict(
        lambda: {"booking": 0.0, "actual": 0.0, "count": 0}
    )
    for order in orders:
        services = list(order.service_set.all())
        order_revenue = parse_money(order.lead.selling_price)
        booking = sum(_money(line) for line in services)
        actual = sum(_money(line, issued=True) for line in services)
        revenue += order_revenue
        booking_purchase += booking
        actual_purchase += actual
        order_rows.append({
            "order": order,
            "revenue": order_revenue,
            "booking_purchase": booking,
            "booking_profit": order_revenue - booking,
            "actual_purchase": actual,
            "post_issue_profit": order_revenue - actual,
        })
        for line in services:
            if supplier and line.supplier.casefold() != supplier.casefold():
                continue
            if service_type and line.service_name.casefold() != service_type.casefold():
                continue
            key = line.supplier or "No supplier"
            bucket = supplier_totals[key]
            bucket["booking"] += _money(line)
            bucket["actual"] += _money(line, issued=True)
            bucket["count"] += 1

    payable_services = Service.objects.filter(
        is_checked=True,
        processed=False,
        due_time__range=(start_dt, end_dt),
    ).exclude(leadtask__status="cancelled")
    if supplier:
        payable_services = payable_services.filter(supplier__iexact=supplier)
    if service_type:
        payable_services = payable_services.filter(service_name__iexact=service_type)
    supplier_payable = sum(_money(line, issued=True) for line in payable_services)

    receivable_payments = Payment.objects.filter(
        is_checked=False,
        is_refund=False,
        date__range=(start_dt, end_dt),
    ).exclude(leadtask__status="cancelled")
    if supplier or service_type:
        related_orders = orders.values_list("pk", flat=True)
        receivable_payments = receivable_payments.filter(leadtask_id__in=related_orders)
    client_receivable = sum(float(payment.amount) for payment in receivable_payments)

    supplier_rows = [
        {
            "name": name,
            # Query value for drill-down links; "none" targets blank suppliers.
            "link_value": name if name != "No supplier" else "none",
            **values,
        }
        for name, values in supplier_totals.items()
    ]
    supplier_rows.sort(key=lambda row: row["actual"], reverse=True)
    order_rows.sort(key=lambda row: row["order"].created_at, reverse=True)
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "supplier_filter": supplier,
        "service_filter": service_type,
        "supplier_choices": get_supplier_choices(),
        "service_choices": get_service_choices(),
        "sold_invoice_count": len(order_rows),
        "revenue": revenue,
        "booking_purchase": booking_purchase,
        "booking_profit": revenue - booking_purchase,
        "actual_purchase": actual_purchase,
        "post_issue_profit": revenue - actual_purchase,
        "supplier_payable": supplier_payable,
        "supplier_payable_count": payable_services.count(),
        "client_receivable": client_receivable,
        "client_receivable_count": receivable_payments.count(),
        "supplier_rows": supplier_rows,
        "order_rows": order_rows[:200],
        "chart_data": {
            "financial_labels": ["Total sales", "Cost when booked", "Cost after issuing"],
            "financial_values": [revenue, booking_purchase, actual_purchase],
            "supplier_labels": [row["name"] for row in supplier_rows[:10]],
            "supplier_booking_costs": [
                row["booking"] for row in supplier_rows[:10]
            ],
            "supplier_actual_costs": [
                row["actual"] for row in supplier_rows[:10]
            ],
        },
    }
