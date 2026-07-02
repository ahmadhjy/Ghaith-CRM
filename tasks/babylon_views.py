"""Babylon hotel spreadsheet — staff view and passcode-protected supplier portal."""

from __future__ import annotations

import json
import secrets
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from tasks.babylon_sync import is_babylon_supplier, push_crm_fields_to_entry, sync_service_from_entry
from tasks.constants import get_service_choices
from tasks.models import BabylonHotelEntry

SESSION_KEY = 'babylon_portal_authenticated'
DEFAULT_BABYLON_PASSCODE = 'Babylon-Ghaith-2026'

EDITABLE_STAFF = {
    'entry_date', 'client_name', 'service_type', 'details',
    'price', 'due_date', 'confirmation_number',
}
EDITABLE_PORTAL = {'details', 'price', 'due_date', 'confirmation_number'}


def _portal_passcode() -> str:
    configured = getattr(settings, 'BABYLON_PORTAL_PASSCODE', None)
    if configured is None:
        return DEFAULT_BABYLON_PASSCODE
    cleaned = str(configured).strip()
    return cleaned or DEFAULT_BABYLON_PASSCODE


def _passcode_is_valid(entered: str) -> bool:
    expected = _portal_passcode()
    if not expected:
        return False
    return secrets.compare_digest(entered.strip(), expected)


def _is_portal_authenticated(request) -> bool:
    return bool(request.session.get(SESSION_KEY))


def babylon_portal_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not _is_portal_authenticated(request):
            return redirect('babylon_portal_login')
        return view_func(request, *args, **kwargs)

    wrapper.__name__ = view_func.__name__
    return wrapper


def _entries_queryset(year: int | None = None):
    qs = BabylonHotelEntry.objects.select_related(
        'service',
        'service__leadtask',
        'service__leadtask__lead',
    )
    if year:
        qs = qs.filter(entry_date__year=year)
    return qs.order_by('entry_date', 'created_at')


def _available_years():
    dates = BabylonHotelEntry.objects.dates('entry_date', 'year', order='DESC')
    years = [d.year for d in dates]
    current = datetime.now().year
    if current not in years:
        years.insert(0, current)
    return years or [current]


def _parse_year(raw) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return datetime.now().year


def _serialize_entry(entry: BabylonHotelEntry, *, portal: bool = False) -> dict:
    service = entry.service
    data = {
        'id': entry.id,
        'entry_date': entry.entry_date.isoformat() if entry.entry_date else '',
        'client_name': entry.client_name,
        'service_type': entry.service_type,
        'details': entry.details,
        'price': entry.price,
        'due_date': entry.due_date.isoformat() if entry.due_date else '',
        'confirmation_number': entry.confirmation_number,
    }
    if not portal:
        data['order_id'] = service.leadtask_id
        data['order_url'] = f'/tasks/leads/edit/{service.leadtask_id}/'
    return data


def _sheet_context(entries, year, *, portal_mode: bool, portal_url: str = ''):
    return {
        'entries': entries,
        'year': year,
        'years': _available_years(),
        'portal_mode': portal_mode,
        'editable_fields': EDITABLE_PORTAL if portal_mode else EDITABLE_STAFF,
        'service_choices': get_service_choices(),
        'portal_url': portal_url,
    }


@require_http_methods(['GET', 'POST'])
def babylon_portal_login(request):
    if _is_portal_authenticated(request):
        return redirect('babylon_portal_sheet')

    error = ''
    if request.method == 'POST':
        passcode = (request.POST.get('passcode') or '').strip()
        if passcode and _passcode_is_valid(passcode):
            request.session[SESSION_KEY] = True
            return redirect('babylon_portal_sheet')
        error = 'Invalid passcode. Please try again.'

    return render(request, 'babylon_portal_login.html', {'error': error})


@babylon_portal_required
@require_GET
def babylon_portal_sheet(request):
    year = _parse_year(request.GET.get('year'))
    entries = _entries_queryset(year)
    return render(request, 'babylon_hotels_sheet.html', _sheet_context(entries, year, portal_mode=True))


@babylon_portal_required
@require_POST
def babylon_portal_logout(request):
    request.session.pop(SESSION_KEY, None)
    return redirect('babylon_portal_login')


@login_required(login_url='/login/')
@require_GET
def babylon_hotels_sheet(request):
    year = _parse_year(request.GET.get('year'))
    entries = _entries_queryset(year)
    return render(request, 'babylon_hotels_sheet.html', _sheet_context(
        entries, year, portal_mode=False, portal_url='/babylon/',
    ))


@require_http_methods(['PATCH', 'POST'])
def babylon_entry_update(request, entry_id: int):
    portal = _is_portal_authenticated(request)
    staff = request.user.is_authenticated

    if not portal and not staff:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    entry = get_object_or_404(BabylonHotelEntry, pk=entry_id)
    allowed = EDITABLE_PORTAL if portal else EDITABLE_STAFF

    if request.content_type == 'application/json':
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        payload = request.POST.dict()

    field = (payload.get('field') or '').strip()
    value = payload.get('value')
    if field not in allowed:
        return JsonResponse({'error': f'Field "{field}" cannot be edited here.'}, status=400)

    if field == 'entry_date':
        try:
            entry.entry_date = datetime.strptime(str(value).strip(), '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date'}, status=400)
    elif field == 'due_date':
        raw = (str(value).strip() if value is not None else '')
        if not raw:
            entry.due_date = None
        else:
            try:
                entry.due_date = datetime.strptime(raw, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Invalid date'}, status=400)
    elif field == 'price':
        entry.price = str(value or '').strip()
    elif field == 'client_name':
        entry.client_name = str(value or '').strip()
    elif field == 'service_type':
        entry.service_type = str(value or '').strip()
    elif field == 'details':
        entry.details = str(value or '').strip()
    elif field == 'confirmation_number':
        entry.confirmation_number = str(value or '').strip()

    entry.save()
    sync_service_from_entry(entry)

    if staff and field in {'entry_date', 'client_name', 'service_type'}:
        push_crm_fields_to_entry(entry)

    return JsonResponse({'ok': True, 'entry': _serialize_entry(entry, portal=portal)})
