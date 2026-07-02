"""Qualification step logic — mirrors CRM Step 2."""

from __future__ import annotations

from django.utils import timezone

from display.models import Lead
from display.services.lead_close_deal import parse_follow_up_date
from display.lead_errors import LeadSyncError


def resolve_qualification_action(data: dict) -> str | None:
    action = (data.get("qualification_action") or "").strip().lower()
    if action:
        return action
    if data.get("advance_to_negotiation") in (True, "true", "1", 1):
        return "advance_to_negotiation"
    if data.get("unqualified") in (True, "true", "1", 1):
        return "mark_unqualified"
    if data.get("save_and_exit") in (True, "true", "1", 1):
        return "save_and_exit"
    return None


def apply_qualification_fields(lead: Lead, data: dict) -> None:
    if data.get("special_request") is not None:
        lead.special_request = (data.get("special_request") or "").strip()
    if data.get("assignment_notes") is not None:
        lead.assignment_notes = (data.get("assignment_notes") or "").strip()
    if data.get("why_this_destination") is not None:
        lead.why_this_destination = (data.get("why_this_destination") or "").strip()
    if data.get("date_notes") is not None:
        lead.date_notes = (data.get("date_notes") or "").strip()
    if data.get("pax") is not None:
        lead.pax = (data.get("pax") or "").strip()
    if data.get("duration") is not None:
        lead.duration = (data.get("duration") or "").strip()
    if data.get("urgent") is not None:
        lead.urgent = bool(data.get("urgent"))

    what_happened = data.get("what_happened")
    if what_happened is None:
        what_happened = data.get("finalization_notes")
    if what_happened is not None:
        lead.finalization_notes = (what_happened or "").strip()

    if data.get("budget_range_from") is not None:
        lead.budget_range_from = data.get("budget_range_from") or None
    if data.get("budget_range_to") is not None:
        lead.budget_range_to = data.get("budget_range_to") or None

    if data.get("follow_up_date") is not None or data.get("follow_up") is not None:
        follow_up = parse_follow_up_date(data)
        if follow_up:
            lead.follow_up = follow_up


def apply_qualification_action(lead: Lead, data: dict) -> Lead:
    apply_qualification_fields(lead, data)

    action = resolve_qualification_action(data)
    if action in (None, "", "save"):
        return lead

    if action in {"save_and_exit", "save_processing", "processing"}:
        lead.status = "processing"
        lead.status_changed_at = timezone.now()
    elif action in {"advance_to_negotiation", "next", "negotiation"}:
        lead.status = "negotiation"
        lead.status_changed_at = timezone.now()
        lead.period = 10
        lead.moved_to_negotiation = True
    elif action in {"mark_unqualified", "unqualified", "unqualify"}:
        lead.status = "done"
        lead.lost = True
        lead.status_changed_at = timezone.now()
    else:
        raise LeadSyncError(
            f"Unknown qualification_action '{action}'",
            code="INVALID_ACTION",
        )

    lead.save()
    return lead
