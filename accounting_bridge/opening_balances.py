from decimal import Decimal

from django.db.models import Sum

from accounting_bridge.models import PartyOpeningBalance


def _opening_qs(*, party_type, client=None, supplier=None, on_or_before=None, statement_date_to=None):
    qs = PartyOpeningBalance.objects.filter(party_type=party_type)
    if client is not None:
        qs = qs.filter(client=client)
    if supplier is not None:
        qs = qs.filter(supplier=supplier)
    if on_or_before is not None:
        qs = qs.filter(as_of_date__lte=on_or_before)
    elif statement_date_to is not None:
        # Statement: include openings effective on or before period end.
        qs = qs.filter(as_of_date__lte=statement_date_to)
    return qs


def client_opening_balance_dr_cr(
    client,
    on_or_before=None,
    *,
    statement_date_to=None,
) -> tuple[Decimal, Decimal]:
    """Total opening debit and credit for a client (USD).

    Use on_or_before for balance snapshots (e.g. day before period start).
    Use statement_date_to when building SOA rows (do not pass statement date_from here).
    """
    agg = _opening_qs(
        party_type=PartyOpeningBalance.PartyType.CLIENT,
        client=client,
        on_or_before=on_or_before,
        statement_date_to=statement_date_to,
    ).aggregate(debit=Sum('debit_usd'), credit=Sum('credit_usd'))
    debit = (agg['debit'] or Decimal('0.00')).quantize(Decimal('0.01'))
    credit = (agg['credit'] or Decimal('0.00')).quantize(Decimal('0.01'))
    return debit, credit


def supplier_opening_balance_dr_cr(
    supplier,
    on_or_before=None,
    *,
    statement_date_to=None,
) -> tuple[Decimal, Decimal]:
    """Total opening debit and credit for a supplier (USD)."""
    agg = _opening_qs(
        party_type=PartyOpeningBalance.PartyType.SUPPLIER,
        supplier=supplier,
        on_or_before=on_or_before,
        statement_date_to=statement_date_to,
    ).aggregate(debit=Sum('debit_usd'), credit=Sum('credit_usd'))
    debit = (agg['debit'] or Decimal('0.00')).quantize(Decimal('0.01'))
    credit = (agg['credit'] or Decimal('0.00')).quantize(Decimal('0.01'))
    return debit, credit


def client_opening_balance_usd(client, on_or_before=None) -> Decimal:
    debit, credit = client_opening_balance_dr_cr(client, on_or_before=on_or_before)
    return (debit - credit).quantize(Decimal('0.01'))


def supplier_opening_balance_usd(supplier, on_or_before=None) -> Decimal:
    debit, credit = supplier_opening_balance_dr_cr(supplier, on_or_before=on_or_before)
    return (credit - debit).quantize(Decimal('0.01'))
