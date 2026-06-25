import uuid

from sales.models import SalesInvoice


def next_temp_invoice_no() -> str:
    """Display-friendly temporary invoice number before posting assigns final sequence."""
    while True:
        candidate = f"TMP-{uuid.uuid4().hex[:8].upper()}"
        if not SalesInvoice.objects.filter(invoice_no=candidate).exists():
            return candidate


def ensure_invoice_has_number(invoice: SalesInvoice) -> str:
    """Assign a temporary number to drafts that have none (e.g. CRM sync)."""
    if invoice.invoice_no and not invoice.invoice_no.startswith("TMP-"):
        return invoice.invoice_no
    if invoice.invoice_no and invoice.invoice_no.startswith("TMP-"):
        return invoice.invoice_no
    invoice.invoice_no = next_temp_invoice_no()
    return invoice.invoice_no
