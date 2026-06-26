"""Map CRM order header total selling (lead.selling_price) onto accounting invoices."""

from decimal import Decimal

from accounting_bridge.utils import parse_money


def get_crm_lead_for_invoice(invoice):
    from accounting_bridge.models import InvoiceSyncQueue

    queue = (
        InvoiceSyncQueue.objects.filter(sales_invoice_id=invoice.pk)
        .select_related("leadtask__lead")
        .first()
    )
    if not queue or not queue.leadtask_id:
        return None
    return queue.leadtask.lead


def crm_lead_selling_total(lead) -> Decimal | None:
    if lead is None:
        return None
    total = parse_money(lead.selling_price)
    if total <= 0:
        return None
    return total


def format_lead_selling_price(total: Decimal) -> str:
    q = total.quantize(Decimal("0.01"))
    text = f"{q:.2f}"
    if text.endswith(".00"):
        return text[:-3]
    if text.endswith("0"):
        return text.rstrip("0").rstrip(".")
    return text


def apply_invoice_header_selling(invoice, total: Decimal) -> None:
    discount = invoice.discount_total or Decimal("0.00")
    invoice.subtotal = total + discount
    invoice.grand_total = total


def push_invoice_selling_to_crm(invoice, total: Decimal) -> bool:
    """Accounting → CRM: update lead.selling_price on the linked order."""
    lead = get_crm_lead_for_invoice(invoice)
    if not lead:
        return False
    new_value = format_lead_selling_price(total) if total > 0 else ""
    if (lead.selling_price or "").strip() != new_value:
        lead.selling_price = new_value
        lead.save(update_fields=["selling_price"])
    return True


def apply_header_selling_from_post(request, invoice) -> bool:
    """
    Read total selling from the accounting invoice form.

    Returns True when the header total was applied (skip re-summing line selling).
    """
    if not request or "invoice_total_selling" not in request.POST:
        return False
    raw = (request.POST.get("invoice_total_selling") or "").strip()
    total = parse_money(raw) if raw else Decimal("0.00")
    apply_invoice_header_selling(invoice, total)
    push_invoice_selling_to_crm(invoice, total)
    return True


def apply_crm_lead_selling_to_invoice(invoice, lead=None) -> bool:
    """
    Use CRM order total selling on the accounting invoice header.

    Returns True when lead.selling_price was applied; False to keep line-based totals.
    """
    lead = lead or get_crm_lead_for_invoice(invoice)
    total = crm_lead_selling_total(lead)
    if total is None:
        return False
    discount = invoice.discount_total or Decimal("0.00")
    invoice.subtotal = total + discount
    invoice.grand_total = total
    return True
