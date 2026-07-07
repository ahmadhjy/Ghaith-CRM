"""Shared query, filter, sort, and export helpers for Babylon and Other Hotels sheets."""

from __future__ import annotations

from datetime import datetime

from django.db.models import F, Q
from django.utils import timezone

from tasks.babylon_sync import is_babylon_supplier
from tasks.constants import effective_service_net, get_service_choices, get_supplier_choices
from tasks.datetime_safety import filter_valid_due_times, valid_datetime_bounds
from tasks.models import BabylonHotelEntry, Service
from tasks.service_defaults import effective_due_date_for_display

OTHER_HOTELS_DESTINATION = 'Bali'
OTHER_HOTELS_SERVICE = 'Hotel'
BABYLON_PORTAL_DEFAULT_SERVICE = 'Hotel'

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


def _parse_year(raw) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return datetime.now().year


def available_entry_years():
    dates = BabylonHotelEntry.objects.dates('entry_date', 'year', order='DESC')
    years = [d.year for d in dates]
    current = datetime.now().year
    if current not in years:
        years.insert(0, current)
    return years or [current]


def _order_babylon_entries(qs, sort: str):
    sort = (sort or SORT_DUE_DESC).strip()
    if sort == SORT_DUE_ASC:
        return qs.order_by(F('due_date').asc(nulls_last=True), '-entry_date', '-created_at')
    if sort == SORT_TRAVEL_ASC:
        return qs.order_by(
            F('service__leadtask__travel_date').asc(nulls_last=True),
            '-entry_date',
            '-created_at',
        )
    if sort == SORT_TRAVEL_DESC:
        return qs.order_by(
            F('service__leadtask__travel_date').desc(nulls_last=True),
            '-entry_date',
            '-created_at',
        )
    if sort == SORT_DUE_DESC:
        return qs.order_by(F('due_date').desc(nulls_last=True), '-entry_date', '-created_at')
    return qs.order_by('-entry_date', '-created_at')


def babylon_portal_query_params(params):
    """Portal sheet defaults to Hotel; explicit empty service_type means All."""
    if hasattr(params, 'copy'):
        q = params.copy()
    else:
        q = dict(params)
    if 'service_type' not in q:
        q['service_type'] = BABYLON_PORTAL_DEFAULT_SERVICE
    return q


def babylon_entries_queryset(params):
    year = _parse_year(params.get('year'))
    service_type = (params.get('service_type') or '').strip()
    sort = (params.get('sort') or SORT_DUE_DESC).strip()

    qs = BabylonHotelEntry.objects.select_related(
        'service',
        'service__leadtask',
        'service__leadtask__lead',
    ).filter(
        entry_date__year=year,
        service__is_checked=False,
    )

    if service_type:
        qs = qs.filter(
            Q(service_type__iexact=service_type)
            | Q(service_type='', service__service_name__iexact=service_type)
        )

    return _order_babylon_entries(qs, sort)


def other_hotels_queryset(params, *, now=None):
    now = now or timezone.now()
    service_type = (params.get('service_type') or '').strip()
    sort = (params.get('sort') or SORT_TRAVEL_ASC).strip()
    no_supplier = (params.get('no_supplier') or '').strip().lower() in {'1', 'true', 'yes', 'on'}

    qs = Service.objects.filter(
        is_checked=False,
        service_name__iexact=OTHER_HOTELS_SERVICE,
        leadtask__lead__destination__iexact=OTHER_HOTELS_DESTINATION,
        leadtask__travel_date__isnull=False,
        leadtask__travel_date__gte=now,
    ).exclude(
        supplier__iexact='BABYLON'
    ).exclude(
        leadtask__status='cancelled'
    ).select_related('leadtask', 'leadtask__lead')

    if no_supplier:
        qs = qs.filter(Q(supplier__isnull=True) | Q(supplier=''))

    lo, hi = valid_datetime_bounds()
    qs = qs.filter(Q(due_time__isnull=True) | Q(due_time__gte=lo, due_time__lte=hi))

    if service_type:
        qs = qs.filter(service_name__iexact=service_type)

    return _order_services_by_sort(qs, sort)


def _order_services_by_sort(qs, sort: str):
    sort = (sort or SORT_TRAVEL_ASC).strip()
    if sort == SORT_DUE_ASC:
        return qs.order_by('due_time')
    if sort == SORT_DUE_DESC:
        return qs.order_by('-due_time')
    if sort == SORT_TRAVEL_DESC:
        return qs.order_by(F('leadtask__travel_date').desc(nulls_last=True), 'due_time')
    return qs.order_by(F('leadtask__travel_date').asc(nulls_last=True), 'due_time')


def _fmt_date(value) -> str:
    if not value:
        return '—'
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)


