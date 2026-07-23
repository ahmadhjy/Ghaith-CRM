"""Supplier services drill-down from Order Analytics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from django.db.models import Q
from django.utils import timezone
from django.utils.http import urlencode

from tasks.constants import get_service_choices, parse_money
from tasks.datetime_safety import valid_datetime_bounds
from tasks.models import Service
from tasks.purchases_filters import (
    SORT_CHOICES,
    SORT_DUE_ASC,
    order_purchases,
)


def _parse_date(raw):
    try:
        return datetime.strptime((raw or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def supplier_display_name(supplier_key: str) -> str:
    key = (supplier_key or "").strip()
    if not key or key.lower() == "none":
        return "No supplier"
    return key


def apply_supplier_services_filters(services, params, *, now, lock_supplier: str):
    """
    Filter services for one supplier (or blank).

    Unlike Purchases, does not force upcoming-travel / unissued defaults —
    analytics drill-down starts from sold-date + supplier scope.
    """
    sold_from = _parse_date(params.get("sold_from"))
    sold_to = _parse_date(params.get("sold_to"))
    due_from = _parse_date(params.get("due_from"))
    due_to = _parse_date(params.get("due_to"))
    travel_from = _parse_date(params.get("travel_from"))
    travel_to = _parse_date(params.get("travel_to"))
    issued_filter = (params.get("issued") or params.get("paid") or "").strip()
    overdue_filter = params.get("overdue") == "on" or params.get("late") == "on"
    service_filter = (params.get("service") or "").strip()
    show_cancelled = params.get("show_cancelled") == "on"
    paid_filter = (params.get("paid_status") or "").strip()

    supplier_key = (lock_supplier or params.get("supplier") or "").strip()
    if supplier_key.lower() == "none" or supplier_key == "":
        services = services.filter(Q(supplier="") | Q(supplier__isnull=True))
    else:
        services = services.filter(supplier__iexact=supplier_key)

    if sold_from:
        services = services.filter(leadtask__created_at__date__gte=sold_from)
    if sold_to:
        services = services.filter(leadtask__created_at__date__lte=sold_to)

    if not show_cancelled:
        services = services.exclude(leadtask__status="cancelled")

    if due_from:
        services = services.filter(due_time__date__gte=due_from)
    if due_to:
        services = services.filter(due_time__date__lte=due_to)
    if travel_from:
        services = services.filter(leadtask__travel_date__date__gte=travel_from)
    if travel_to:
        services = services.filter(leadtask__travel_date__date__lte=travel_to)

    if overdue_filter:
        services = services.filter(is_checked=False, due_time__lt=now, due_time__isnull=False)
    elif issued_filter in ("issued", "paid"):
        services = services.filter(is_checked=True)
    elif issued_filter in ("unissued", "unpaid"):
        services = services.filter(is_checked=False)

    if paid_filter == "paid":
        services = services.filter(is_checked=True, processed=True)
    elif paid_filter == "outstanding":
        services = services.filter(is_checked=True, processed=False)

    if service_filter:
        services = services.filter(service_name__iexact=service_filter)

    return services


def _service_amount(service) -> float:
    return parse_money(service.issue_price or service.net)


def build_service_type_stats(services, *, now):
    """Per service-type: total, upcoming (not issued), issued."""
    buckets = defaultdict(lambda: {"total": 0, "upcoming": 0, "issued": 0, "amount": 0.0})
    for service in services:
        name = (service.service_name or "").strip() or "No service type"
        bucket = buckets[name]
        bucket["total"] += 1
        bucket["amount"] += _service_amount(service)
        if service.is_checked:
            bucket["issued"] += 1
        else:
            bucket["upcoming"] += 1
    rows = [
        {"name": name, **values}
        for name, values in buckets.items()
    ]
    rows.sort(key=lambda row: (-row["total"], row["name"].casefold()))
    return rows


def build_supplier_payment_stats(services):
    """Paid vs outstanding for issued services of this supplier."""
    paid_count = outstanding_count = 0
    paid_amount = outstanding_amount = 0.0
    for service in services:
        if not service.is_checked:
            continue
        amount = _service_amount(service)
        if service.processed:
            paid_count += 1
            paid_amount += amount
        else:
            outstanding_count += 1
            outstanding_amount += amount
    return {
        "paid_count": paid_count,
        "paid_amount": paid_amount,
        "outstanding_count": outstanding_count,
        "outstanding_amount": outstanding_amount,
    }


def build_supplier_services_context(params, *, user):
    now = timezone.now()
    supplier_key = (params.get("supplier") or "").strip() or "none"
    sold_from = (params.get("sold_from") or "").strip()
    sold_to = (params.get("sold_to") or "").strip()
    due_from = (params.get("due_from") or "").strip()
    due_to = (params.get("due_to") or "").strip()
    travel_from = (params.get("travel_from") or "").strip()
    travel_to = (params.get("travel_to") or "").strip()
    issued_filter = (params.get("issued") or params.get("paid") or "").strip()
    overdue_filter = params.get("overdue") == "on" or params.get("late") == "on"
    service_filter = (params.get("service") or "").strip()
    show_cancelled = params.get("show_cancelled") == "on"
    paid_filter = (params.get("paid_status") or "").strip()
    sort = (params.get("sort") or SORT_DUE_ASC).strip()

    if user.is_staff or user.is_superuser:
        services = Service.objects.all()
    else:
        services = Service.objects.filter(leadtask__assigned_to=user)
    # Skip corrupt due_time values without .only() — this page needs processed,
    # created_at, and full leadtask fields for filters and payment stats.
    lo, hi = valid_datetime_bounds()
    services = services.filter(
        Q(due_time__isnull=True) | Q(due_time__gte=lo, due_time__lte=hi)
    ).select_related("leadtask", "leadtask__lead")

    # Shortcut counts before issued/paid/overdue table filters (same sold+supplier scope).
    base_params = {
        "sold_from": sold_from,
        "sold_to": sold_to,
        "show_cancelled": "on" if show_cancelled else "",
        "supplier": supplier_key,
    }
    base_qs = apply_supplier_services_filters(
        services, base_params, now=now, lock_supplier=supplier_key
    )
    overdue_count = base_qs.filter(
        is_checked=False, due_time__lt=now, due_time__isnull=False
    ).count()
    issued_count = base_qs.filter(is_checked=True).count()
    # Paid/outstanding shortcut counts stay scoped to sold+supplier only
    # (not the table's issued/paid filters), same pattern as Purchases.
    base_payment_stats = build_supplier_payment_stats(list(base_qs))

    filtered = apply_supplier_services_filters(
        services, params, now=now, lock_supplier=supplier_key
    )
    filtered = order_purchases(filtered, sort)
    filtered_list = list(filtered)

    type_stats = build_service_type_stats(filtered_list, now=now)
    payment_stats = build_supplier_payment_stats(filtered_list)
    filtered_total = sum(_service_amount(s) for s in filtered_list)

    reset_params = {
        "supplier": supplier_key,
        "sold_from": sold_from,
        "sold_to": sold_to,
    }
    reset_query = urlencode({k: v for k, v in reset_params.items() if v})

    return {
        "supplier_key": supplier_key,
        "supplier_name": supplier_display_name(supplier_key),
        "sold_from": sold_from,
        "sold_to": sold_to,
        "due_from": due_from,
        "due_to": due_to,
        "travel_from": travel_from,
        "travel_to": travel_to,
        "issued_filter": issued_filter,
        "overdue_filter": overdue_filter,
        "overdue_count": overdue_count,
        "issued_count": issued_count,
        "service_filter": service_filter,
        "service_filter_options": get_service_choices(),
        "show_cancelled": show_cancelled,
        "paid_filter": paid_filter,
        "sort": sort,
        "sort_choices": SORT_CHOICES,
        "services": filtered_list,
        "filtered_count": len(filtered_list),
        "filtered_total": filtered_total,
        "service_type_stats": type_stats,
        "payment_stats": payment_stats,
        "base_payment_stats": base_payment_stats,
        "reset_query": reset_query,
        "now": now,
        "today": now.date(),
    }
