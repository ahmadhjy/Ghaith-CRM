"""Babylon hotel spreadsheet — staff view, supplier portal, Other Hotels, exports."""

from __future__ import annotations

import json
import secrets
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts_core.export_utils import build_xlsx_response
from tasks.babylon_sheet import (
    SORT_DUE_DESC,
    SORT_TRAVEL_ASC,
    babylon_applied_filters,
    babylon_entries_queryset,
    babylon_export_table,
    other_hotels_applied_filters,
    other_hotels_queryset,
    row_from_entry,
    row_from_service,
    sheet_filter_context,
)
from tasks.babylon_sync import push_crm_fields_to_entry, sync_service_from_entry
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


def _serialize_entry(entry: BabylonHotelEntry, *, portal: bool = False) -> dict:
    row = row_from_entry(entry, portal=portal)
    data = {
        'id': entry.id,
        'entry_date': row['entry_date'].isoformat() if row['entry_date'] else '',
        'client_name': row['client_name'],
        'service_type': row['service_type'],
        'details': row['details'],
        'price': row['price'],
        'due_date': row['due_date'].isoformat() if row['due_date'] else '',
        'travel_date': row['travel_date'].date().isoformat() if row['travel_date'] else '',
        'confirmation_number': row['confirmation_number'],
        'is_checked': row['is_checked'],
    }
    if not portal:
        data['order_id'] = row['order_id']
        data['order_url'] = f'/tasks/leads/edit/{row["order_id"]}/'
    return data


def _sheet_context(
    *,
    rows,
    sheet_kind: str,
    title: str,
    subtitle: str,
    portal_mode: bool,
    editable_fields,
    filter_ctx: dict,
    portal_url: str = '',
    export_pdf_url: str = '',
    export_xlsx_url: str = '',
    other_hotels_url: str = '',
    babylon_url: str = '',
    show_conf: bool = True,
    empty_message: str = '',
):
    return {
        'rows': rows,
        'sheet_kind': sheet_kind,
        'title': title,
        'subtitle': subtitle,
        'portal_mode': portal_mode,
        'editable_fields': editable_fields,
        'show_conf': show_conf,
        'show_order': not portal_mode,
        'portal_url': portal_url,
        'export_pdf_url': export_pdf_url,
        'export_xlsx_url': export_xlsx_url,
        'other_hotels_url': other_hotels_url,
        'babylon_url': babylon_url,
        'empty_message': empty_message,
        **filter_ctx,
    }


def _babylon_filter_ctx(request):
    return sheet_filter_context(request.GET, default_sort=SORT_DUE_DESC)


def _other_hotels_filter_ctx(request):
    return sheet_filter_context(request.GET, default_sort=SORT_TRAVEL_ASC)


def _build_babylon_pdf_response(request, *, portal: bool):
    from tasks.pdf_template import build_report_pdf

    entries = babylon_entries_queryset(request.GET)
    rows = [row_from_entry(entry, portal=portal) for entry in entries]
    headers, table_rows = babylon_export_table(rows, portal=portal, show_conf=True)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="babylon-hotels-report.pdf"'
    build_report_pdf(
        response=response,
        doc_title='Babylon Hotels',
        subtitle=datetime.now().strftime('%Y-%m-%d %H:%M'),
        applied_filters=babylon_applied_filters(request.GET),
        headers=headers,
        rows=table_rows,
    )
    return response


def _build_babylon_xlsx_response(request, *, portal: bool):
    entries = babylon_entries_queryset(request.GET)
    rows = [row_from_entry(entry, portal=portal) for entry in entries]
    headers, table_rows = babylon_export_table(rows, portal=portal, show_conf=True)
    return build_xlsx_response('babylon-hotels-report', headers, table_rows)


def _build_other_hotels_pdf_response(request):
    from django.utils import timezone

    from tasks.pdf_template import build_report_pdf

    services = other_hotels_queryset(request.GET, now=timezone.now())
    rows = [row_from_service(service) for service in services]
    headers, table_rows = babylon_export_table(rows, portal=False, show_conf=False)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="other-hotels-bali-report.pdf"'
    build_report_pdf(
        response=response,
        doc_title='Other Hotels — Bali',
        subtitle=datetime.now().strftime('%Y-%m-%d %H:%M'),
        applied_filters=other_hotels_applied_filters(request.GET),
        headers=headers,
        rows=table_rows,
    )
    return response


