"""Sync dashboard Event records with LeadTask services and client payments."""
from django.urls import reverse

from dashboard.models import Event


def _invoice_url(leadtask_id):
    return reverse('edit_lead_tasks', kwargs={'pk': leadtask_id})


def sync_service_event(service):
    """Create or update supplier purchase calendar event for a service."""
    if not service.due_time:
        if hasattr(service, 'calendar_event'):
            try:
                service.calendar_event.delete()
            except Event.DoesNotExist:
                pass
        return

    leadtask = service.leadtask
    lead = leadtask.lead
    when_date = service.due_time.date() if hasattr(service.due_time, 'date') else service.due_time
    net = service.issue_price or service.net or ''
    description = (
        f"Service: {service.service_name}\n"
        f"Supplier: {service.supplier}\n"
        f"Net: ${net}\n"
        f"Client: {lead.name} ({lead.phone})\n"
        f"Invoice: {_invoice_url(leadtask.pk)}"
    )
    title = f"{service.supplier or 'Supplier'} — {lead.name} (${net})"
    defaults = {
        'event_type': 'followup',
        'user': leadtask.assigned_to,
        'title': title,
        'description': description,
        'when': when_date,
        'leadtask': leadtask,
        'done': service.is_checked,
    }
    try:
        event = service.calendar_event
        for key, val in defaults.items():
            setattr(event, key, val)
        event.save()
    except Event.DoesNotExist:
        Event.objects.create(service=service, **defaults)


def sync_payment_event(payment):
    """Create or update client payment calendar event."""
    leadtask = payment.leadtask
    lead = leadtask.lead
    when_date = payment.date.date() if hasattr(payment.date, 'date') else payment.date
    label = 'Refund' if payment.is_refund else 'Client payment'
    description = (
        f"{label}: ${payment.amount}\n"
        f"Client: {lead.name} ({lead.phone})\n"
        f"Invoice: {_invoice_url(leadtask.pk)}"
    )
    title = f"{label}: {lead.name} (${payment.amount})"
    defaults = {
        'event_type': 'task',
        'user': leadtask.assigned_to,
        'title': title,
        'description': description,
        'when': when_date,
        'leadtask': leadtask,
        'payment': payment,
        'done': payment.is_checked,
    }
    try:
        event = payment.calendar_event
        for key, val in defaults.items():
            setattr(event, key, val)
        event.save()
    except Event.DoesNotExist:
        Event.objects.create(**defaults)


def sync_travel_event(leadtask):
    """Create or update calendar event when a client has a travel date on an order."""
    if not leadtask.travel_date or leadtask.status == 'cancelled':
        Event.objects.filter(leadtask=leadtask, event_type='user').delete()
        return

    lead = leadtask.lead
    when_date = (
        leadtask.travel_date.date()
        if hasattr(leadtask.travel_date, 'date')
        else leadtask.travel_date
    )
    title = f"Travelling: {lead.name}"
    description = (
        f"Client: {lead.name}\n"
        f"Destination: {lead.destination or '—'}\n"
        f"Phone: {lead.phone}\n"
        f"Invoice: {_invoice_url(leadtask.pk)}"
    )
    defaults = {
        'user': leadtask.assigned_to,
        'title': title,
        'description': description,
        'when': when_date,
        'done': leadtask.status == 'done',
    }
    event, created = Event.objects.get_or_create(
        leadtask=leadtask,
        event_type='user',
        defaults=defaults,
    )
    if not created:
        for key, val in defaults.items():
            setattr(event, key, val)
        event.save()


def sync_followup_event(lead, user=None):
    """Create or update follow-up reminder when lead is postponed."""
    if lead.status != 'followup' or not lead.follow_up:
        Event.objects.filter(lead=lead, event_type='invoice').delete()
        return

    assignee = user or lead.assigned_to
    defaults = {
        'user': assignee,
        'title': f"Follow-up: {lead.name}",
        'description': (
            f"Follow-up for {lead.name}\n"
            f"Destination: {lead.destination or '—'}\n"
            f"Phone: {lead.phone}"
        ),
        'when': lead.follow_up,
        'event_type': 'invoice',
        'lead': lead,
        'done': False,
    }
    event, created = Event.objects.get_or_create(
        lead=lead,
        event_type='invoice',
        defaults=defaults,
    )
    if not created:
        for key, val in defaults.items():
            setattr(event, key, val)
        event.save()
