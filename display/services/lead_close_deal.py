"""Close-deal (finalization) logic — mirrors CRM Step 4: sold, lost, postpone."""

from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone

from display.models import Lead
from display.lead_errors import LeadSyncError


def _parse_money(value) -> float:
    if value is None:
        raise ValueError("empty")
    cleaned = "".join(c for c in str(value).strip() if c.isdigit() or c in ".-")
    if not cleaned:
        raise ValueError("empty")
    return float(cleaned)


def calculate_profit_string(selling_price, net) -> str:
    profit_value = _parse_money(selling_price) - _parse_money(net)
    if profit_value == int(profit_value):
        return str(int(profit_value))
    return str(profit_value)


def parse_follow_up_date(data: dict) -> date | None:
    raw = data.get("follow_up_date")
    if raw is None:
        raw = data.get("follow_up")
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        return raw
    try:
        return datetime.fromisoformat(str(raw).strip()).date()
    except (TypeError, ValueError) as exc:
        raise LeadSyncError(
            "follow_up_date must be an ISO date (YYYY-MM-DD)",
            code="INVALID_DATE",
        ) from exc


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_close_outcome(data: dict) -> str | None:
    outcome = (data.get("outcome") or "").strip().lower()
    if outcome in {"sold", "lost", "postponed", "postpone", "followup", "follow_up"}:
        if outcome in {"postpone", "followup", "follow_up"}:
            return "postponed"
        return outcome
    if _truthy(data.get("sold")):
        return "sold"
    if _truthy(data.get("lost")):
        return "lost"
    if _truthy(data.get("postpone")) or _truthy(data.get("postponed")):
        return "postponed"
    return None


def apply_close_deal(lead: Lead, data: dict) -> Lead:
    """
    Apply one close-deal outcome (mutually exclusive):

    - sold: requires selling_price + net; profit calculated automatically
    - lost: requires why / finalization_notes
    - postponed: requires follow_up_date; status → followup
    """
    outcome = resolve_close_outcome(data)
    if not outcome:
        return lead

    if outcome == "sold":
        selling_price = data.get("selling_price")
        net = data.get("net")
        if selling_price in (None, "") or net in (None, ""):
            raise LeadSyncError(
                "selling_price and net are required when marking as sold",
                code="MISSING_FIELDS",
            )
        try:
            lead.selling_price = str(selling_price).strip()
            lead.net = str(net).strip()
            lead.profit = calculate_profit_string(selling_price, net)
        except ValueError as exc:
            raise LeadSyncError(
                "selling_price and net must be valid numbers",
                code="INVALID_AMOUNT",
            ) from exc
        lead.sold = True
        lead.lost = False
        lead.status = "finalized"
        lead.status_changed_at = timezone.now()

    elif outcome == "lost":
        why = data.get("why")
        if why is None:
            why = data.get("finalization_notes")
        if why is None:
            why = data.get("what_happened")
        if not (why or "").strip():
            raise LeadSyncError(
                "why (or finalization_notes) is required when marking as lost",
                code="MISSING_FIELDS",
            )
        lead.finalization_notes = str(why).strip()
        lead.lost = True
        lead.sold = False
        lead.status = "finalized"
        lead.status_changed_at = timezone.now()

    elif outcome == "postponed":
        follow_up = parse_follow_up_date(data)
        if not follow_up:
            raise LeadSyncError(
                "follow_up_date is required when postponing a lead",
                code="MISSING_FIELDS",
            )
        lead.follow_up = follow_up
        lead.sold = False
        lead.lost = False
        lead.status = "followup"
        lead.status_changed_at = timezone.now()
        try:
            from tasks.calendar_sync import sync_followup_event

            sync_followup_event(lead, user=lead.assigned_to)
        except Exception:
            pass

    lead.save()
    return lead
