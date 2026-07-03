"""Invoice number assignment — final INV sequence at creation (no TMP drafts)."""

from django.utils import timezone

from sales.models import SalesInvoice


def next_invoice_no(*, year=None) -> str:
    from accounts_core.models import DocumentSequence

    y = year or timezone.localdate().year
    return DocumentSequence.next_value("INV", "INV-", y)


def next_temp_invoice_no() -> str:
    """Backward-compatible alias; new invoices use INV- immediately."""
    return next_invoice_no()


def ensure_invoice_has_number(invoice: SalesInvoice) -> str:
    """Assign an invoice number when missing (e.g. CRM sync)."""
    if invoice.invoice_no and not invoice.invoice_no.startswith("TMP-"):
        return invoice.invoice_no
    invoice.invoice_no = next_invoice_no(
        year=invoice.issue_date.year if invoice.issue_date else None
    )
    return invoice.invoice_no
