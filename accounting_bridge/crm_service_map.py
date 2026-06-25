"""Map CRM Service rows to accounting SalesInvoiceLine fields (1:1 with CRM invoice table)."""

from __future__ import annotations

from decimal import Decimal

from tasks.constants import effective_service_net
from tasks.models import Service

from accounting_bridge.services.master_data import sync_destination, sync_service_type, sync_supplier
from accounting_bridge.services.line_flags_sync import (
    merge_issue_price_from_crm,
    merge_line_flags_from_crm,
)
from accounting_bridge.utils import parse_money


def build_crm_line_notes(service: Service) -> str:
    """Details + voucher + issue-price note — mirrors CRM Description column."""
    parts = []
    details = (service.details or '').strip()
    if details:
        parts.append(details)
    voucher = (service.voucher_id or '').strip()
    if voucher:
        parts.append(f'Voucher: {voucher}')
    net = (service.net or '').strip()
    issue = (service.issue_price or '').strip()
    if issue and issue != net:
        if net:
            parts.append(f'Booking net: {net}')
        parts.append(f'Issue price: {issue}')
    return '\n'.join(parts)


def crm_service_to_line_kwargs(
    service: Service,
    *,
    employee,
    header_destination,
    issue_date,
    sort_order: int,
    existing_line=None,
) -> dict:
    """
    CRM services table → accounting invoice line.

    CRM column          Accounting field
    ─────────────────   ────────────────
    Service             service_type
    Supplier            supplier
    Details             notes (+ voucher/issue text)
    Net                 cost_price (issue price overrides net when set)
    Selling             sell_price
    Due                 service_date
    (Voucher)           included in notes
    """
    service_type = sync_service_type(service.service_name)
    supplier = sync_supplier(service.supplier)
    destination = header_destination

    service_date = issue_date
    if service.due_time:
        service_date = service.due_time.date()

    issue_price = merge_issue_price_from_crm(service, existing_line)
    sent, issued = merge_line_flags_from_crm(service, existing_line)
    cost_net = parse_money(effective_service_net(service))
    if issue_price:
        cost_net = parse_money(issue_price)

    return {
        'service_type': service_type,
        'supplier': supplier,
        'line_employee': employee,
        'destination': destination,
        'service_date': service_date,
        'qty': Decimal('1'),
        'sell_price': parse_money(service.selling),
        'cost_price': cost_net,
        'line_discount': Decimal('0'),
        'notes': build_crm_line_notes(service),
        'send_to_client': sent,
        'crm_issued': issued,
        'line_data': {
            'issue_price': issue_price,
        },
        'sort_order': sort_order,
    }
