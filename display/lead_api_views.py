"""JSON API views for WhatsApp AI dashboard → CRM lead synchronization."""

from __future__ import annotations

from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from display.api_utils import auth_or_401, json_error, parse_json_body
from display.constants import DEPARTMENT_DEFINITIONS, LEAD_STATUS_API_LABELS
from display.models import CrmNotification, Department, Lead
from display.lead_errors import LeadSyncError
from display.services.lead_sync import (
    create_or_update_lead_from_dashboard,
    serialize_lead,
    update_lead_from_dashboard,
)


@csrf_exempt
@require_http_methods(["GET"])
def api_list_departments(request):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    departments = Department.objects.filter(is_active=True).order_by("sort_order", "name")
    data = [
        {
            "code": dept.code,
            "name": dept.name,
            "users": [
                {
                    "id": profile.user_id,
                    "username": profile.user.username,
                    "full_name": profile.user.get_full_name().strip() or profile.user.username,
                    "receives_lead_assignments": profile.receives_lead_assignments,
                }
                for profile in dept.users.select_related("user").filter(user__is_active=True)
            ],
        }
        for dept in departments
    ]
    return JsonResponse(
        {
            "departments": data,
            "status_values": [
                {"value": value, "label": LEAD_STATUS_API_LABELS[value]}
                for value in sorted(LEAD_STATUS_API_LABELS)
            ],
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["GET"])
def api_list_lead_stages(request):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized
    return JsonResponse(
        {
            "stages": [
                {"value": value, "label": label}
                for value, label in LEAD_STATUS_API_LABELS.items()
            ]
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_sync_lead(request):
    """
    Create or update a CRM lead from the WhatsApp AI dashboard.

  Scope: Lead model only. Does not create tasks, orders, or other entities.
    """
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    data, err = parse_json_body(request)
    if err:
        return err

    try:
        lead, created = create_or_update_lead_from_dashboard(data)
    except LeadSyncError as exc:
        return json_error(exc.message, code=exc.code, extra=exc.details or None)

    return JsonResponse(serialize_lead(lead), status=201 if created else 200)


@csrf_exempt
def api_lead_detail(request, lead_id: int):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    lead = get_object_or_404(Lead, pk=lead_id)
    if request.method == "GET":
        return JsonResponse(serialize_lead(lead), status=200)

    if request.method in ("PATCH", "PUT"):
        data, err = parse_json_body(request)
        if err:
            return err
        try:
            lead = update_lead_from_dashboard(lead, data)
        except LeadSyncError as exc:
            return json_error(exc.message, code=exc.code, extra=exc.details or None)
        return JsonResponse(serialize_lead(lead), status=200)

    return json_error("Method not allowed", status=405, code="METHOD_NOT_ALLOWED")


@csrf_exempt
@require_http_methods(["POST", "PATCH", "PUT"])
def api_qualify_lead(request, lead_id: int):
    """CRM Step 2 — qualification."""
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    lead = get_object_or_404(Lead, pk=lead_id)
    data, err = parse_json_body(request)
    if err:
        return err
    try:
        lead = update_lead_from_dashboard(lead, data)
    except LeadSyncError as exc:
        return json_error(exc.message, code=exc.code, extra=exc.details or None)
    return JsonResponse(serialize_lead(lead), status=200)


@csrf_exempt
@require_http_methods(["POST", "PATCH", "PUT"])
def api_close_deal(request, lead_id: int):
    """CRM Step 4 — close deal (sold / lost / postponed)."""
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    lead = get_object_or_404(Lead, pk=lead_id)
    data, err = parse_json_body(request)
    if err:
        return err
    try:
        lead = update_lead_from_dashboard(lead, data)
    except LeadSyncError as exc:
        return json_error(exc.message, code=exc.code, extra=exc.details or None)
    return JsonResponse(serialize_lead(lead), status=200)


@csrf_exempt
@require_http_methods(["GET"])
def api_get_lead(request, lead_id: int):
    return api_lead_detail(request, lead_id)


@csrf_exempt
@require_http_methods(["PATCH", "PUT"])
def api_update_lead(request, lead_id: int):
    return api_lead_detail(request, lead_id)


@csrf_exempt
@require_http_methods(["GET"])
def api_search_leads(request):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    phone = (request.GET.get("phone") or "").strip()
    external_id = (request.GET.get("external_id") or "").strip()
    if not phone and not external_id:
        return json_error(
            "phone or external_id query parameter is required",
            code="MISSING_FIELDS",
        )

    qs = Lead.objects.all().order_by("-created_at")
    if external_id:
        qs = qs.filter(external_id=external_id)
    if phone:
        qs = qs.filter(phone__icontains=phone)

    return JsonResponse({"results": [serialize_lead(lead) for lead in qs[:50]]}, status=200)


# --- Backward-compatible contact endpoints (Lead-only) ---


@csrf_exempt
@require_http_methods(["POST"])
def api_create_contact(request):
    """Legacy alias for POST /api/leads/."""
    return api_sync_lead(request)


@csrf_exempt
@require_http_methods(["GET"])
def api_search_contact_by_phone(request):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized
    return api_search_leads(request)


@csrf_exempt
@require_http_methods(["GET"])
def api_get_contact_by_phone(request):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    phone = (request.GET.get("phone") or "").strip()
    if not phone:
        return json_error("phone query parameter is required", code="MISSING_FIELDS")

    lead = Lead.objects.filter(phone=phone).order_by("-created_at").first()
    if not lead:
        return json_error(f"No contact found for phone {phone}", status=404, code="CONTACT_NOT_FOUND")
    return JsonResponse(serialize_lead(lead), status=200)


@csrf_exempt
@require_http_methods(["GET"])
def api_list_destinations(request):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    from display.models import Destination

    destinations = Destination.objects.all().order_by("name")
    data = [{"id": d.id, "name": d.name} for d in destinations]
    return JsonResponse({"destinations": data}, status=200)


@csrf_exempt
@require_http_methods(["GET"])
def api_list_departures(request):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    codes = (
        Lead.objects.exclude(country_code__isnull=True)
        .exclude(country_code__exact="")
        .values_list("country_code", flat=True)
        .distinct()
    )
    return JsonResponse({"departures": [{"code": code} for code in codes]}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def api_create_followup(request, lead_id: int):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    lead = get_object_or_404(Lead, pk=lead_id)
    data, err = parse_json_body(request)
    if err:
        return err

    follow_up_date_str = data.get("follow_up_date")
    if not follow_up_date_str:
        return json_error("follow_up_date is required", code="MISSING_FIELDS")

    try:
        follow_up_date = datetime.fromisoformat(follow_up_date_str).date()
    except (TypeError, ValueError):
        return json_error("follow_up_date must be an ISO date string", code="INVALID_DATE")

    lead.follow_up = follow_up_date
    if data.get("notes"):
        existing_notes = (lead.date_notes or "").strip()
        new_note = data["notes"]
        lead.date_notes = f"{existing_notes}\n{new_note}" if existing_notes else new_note
    lead.status = "followup"
    lead.save()

    if data.get("create_calendar_event"):
        try:
            from dashboard.models import Event

            Event.objects.create(
                user=lead.assigned_to,
                title=f"Follow-up: {lead.name}",
                description=f"API follow-up for lead: {lead.name} - {lead.destination or 'No destination'}",
                when=lead.follow_up,
                event_type="invoice",
            )
        except Exception:
            pass

    return JsonResponse(
        {
            "id": lead.id,
            "follow_up_date": str(lead.follow_up),
            "status": lead.status,
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_create_crm_notification(request):
    unauthorized = auth_or_401(request)
    if unauthorized:
        return unauthorized

    data, err = parse_json_body(request)
    if err:
        return err

    phone = (data.get("phone") or "").strip()
    if not phone:
        return json_error("phone is required", code="MISSING_FIELDS")

    lead = None
    lead_id = data.get("lead_id")
    if lead_id:
        lead = Lead.objects.filter(pk=lead_id).first()
    if not lead:
        lead = Lead.objects.filter(phone=phone).order_by("-created_at").first()

    notification = CrmNotification.objects.create(
        lead=lead,
        phone=phone,
        summary_section=(data.get("summary_section") or data.get("chat_summary") or ""),
        department=(data.get("department") or ""),
        channel=(data.get("channel") or ""),
        metadata=data.get("metadata"),
    )

    return JsonResponse(
        {
            "id": notification.id,
            "lead_id": lead.id if lead else None,
            "created_at": notification.created_at.isoformat(),
        },
        status=201,
    )


def seed_departments():
    for sort_order, (code, name) in enumerate(DEPARTMENT_DEFINITIONS):
        Department.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_active": True, "sort_order": sort_order},
        )
