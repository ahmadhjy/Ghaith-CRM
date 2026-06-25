from datetime import date
from decimal import Decimal

from django.db.models import Q

from reporting.statement_refs import invoice_ref_url, invoice_statement_ref, payment_ref_url
from reporting.statement_sort import sort_statement_rows
from sales.models import SalesInvoice, SalesInvoiceLine
from treasury.models import Payment

try:
    from accounting_bridge.opening_balances import supplier_opening_balance_dr_cr
except ImportError:
    supplier_opening_balance_dr_cr = None


def _supplier_payments_qs(supplier, date_from=None, date_to=None):
    qs = Payment.objects.filter(
        supplier=supplier,
        party_type=Payment.PartyType.SUPPLIER,
        direction=Payment.Direction.OUT,
        status=Payment.Status.POSTED,
    ).select_related("money_account")
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


def _payment_supplier_description(payment: Payment) -> str:
    return payment.money_account.name if payment.money_account_id else "—"


def _line_visible_by_report_dates(line, date_from=None, date_to=None):
    line_date = line.effective_service_date()
    if date_from and line_date and line_date < date_from:
        return False
    if date_to and line_date and line_date > date_to:
        return False
    return True


def build_supplier_statement_rows(supplier, date_from=None, date_to=None):
    """One credit row per invoice service line (cost); one debit per supplier payment."""
    today = date.today()
    rows = []
    if supplier_opening_balance_dr_cr and date_from:
        opening_debit, opening_credit = supplier_opening_balance_dr_cr(
            supplier, statement_date_to=date_to
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
                    'sort_seq': None,
                    'sort_id': 'opening',
                    'is_pending': False,
                }
            )

    lines = (
        SalesInvoiceLine.objects.filter(
            supplier=supplier,
            crm_issued=True,
            invoice__status__in=SalesInvoice.reporting_statuses(),
        )
        .select_related(
            "invoice",
            "service_type",
            "destination",
            "service_instance__service_type",
        )
        .prefetch_related("service_type__field_definitions")
    )

    for line in lines.order_by("service_date", "invoice__issue_date", "invoice__created_at", "id"):
        if not _line_visible_by_report_dates(line, date_from, date_to):
            continue
        inv = line.invoice
        svc_date = line.effective_service_date()
        amt = line.line_cost_amount_usd().quantize(Decimal("0.01"))
        st = line.service_type
        if not st and line.service_instance_id and line.service_instance:
            st = line.service_instance.service_type
        rows.append(
            {
                "date": svc_date,
                "type": st.name if st else "Service",
                "description": line.supplier_statement_description(),
                "destination": line.destination.name if line.destination_id else "—",
                "ref": invoice_statement_ref(inv),
                "ref_url": invoice_ref_url(inv.id),
                "debit": Decimal("0.00"),
                "credit": amt,
                "sort_seq": inv.created_at,
                "sort_id": str(line.id),
                "is_pending": bool(svc_date and svc_date > today),
            }
        )

    for pay in _supplier_payments_qs(supplier, date_from, date_to).order_by("date", "created_at"):
        rows.append(
            {
                "date": pay.date,
                "type": "Payment",
                "description": _payment_supplier_description(pay),
                "destination": "—",
                "ref": pay.receipt_no,
                "ref_url": payment_ref_url(pay.id),
                "debit": pay.amount,
                "credit": Decimal("0.00"),
                "sort_seq": pay.created_at,
                "sort_id": str(pay.id),
                "is_pending": False,
            }
        )

    return sort_statement_rows(rows)
