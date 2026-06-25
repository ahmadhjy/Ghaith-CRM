from decimal import Decimal

from django.db.models import Sum

from reporting.payment_amounts import payment_usd_amount
from sales.models import SalesInvoice, SalesInvoiceLine
from treasury.models import Payment

try:
    from accounting_bridge.opening_balances import client_opening_balance_usd, supplier_opening_balance_usd
except ImportError:
    client_opening_balance_usd = None
    supplier_opening_balance_usd = None


def _client_payments_qs(client, date_from=None, date_to=None, on_or_before=None):
    from reporting.client_statement_rows import _client_payments_qs as qs_fn

    qs = qs_fn(client, date_from=date_from, date_to=date_to)
    if on_or_before is not None:
        qs = qs.filter(date__lte=on_or_before)
    return qs


def _supplier_payments_qs(supplier, date_from=None, date_to=None, on_or_before=None):
    from reporting.supplier_statement_rows import _supplier_payments_qs as qs_fn

    qs = qs_fn(supplier, date_from=date_from, date_to=date_to)
    if on_or_before is not None:
        qs = qs.filter(date__lte=on_or_before)
    return qs


def client_ar_balance(client, on_or_before):
    if on_or_before is None:
        return Decimal("0.00")
    inv = (
        SalesInvoice.objects.filter(
            client=client,
            status__in=SalesInvoice.reporting_statuses(),
            issue_date__lte=on_or_before,
        ).aggregate(t=Sum("grand_total_usd"))["t"]
        or Decimal("0.00")
    )
    payments = sum(
        (payment_usd_amount(p) for p in _client_payments_qs(client, on_or_before=on_or_before)),
        Decimal("0.00"),
    )
    opening = client_opening_balance_usd(client, on_or_before=on_or_before) if client_opening_balance_usd else Decimal("0.00")
    return opening + inv - payments


def supplier_ap_balance(supplier, on_or_before):
    if on_or_before is None:
        return Decimal("0.00")
    lines = SalesInvoiceLine.objects.filter(
        supplier=supplier,
        invoice__status__in=SalesInvoice.reporting_statuses(),
        invoice__issue_date__lte=on_or_before,
    )
    costs = sum((line.line_cost_amount_usd() for line in lines), Decimal("0.00"))
    payments = sum((p.amount for p in _supplier_payments_qs(supplier, on_or_before=on_or_before)), Decimal("0.00"))
    opening = supplier_opening_balance_usd(supplier, on_or_before=on_or_before) if supplier_opening_balance_usd else Decimal("0.00")
    return opening + costs - payments


def supplier_line_purchases(supplier, date_from=None, date_to=None):
    lines = SalesInvoiceLine.objects.filter(
        supplier=supplier,
        invoice__status__in=SalesInvoice.reporting_statuses(),
    )
    if date_from:
        lines = lines.filter(service_date__gte=date_from)
    if date_to:
        lines = lines.filter(service_date__lte=date_to)
    return sum((line.line_cost_amount_usd() for line in lines), Decimal("0.00"))
