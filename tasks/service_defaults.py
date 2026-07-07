"""Default field values when saving CRM services."""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from tasks.babylon_sync import is_babylon_supplier


def default_service_due_time(leadtask, supplier: str | None, due_time):
    """
    Non-Babylon services without a due time use the order travel date at midnight local.
    Babylon services keep due_time unset until set explicitly or via the Babylon sheet.
    """
    if due_time:
        return due_time
    if is_babylon_supplier(supplier):
        return None
    travel = getattr(leadtask, "travel_date", None)
    if not travel:
        return None
    if hasattr(travel, "hour"):
        if timezone.is_naive(travel):
            return timezone.make_aware(travel, timezone.get_current_timezone())
        return travel
    naive = datetime.combine(travel, datetime.min.time())
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def effective_due_date_for_display(service):
    """Due date for spreadsheets when due_time is unset (falls back to travel date)."""
    if service.due_time:
        return timezone.localdate(service.due_time)
    leadtask = service.leadtask
    travel = getattr(leadtask, "travel_date", None) if leadtask else None
    if travel and hasattr(travel, "date"):
        return travel.date()
    return None
