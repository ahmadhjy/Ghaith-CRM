from datetime import date
from decimal import Decimal

from reporting.payment_amounts import payment_usd_amount
from reporting.statement_refs import invoice_ref_url, invoice_statement_ref, payment_ref_url
from reporting.statement_sort import sort_statement_rows
from sales.models import SalesInvoice
from treasury.models import Payment

try:
    from accounting_bridge.opening_balances import client_opening_balance_dr_cr
except ImportError:
    client_opening_balance_dr_cr = None


def _client_payments_qs(client, date_from=None, date_to=None):
    qs = Payment.objects.filter(
        client=client,
        party_type=Payment.PartyType.CLIENT,
        direction=Payment.Direction.IN,
        status=Payment.Status.POSTED,
    )
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs.select_related("money_account")


def _payment_statement_description(payment: Payment) -> str:
    ref_no = (payment.reference or "").strip() or "—"
    account = payment.money_account.name if payment.money_account_id else "—"
    return f"{ref_no} - {account}"


def _line_visible_by_report_dates(line, date_from=None, date_to=None):
    line_date = line.effective_service_date()
    if date_from and line_date and line_date < date_from:
        return False
    if date_to and line_date and line_date > date_to:
        return False
    return True


def _invoice_total_debit(inv: SalesInvoice) -> tuple[Decimal, bool]:
    """Return (debit amount, show N/A) using invoice header total selling in USD."""
    amt = (inv.grand_total_usd or Decimal("0.00")).quantize(Decimal("0.01"))
    if amt <= 0:
        return Decimal("0.00"), True
    return amt, False


def build_client_statement_rows(client, date_from=None, date_to=None):
    """Service line detail rows plus one debit per invoice (header total selling)."""
    today = date.today()
    rows = []
    if client_opening_balance_dr_cr and date_from:
        opening_debit, opening_credit = client_opening_balance_dr_cr(
            client, statement_date_to=date_to
        )
        if opening_debit or opening_credit:
            rows.append(
                {
                    'date': date_from,
                    'type': 'Opening balance',
                    'description': 'Balance brought forward',
                    'destination': '—',
                    'ref': 'OPEN',
                    'ref_url': None,
                    'debit': opening_debit,
                    'credit': opening_credit,
                    'debit_display_na': False,
                    'sort_seq': None,
                    'sort_id': 'opening',
                    'is_pending': False,
                }
            )

    invoices = (
        SalesInvoice.objects.filter(client=client, status__in=SalesInvoice.reporting_statuses())
        .prefetch_related(
            "lines__service_type__field_definitions",
            "lines__service_instance__service_type__field_definitions",
        )
    )
    for inv in invoices.order_by("issue_date", "created_at"):
        visible_lines = []
        for line in inv.lines.select_related("destination", "service_type", "service_instance__service_type").all():
            if not _line_visible_by_report_dates(line, date_from, date_to):
                continue
            visible_lines.append(line)
        if not visible_lines:
            continue

        for line in visible_lines:
            line_date = line.effective_service_date()
            st = line.service_type
            if not st and line.service_instance_id and line.service_instance:
                st = line.service_instance.service_type
            rows.append(
                {
                    "date": line_date,
                    "type": st.name if st else "Service",
                    "description": line.statement_line_details(),
                    "destination": line.destination.name if line.destination_id else "—",
                    "ref": invoice_statement_ref(inv),
                    "ref_url": invoice_ref_url(inv.id),
                    "debit": Decimal("0.00"),
                    "credit": Decimal("0.00"),
                    "debit_display_na": True,
                    "sort_seq": inv.created_at,
                    "sort_id": str(line.id),
                    "is_pending": bool(line_date and line_date > today),
                }
            )

        total_debit, total_na = _invoice_total_debit(inv)
        rows.append(
            {
                "date": inv.issue_date,
                "type": "Invoice",
                "description": "Total selling",
                "destination": "—",
                "ref": invoice_statement_ref(inv),
                "ref_url": invoice_ref_url(inv.id),
                "debit": total_debit,
                "credit": Decimal("0.00"),
                "debit_display_na": total_na,
                "sort_seq": inv.created_at,
                "sort_id": f"total-{inv.id}",
                "is_pending": bool(inv.issue_date and inv.issue_date > today),
            }
        )

    for pay in _client_payments_qs(client, date_from, date_to).order_by("date", "created_at"):
        rows.append(
            {
                "date": pay.date,
                "type": "Payment",
                "description": _payment_statement_description(pay),
                "destination": "—",
                "ref": pay.receipt_no,
                "ref_url": payment_ref_url(pay.id),
                "debit": Decimal("0.00"),
                "credit": payment_usd_amount(pay),
                "debit_display_na": False,
                "sort_seq": pay.created_at,
                "sort_id": str(pay.id),
                "is_pending": False,
            }
        )

    return sort_statement_rows(rows)
