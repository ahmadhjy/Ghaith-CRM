"""Shared filter and sort helpers for the Purchases (supplier payments) list."""

from __future__ import annotations

from datetime import datetime

from django.db.models import F


SORT_DUE_ASC = 'due'
SORT_DUE_DESC = '-due'
SORT_TRAVEL_ASC = 'travel'
SORT_TRAVEL_DESC = '-travel'

SORT_CHOICES = (
    (SORT_DUE_ASC, 'Due date (earliest)'),
    (SORT_DUE_DESC, 'Due date (latest)'),
    (SORT_TRAVEL_ASC, 'Travel date (earliest)'),
    (SORT_TRAVEL_DESC, 'Travel date (latest)'),
)


def _parse_date(raw: str):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


def apply_purchases_filters(services, params, *, now):
    due_from = _parse_date(params.get('due_from'))
    due_to = _parse_date(params.get('due_to'))
    travel_from = _parse_date(params.get('travel_from'))
    travel_to = _parse_date(params.get('travel_to'))
    issued_filter = (params.get('issued') or params.get('paid') or '').strip()
    overdue_filter = params.get('overdue') == 'on' or params.get('late') == 'on'
    supplier_filter = (params.get('supplier') or '').strip()
    service_filter = (params.get('service') or '').strip()
    show_cancelled = params.get('show_cancelled') == 'on'

    if not show_cancelled:
        services = services.exclude(leadtask__status='cancelled')

    has_due_range = bool(due_from or due_to)
    if due_from:
        services = services.filter(due_time__date__gte=due_from)
    if due_to:
        services = services.filter(due_time__date__lte=due_to)

    if travel_from:
        services = services.filter(leadtask__travel_date__date__gte=travel_from)
    if travel_to:
        services = services.filter(leadtask__travel_date__date__lte=travel_to)

    if overdue_filter:
        services = services.filter(is_checked=False, due_time__lt=now)
    elif not has_due_range and not issued_filter:
        services = services.filter(is_checked=False)

    if issued_filter in ('issued', 'paid'):
        services = services.filter(is_checked=True)
    elif issued_filter in ('unissued', 'unpaid'):
        services = services.filter(is_checked=False)

    if supplier_filter:
        services = services.filter(supplier__iexact=supplier_filter)
    if service_filter:
        services = services.filter(service_name__iexact=service_filter)

    return services


def order_purchases(services, sort: str):
    sort = (sort or SORT_DUE_ASC).strip()
    if sort == SORT_DUE_DESC:
        return services.order_by(F('due_time').desc(nulls_last=True), 'pk')
    if sort == SORT_TRAVEL_ASC:
        return services.order_by(
            F('leadtask__travel_date').asc(nulls_last=True),
            F('due_time').asc(nulls_last=True),
            'pk',
        )
    if sort == SORT_TRAVEL_DESC:
        return services.order_by(
            F('leadtask__travel_date').desc(nulls_last=True),
            F('due_time').asc(nulls_last=True),
            'pk',
        )
    return services.order_by(F('due_time').asc(nulls_last=True), 'pk')


def purchases_applied_filters(params) -> list[str]:
    filters = []
    due_from = (params.get('due_from') or '').strip()
    due_to = (params.get('due_to') or '').strip()
    travel_from = (params.get('travel_from') or '').strip()
    travel_to = (params.get('travel_to') or '').strip()
    issued = (params.get('issued') or params.get('paid') or '').strip()
    overdue = params.get('overdue') == 'on' or params.get('late') == 'on'
    supplier = (params.get('supplier') or '').strip()
    service = (params.get('service') or '').strip()
    show_cancelled = params.get('show_cancelled') == 'on'
    sort = (params.get('sort') or SORT_DUE_ASC).strip()
    sort_labels = dict(SORT_CHOICES)

    if due_from:
        filters.append(f'Due from: {due_from}')
    if due_to:
        filters.append(f'Due to: {due_to}')
    if travel_from:
        filters.append(f'Travel from: {travel_from}')
    if travel_to:
        filters.append(f'Travel to: {travel_to}')
    if overdue:
        filters.append('Overdue only')
    elif issued in ('issued', 'paid'):
        filters.append('Issued only')
    elif issued in ('unissued', 'unpaid'):
        filters.append('Unissued only')
    elif not due_from and not due_to:
        filters.append('Unissued only (default)')
    if supplier:
        filters.append(f'Supplier: {supplier}')
    if service:
        filters.append(f'Service: {service}')
    if show_cancelled:
        filters.append('Including cancelled orders')
    filters.append(f'Sort: {sort_labels.get(sort, sort)}')
    return filters
