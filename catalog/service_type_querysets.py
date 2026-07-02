"""Accounting service types limited to the CRM predefined service list."""

from django.db.models import Q

from catalog.models import ServiceType


def _accounting_ids_for_crm_predefined_services() -> list:
    """Ensure every active CRM ServiceType has a catalog row; return their IDs."""
    from accounting_bridge.services.master_data import sync_service_type
    from tasks.models import ServiceType as CrmServiceType

    ids = []
    for crm_row in CrmServiceType.objects.filter(is_active=True).order_by("name"):
        acc = sync_service_type(crm_row.name)
        if acc:
            ids.append(acc.pk)
    return ids


def crm_predefined_service_types(*, extra_pk=None):
    """
    Full CRM predefined service list for accounting dropdowns and catalog pages.

    Auto-creates missing catalog ServiceType rows from active CRM ServiceType records
    so the dropdown always matches the CRM clean list, not only services seen on past orders.
    """
    acc_ids = _accounting_ids_for_crm_predefined_services()
    qs = ServiceType.objects.filter(pk__in=acc_ids, is_active=True).order_by("name")
    if extra_pk:
        qs = ServiceType.objects.filter(Q(pk=extra_pk) | Q(pk__in=acc_ids)).distinct().order_by("name")
    return qs
