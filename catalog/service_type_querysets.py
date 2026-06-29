"""Accounting service types limited to the CRM predefined service list."""

from django.db.models import Q

from catalog.models import ServiceType


def crm_predefined_service_types(*, extra_pk=None):
    """
    Catalog service types that match active CRM ServiceType rows (predefined order services).

    Excludes legacy free-text service names synced from old CRM orders.
    """
    from accounting_bridge.models import CrmServiceTypeLink
    from tasks.models import ServiceType as CrmServiceType

    active_crm = CrmServiceType.objects.filter(is_active=True)
    linked_ids = CrmServiceTypeLink.objects.filter(
        crm_service_type__in=active_crm
    ).values_list("acc_service_type_id", flat=True)
    names = list(active_crm.values_list("name", flat=True))

    if not names and not linked_ids:
        qs = ServiceType.objects.none()
    else:
        filters = Q(pk__in=linked_ids)
        if names:
            name_q = Q()
            for name in names:
                name_q |= Q(name__iexact=name)
            filters |= name_q
        qs = ServiceType.objects.filter(is_active=True).filter(filters).distinct()

    if extra_pk:
        qs = ServiceType.objects.filter(
            Q(pk=extra_pk) | Q(pk__in=qs.values_list("pk", flat=True))
        ).distinct()
    return qs.order_by("name")
