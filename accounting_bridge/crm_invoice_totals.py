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
