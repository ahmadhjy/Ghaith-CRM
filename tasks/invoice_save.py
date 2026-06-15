"""Unified save helpers for edit leadtask / invoice page."""
from django.shortcuts import get_object_or_404

from .calendar_sync import sync_payment_event, sync_service_event
from .forms import LeadTaskForm, ServiceForm
from .models import LeadTask, Payment, Service


def _save_existing_services(request, leadtask, seen_ids):
    for pk in seen_ids:
        try:
            service = Service.objects.get(pk=pk, leadtask=leadtask)
        except Service.DoesNotExist:
            continue
        form = ServiceForm({
            'service_name': request.POST.get(f'service_{pk}_service_name', ''),
            'supplier': request.POST.get(f'service_{pk}_supplier', ''),
            'details': request.POST.get(f'service_{pk}_details', ''),
            'net': request.POST.get(f'service_{pk}_net', ''),
            'issue_price': request.POST.get(f'service_{pk}_issue_price', ''),
            'selling': request.POST.get(f'service_{pk}_selling', ''),
            'due_time': request.POST.get(f'service_{pk}_due_time') or None,
            'voucher_id': request.POST.get(f'service_{pk}_voucher_id', ''),
            'is_checked': request.POST.get(f'service_{pk}_is_checked') == 'on',
            'send_to_client': request.POST.get(f'service_{pk}_send_to_client') == 'on',
        }, instance=service)
        if form.is_valid():
            saved = form.save()
            sync_service_event(saved)


def _save_new_services(request, leadtask):
    names = request.POST.getlist('service_name[]')
    if not names:
        return
    suppliers = request.POST.getlist('supplier[]')
    details = request.POST.getlist('details[]')
    nets = request.POST.getlist('net[]')
    issue_prices = request.POST.getlist('issue_price[]')
    sellings = request.POST.getlist('selling[]')
    due_times = request.POST.getlist('due_time[]')
    voucher_ids = request.POST.getlist('voucher_id[]')
    send_to_clients = request.POST.getlist('send_to_client[]')
    for i in range(len(names)):
        form = ServiceForm({
            'service_name': names[i] if i < len(names) else '',
            'supplier': suppliers[i] if i < len(suppliers) else '',
            'details': details[i] if i < len(details) else '',
            'net': nets[i] if i < len(nets) else '',
            'issue_price': issue_prices[i] if i < len(issue_prices) else '',
            'selling': sellings[i] if i < len(sellings) else '',
            'due_time': due_times[i] if i < len(due_times) else None,
            'voucher_id': voucher_ids[i] if i < len(voucher_ids) else '',
            'send_to_client': (send_to_clients[i] if i < len(send_to_clients) else '') == 'on',
        })
        if form.is_valid() and (form.cleaned_data.get('service_name') or form.cleaned_data.get('supplier')):
            service = form.save(commit=False)
            service.leadtask = leadtask
            service.save()
            sync_service_event(service)


def save_invoice_from_post(request, leadtask):
    """Save leadtask, lead selling, services, and optional refund payment."""
    old_status = leadtask.status
    form = LeadTaskForm(request.POST, instance=leadtask)
    if not form.is_valid():
        return None, form

    updated = form.save()
    lead = updated.lead
    lead.finalization_notes = form.cleaned_data.get('finalization_notes', '') or ''

    selling = request.POST.get('lead_selling_price', '').strip()
    if selling or 'lead_selling_price' in request.POST:
        lead.selling_price = selling
    lead.save()

    from display.passengers import save_lead_passengers
    save_lead_passengers(lead, request.POST.getlist('passenger_names'))

    if request.POST.get('lead_date_of_birth'):
        from datetime import datetime as dt
        try:
            updated.date_of_birth = dt.strptime(request.POST['lead_date_of_birth'], '%Y-%m-%d').date()
            updated.save(update_fields=['date_of_birth'])
        except ValueError:
            pass
    if request.POST.get('lead_passport_expiry'):
        from datetime import datetime as dt
        try:
            updated.passport_expiry_date = dt.strptime(request.POST['lead_passport_expiry'], '%Y-%m-%d').date()
            updated.save(update_fields=['passport_expiry_date'])
        except ValueError:
            pass

    lead.save()

    for field, attr in (
        ('lead_name', 'name'),
        ('lead_phone', 'phone'),
        ('lead_channel', 'channel'),
        ('lead_destination', 'destination'),
        ('lead_special_request', 'special_request'),
    ):
        val = request.POST.get(field)
        if val is not None:
            setattr(lead, attr, val.strip())
    lead.save()

    prefix = 'service_'
    seen_ids = set()
    for key in request.POST:
        if key.startswith(prefix) and '_' in key[len(prefix):]:
            sid = key[len(prefix):].split('_')[0]
            if sid.isdigit():
                seen_ids.add(int(sid))
    _save_existing_services(request, updated, seen_ids)
    _save_new_services(request, updated)

    if old_status != 'cancelled' and updated.status == 'cancelled':
        refund_amount = request.POST.get('refund_amount', '').strip()
        refund_date = request.POST.get('refund_date', '').strip()
        if refund_amount and refund_date:
            from datetime import datetime as dt
            from django.utils import timezone
            try:
                amount = int(''.join(c for c in refund_amount if c.isdigit()) or '0')
                d = dt.strptime(refund_date, '%Y-%m-%d')
                aware = timezone.make_aware(dt.combine(d.date(), dt.min.time()))
                payment = Payment.objects.create(
                    leadtask=updated,
                    amount=amount,
                    date=aware,
                    is_refund=True,
                    is_checked=False,
                )
                sync_payment_event(payment)
            except (ValueError, TypeError):
                pass

    return updated, form