def _fmt_travel_date(value) -> str:
    if not value:
        return '—'
    if hasattr(value, 'date'):
        return value.date().strftime('%Y-%m-%d')
    return _fmt_date(value)


def row_from_entry(entry: BabylonHotelEntry, *, portal: bool = False) -> dict:
    service = entry.service
    leadtask = service.leadtask
    return {
        'row_kind': 'babylon',
        'entry_id': entry.id,
        'service_id': service.id,
        'entry_date': entry.entry_date,
        'client_name': entry.client_name,
        'service_type': entry.service_type or service.service_name or '',
        'details': entry.details,
        'price': entry.price,
        'due_date': entry.due_date,
        'travel_date': leadtask.travel_date if leadtask else None,
        'confirmation_number': entry.confirmation_number,
        'is_checked': service.is_checked,
        'order_id': service.leadtask_id,
        'is_incomplete': portal and (not (entry.price or '').strip() or not entry.due_date),
    }


def row_from_service(service: Service) -> dict:
    leadtask = service.leadtask
    lead = leadtask.lead
    due_date = effective_due_date_for_display(service)
    entry_date = service.created_at.date() if service.created_at else None
    supplier = (service.supplier or '').strip()
    return {
        'row_kind': 'service',
        'entry_id': None,
        'service_id': service.id,
        'entry_date': entry_date,
        'client_name': lead.name if lead else '',
        'service_type': service.service_name or '',
        'details': service.details,
        'price': effective_service_net(service),
        'due_date': due_date,
        'travel_date': leadtask.travel_date if leadtask else None,
        'confirmation_number': '',
        'supplier': supplier,
        'supplier_label': supplier or 'Pending supplier',
        'needs_supplier': not supplier,
        'is_checked': service.is_checked,
        'order_id': service.leadtask_id,
        'is_incomplete': not supplier,
    }


def babylon_applied_filters(params) -> list[str]:
    filters = []
    year = _parse_year(params.get('year'))
    filters.append(f'Year: {year}')
    filters.append('Unissued only')
    service_type = (params.get('service_type') or '').strip()
    if service_type:
        filters.append(f'Service: {service_type}')
    sort = (params.get('sort') or SORT_DUE_DESC).strip()
    sort_labels = dict(SORT_CHOICES)
    filters.append(f'Sort: {sort_labels.get(sort, sort)}')
    return filters


def other_hotels_applied_filters(params) -> list[str]:
    filters = [
        f'Destination: {OTHER_HOTELS_DESTINATION}',
        'Upcoming travel only',
        f'Service: {OTHER_HOTELS_SERVICE}',
        'Supplier: not BABYLON',
        'Unissued only',
    ]
    if (params.get('no_supplier') or '').strip().lower() in {'1', 'true', 'yes', 'on'}:
        filters.append('Pending supplier only')
    service_type = (params.get('service_type') or '').strip()
    if service_type:
        filters.append(f'Service filter: {service_type}')
    sort = (params.get('sort') or SORT_TRAVEL_ASC).strip()
    sort_labels = dict(SORT_CHOICES)
    filters.append(f'Sort: {sort_labels.get(sort, sort)}')
    return filters


def babylon_export_table(rows, *, portal: bool, show_conf: bool = True, show_issued: bool = True, show_supplier: bool = False) -> tuple[list[str], list[list]]:
    headers = ['Date', 'Client Name', 'Service', 'Details', 'Price (Net)', 'Due', 'Travel date']
    if show_supplier:
        headers.append('Supplier')
    if show_issued:
        headers.append('Issued')
    if show_conf:
        headers.append('Conf #')
    if not portal:
        headers.append('Order')

    table_rows = []
    for row in rows:
        line = [
            _fmt_date(row.get('entry_date')),
            row.get('client_name') or '—',
            row.get('service_type') or '—',
            row.get('details') or '—',
            row.get('price') or '—',
            _fmt_date(row.get('due_date')),
            _fmt_travel_date(row.get('travel_date')),
        ]
        if show_supplier:
            line.append(row.get('supplier_label') or row.get('supplier') or '—')
        if show_issued:
            line.append('Yes' if row.get('is_checked') else 'No')
        if show_conf:
            line.append(row.get('confirmation_number') or '—')
        if not portal:
            line.append(str(row.get('order_id') or '—'))
        table_rows.append(line)
    return headers, table_rows


def sheet_filter_context(params, *, default_sort: str) -> dict:
    return {
        'year': _parse_year(params.get('year')),
        'years': available_entry_years(),
        'service_type': (params.get('service_type') or '').strip(),
        'sort': (params.get('sort') or default_sort).strip(),
        'no_supplier': (params.get('no_supplier') or '').strip().lower() in {'1', 'true', 'yes', 'on'},
        'service_choices': get_service_choices(),
        'supplier_choices': get_supplier_choices(),
        'sort_choices': SORT_CHOICES,
    }
