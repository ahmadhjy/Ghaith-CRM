"""One-off and migration helpers for purchases (supplier services) issued state."""

PAST_TRAVEL_YEARS = (2024, 2025)


def mark_past_travel_services_issued(apps=None):
    """
    Set is_checked on purchases-list services whose CRM order travel date is in 2024 or 2025.
    When apps is provided (migrations), uses historical models; otherwise uses live models.
    """
    if apps is not None:
        Service = apps.get_model('tasks', 'Service')
        Event = apps.get_model('dashboard', 'Event')
    else:
        from dashboard.models import Event
        from tasks.models import Service

    service_ids = list(
        Service.objects.filter(
            due_time__isnull=False,
            is_checked=False,
            leadtask__travel_date__year__in=PAST_TRAVEL_YEARS,
        ).values_list('pk', flat=True)
    )
    if not service_ids:
        return 0

    Service.objects.filter(pk__in=service_ids).update(is_checked=True)
    Event.objects.filter(service_id__in=service_ids, done=False).update(done=True)
    return len(service_ids)
