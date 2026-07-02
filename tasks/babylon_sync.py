"""Two-way sync between CRM Service rows (BABYLON supplier) and Babylon hotel sheet."""

from __future__ import annotations

from datetime import datetime, time

from django.utils import timezone

from tasks.constants import effective_service_net
from tasks.models import BabylonHotelEntry, Service

BABYLON_SUPPLIER_KEY = 'babylon'


def is_babylon_supplier(name: str | None) -> bool:
    return (name or '').strip().upper() == BABYLON_SUPPLIER_KEY.upper()


def _service_entry_date(service: Service):
    if service.created_at:
        return timezone.localdate(service.created_at)
    return timezone.localdate()


def _service_due_date(service: Service):
    if service.due_time:
        return timezone.localdate(service.due_time)
    return None


def _due_datetime_from_date(due_date):
    if not due_date:
        return None
    naive = datetime.combine(due_date, time.min)
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def sync_entry_from_service(service: Service) -> BabylonHotelEntry | None:
    """Create or update the Babylon sheet row from a CRM service."""
    if not is_babylon_supplier(service.supplier):
        BabylonHotelEntry.objects.filter(service=service).delete()
        return None

    lead = service.leadtask.lead
    entry, _created = BabylonHotelEntry.objects.update_or_create(
        service=service,
        defaults={
            'entry_date': _service_entry_date(service),
            'client_name': lead.name or '',
            'service_type': (service.service_name or '').strip(),
            'details': (service.details or '').strip(),
            'price': effective_service_net(service),
            'due_date': _service_due_date(service),
        },
    )
    return entry


def sync_service_from_entry(entry: BabylonHotelEntry) -> Service | None:
    """Push Babylon sheet edits back to the linked CRM service."""
    service = entry.service
    if not service or not is_babylon_supplier(service.supplier):
        return None

    service.details = (entry.details or '').strip()
    service.net = (entry.price or '').strip()
    service.issue_price = ''
    service.due_time = _due_datetime_from_date(entry.due_date)
    service.service_name = (entry.service_type or '').strip()
    service._babylon_skip_sync = True
    service.save(
        update_fields=['details', 'net', 'issue_price', 'due_time', 'service_name'],
    )
    return service


def push_crm_fields_to_entry(entry: BabylonHotelEntry) -> BabylonHotelEntry:
    """Refresh CRM-owned columns on the sheet (date, client name) from the service."""
    service = entry.service
    lead = service.leadtask.lead
    entry.entry_date = _service_entry_date(service)
    entry.client_name = lead.name or ''
    entry.service_type = (service.service_name or '').strip()
    entry._babylon_skip_sync = True
    entry.save(update_fields=['entry_date', 'client_name', 'service_type', 'updated_at'])
    return entry
