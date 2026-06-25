"""Bidirectional sync of CRM ↔ accounting line flags (issued, sent to client, issue price)."""

from __future__ import annotations

from tasks.models import Service


def merge_line_flags_from_crm(service, existing_line=None) -> tuple[bool, bool]:
    """
    Sticky OR: once issued/sent in either system, CRM refresh does not clear accountant flags.
    """
    sent = bool(service.send_to_client)
    issued = bool(service.is_checked)
    if existing_line is not None:
        sent = sent or bool(existing_line.send_to_client)
        issued = issued or bool(existing_line.crm_issued)
    return sent, issued


def merge_issue_price_from_crm(service, existing_line=None) -> str:
    crm_issue = (service.issue_price or '').strip()
    if crm_issue:
        return crm_issue
    if existing_line is not None:
        return ((existing_line.line_data or {}).get('issue_price') or '').strip()
    return ''


def push_accounting_line_flags_to_crm(line) -> None:
    """Accounting → CRM for linked service rows only."""
    if not line.crm_service_id:
        return
    service = Service.objects.filter(pk=line.crm_service_id).first()
    if not service:
        return
    issue = ((line.line_data or {}).get('issue_price') or '').strip()
    updates = {}
    if service.is_checked != bool(line.crm_issued):
        updates['is_checked'] = bool(line.crm_issued)
    if service.send_to_client != bool(line.send_to_client):
        updates['send_to_client'] = bool(line.send_to_client)
    if (service.issue_price or '').strip() != issue:
        updates['issue_price'] = issue
    if updates:
        Service.objects.filter(pk=service.pk).update(**updates)