def _build_other_hotels_xlsx_response(request):
    from django.utils import timezone

    services = other_hotels_queryset(request.GET, now=timezone.now())
    rows = [row_from_service(service) for service in services]
    headers, table_rows = babylon_export_table(rows, portal=False, show_conf=False)
    return build_xlsx_response('other-hotels-bali-report', headers, table_rows)


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
    entries = babylon_entries_queryset(request.GET)
    rows = [row_from_entry(entry, portal=True) for entry in entries]
    q = request.GET.urlencode()
    return render(request, 'babylon_hotels_sheet.html', _sheet_context(
        rows=rows,
        sheet_kind='babylon',
        title='Babylon Hotels',
        subtitle='',
        portal_mode=True,
        editable_fields=EDITABLE_PORTAL,
        filter_ctx=_babylon_filter_ctx(request),
        export_pdf_url=f'/babylon/export/pdf/?{q}' if q else '/babylon/export/pdf/',
        export_xlsx_url=f'/babylon/export/xlsx/?{q}' if q else '/babylon/export/xlsx/',
        empty_message=f'No Babylon hotel rows for {request.GET.get("year") or datetime.now().year} yet.',
    ))


@babylon_portal_required
@require_GET
def babylon_portal_export_pdf(request):
    return _build_babylon_pdf_response(request, portal=True)


@babylon_portal_required
@require_GET
def babylon_portal_export_xlsx(request):
    return _build_babylon_xlsx_response(request, portal=True)


@babylon_portal_required
@require_POST
def babylon_portal_logout(request):
    request.session.pop(SESSION_KEY, None)
    return redirect('babylon_portal_login')


@login_required(login_url='/login/')
@require_GET
def babylon_hotels_sheet(request):
    entries = babylon_entries_queryset(request.GET)
    rows = [row_from_entry(entry, portal=False) for entry in entries]
    q = request.GET.urlencode()
    return render(request, 'babylon_hotels_sheet.html', _sheet_context(
        rows=rows,
        sheet_kind='babylon',
        title='Babylon Hotels',
        subtitle='Rows are created automatically when an order service uses BABYLON as supplier.',
        portal_mode=False,
        editable_fields=EDITABLE_STAFF,
        filter_ctx=_babylon_filter_ctx(request),
        portal_url='/babylon/',
        export_pdf_url=f'/tasks/babylon-hotels/pdf/?{q}' if q else '/tasks/babylon-hotels/pdf/',
        export_xlsx_url=f'/tasks/babylon-hotels/xlsx/?{q}' if q else '/tasks/babylon-hotels/xlsx/',
        other_hotels_url='/tasks/other-hotels/',
        empty_message=f'No Babylon hotel rows for {request.GET.get("year") or datetime.now().year} yet. Add a service with supplier BABYLON on an order to create one.',
    ))


@login_required(login_url='/login/')
@require_GET
def babylon_hotels_export_pdf(request):
    return _build_babylon_pdf_response(request, portal=False)


@login_required(login_url='/login/')
@require_GET
def babylon_hotels_export_xlsx(request):
    return _build_babylon_xlsx_response(request, portal=False)


@login_required(login_url='/login/')
@require_GET
def other_hotels_sheet(request):
    from django.utils import timezone

    services = other_hotels_queryset(request.GET, now=timezone.now())
    rows = [row_from_service(service) for service in services]
    q = request.GET.urlencode()
    return render(request, 'babylon_hotels_sheet.html', _sheet_context(
        rows=rows,
        sheet_kind='other_hotels',
        title='Other Hotels — Bali',
        subtitle='Hotel services for upcoming Bali travel from suppliers other than BABYLON.',
        portal_mode=False,
        editable_fields=set(),
        filter_ctx=_other_hotels_filter_ctx(request),
        show_conf=False,
        export_pdf_url=f'/tasks/other-hotels/pdf/?{q}' if q else '/tasks/other-hotels/pdf/',
        export_xlsx_url=f'/tasks/other-hotels/xlsx/?{q}' if q else '/tasks/other-hotels/xlsx/',
        babylon_url='/tasks/babylon-hotels/',
        empty_message='No upcoming Bali hotel services from other suppliers.',
    ))


@login_required(login_url='/login/')
@require_GET
def other_hotels_export_pdf(request):
    return _build_other_hotels_pdf_response(request)


@login_required(login_url='/login/')
@require_GET
def other_hotels_export_xlsx(request):
    return _build_other_hotels_xlsx_response(request)


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
