"""Helpers for invalid/corrupt datetime values in the database."""
from datetime import datetime

from django.db import connection
from django.db.models import Q
from django.utils import timezone


MIN_YEAR = 1970
MAX_YEAR = 2100


def _aware(lo=None, hi=None):
    tz = timezone.get_current_timezone()
    if lo is None:
        lo = datetime(MIN_YEAR, 1, 1)
    if hi is None:
        hi = datetime(MAX_YEAR, 12, 31, 23, 59, 59)
    return timezone.make_aware(lo, tz), timezone.make_aware(hi, tz)


def valid_datetime_bounds():
    return _aware()


def filter_valid_due_times(queryset, prefix=''):
    """Exclude service rows whose due_time cannot be read by Python (out-of-range years)."""
    lo, hi = valid_datetime_bounds()
    field_gte = f'{prefix}due_time__gte' if prefix else 'due_time__gte'
    field_lte = f'{prefix}due_time__lte' if prefix else 'due_time__lte'
    return queryset.filter(**{field_gte: lo, field_lte: hi})


def purchases_services_queryset(queryset):
    """List queryset: valid due_time only; defer heavy leadtask date fields."""
    qs = filter_valid_due_times(queryset)
    return qs.select_related('leadtask', 'leadtask__lead').only(
        'id',
        'service_name',
        'supplier',
        'net',
        'issue_price',
        'due_time',
        'is_checked',
        'leadtask_id',
        'leadtask__id',
        'leadtask__status',
        'leadtask__lead_id',
        'leadtask__lead__id',
        'leadtask__lead__name',
    )


def repair_invalid_datetimes(verbose=False):
    """
    Null out datetime fields PostgreSQL can store but Python cannot read (year < 1970, etc.).
    Returns counts of repaired rows per table/field.
    """
    repairs = {}
    specs = [
        ('tasks_service', 'due_time', 'id'),
        ('tasks_leadtask', 'travel_date', 'id'),
        ('tasks_leadtask', 'return_date', 'id'),
        ('tasks_payment', 'date', 'id'),
    ]
    min_ts = f'{MIN_YEAR}-01-01'
    max_ts = f'{MAX_YEAR}-12-31 23:59:59'

    with connection.cursor() as cursor:
        for table, column, pk_col in specs:
            sql = f"""
                UPDATE {table}
                SET {column} = NULL
                WHERE {column} IS NOT NULL
                  AND ({column} < %s OR {column} > %s)
            """
            cursor.execute(sql, [min_ts, max_ts])
            count = cursor.rowcount
            if count:
                repairs[f'{table}.{column}'] = count
                if verbose:
                    print(f'Cleared {count} invalid {table}.{column} value(s)')

    return repairs


def services_for_leadtask(leadtask):
    """Services for invoice page; skip corrupt due_time values until repaired."""
    from tasks.models import Service

    lo, hi = valid_datetime_bounds()
    return Service.objects.filter(leadtask=leadtask).filter(
        Q(due_time__isnull=True) | Q(due_time__gte=lo, due_time__lte=hi),
    )


def get_leadtask_for_edit(pk):
    """Load a LeadTask for the invoice page; repair corrupt datetimes once and retry."""
    from django.shortcuts import get_object_or_404

    from tasks.models import LeadTask

    def _load():
        return get_object_or_404(
            LeadTask.objects.select_related('lead').prefetch_related('lead__passengers'),
            pk=pk,
        )

    try:
        return _load()
    except (ValueError, OverflowError) as exc:
        if 'year' not in str(exc).lower() and 'range' not in str(exc).lower():
            raise
        repair_invalid_datetimes()
        return _load()
