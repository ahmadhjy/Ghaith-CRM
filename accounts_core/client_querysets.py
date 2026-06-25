"""Client list visibility: show financially active clients by default, all when searching."""

from django.db.models import Exists, OuterRef, Q

from accounts_core.models import Client


def _has_invoice():
    from sales.models import SalesInvoice

    return Exists(
        SalesInvoice.objects.filter(
            client_id=OuterRef("pk"),
            status__in=SalesInvoice.reporting_statuses(),
        )
    )


def _has_opening_balance():
    from accounting_bridge.models import PartyOpeningBalance

    return Exists(
        PartyOpeningBalance.objects.filter(
            client_id=OuterRef("pk"),
            party_type=PartyOpeningBalance.PartyType.CLIENT,
        ).exclude(debit_usd=0, credit_usd=0)
    )


def _has_client_payment():
    from treasury.models import Payment

    return Exists(
        Payment.objects.filter(
            client_id=OuterRef("pk"),
            party_type=Payment.PartyType.CLIENT,
        )
    )


def clients_with_accounting_activity():
    """Clients with invoices, opening balances, or client payments (non-empty statement)."""
    return (
        Client.objects.annotate(
            _has_inv=_has_invoice(),
            _has_ob=_has_opening_balance(),
            _has_pay=_has_client_payment(),
        )
        .filter(Q(_has_inv=True) | Q(_has_ob=True) | Q(_has_pay=True))
        .distinct()
    )


def clients_for_select(*, extra_pk=None):
    """Dropdown options: active clients plus the currently selected row (if any)."""
    active_ids = clients_with_accounting_activity().values_list("pk", flat=True)
    qs = Client.objects.filter(pk__in=active_ids)
    if extra_pk:
        qs = Client.objects.filter(Q(pk=extra_pk) | Q(pk__in=active_ids))
    return qs.order_by("name_en").distinct()


def search_clients(q: str = "", *, limit: int = 50):
    """Search all clients by name or code (for typeahead in dropdowns and list search)."""
    qs = Client.objects.all().order_by("name_en")
    q = (q or "").strip()
    if q:
        qs = qs.filter(
            Q(name_en__icontains=q)
            | Q(name_ar__icontains=q)
            | Q(client_code__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
        )
    return qs[:limit]


def client_choice_label(client: Client) -> str:
    return f"{client.client_code} — {client.name_en}"
