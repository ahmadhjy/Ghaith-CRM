"""Correct, permission-scoped calculations for the CRM performance dashboard."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from display.models import Lead, MonthlyTarget, Offer, UserMonthlyTarget
from tasks.constants import parse_money
from tasks.models import LeadTask


def parse_date_range(params, *, default_days=30):
    today = timezone.localdate()
    default_start = today - timedelta(days=default_days - 1)

    def clean(name, fallback):
        try:
            return datetime.strptime((params.get(name) or "").strip(), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return fallback

    start = clean("date_from", default_start)
    end = clean("date_to", today)
    if start > end:
        start, end = end, start
    start_dt = timezone.make_aware(datetime.combine(start, time.min))
    end_dt = timezone.make_aware(datetime.combine(end, time.max))
    return start, end, start_dt, end_dt


def modified_leads_q(start_dt, end_dt):
    return Q(last_modified__range=(start_dt, end_dt))


def modified_orders_q(start_dt, end_dt):
    return (
        Q(updated_at__range=(start_dt, end_dt))
        | Q(lead__last_modified__range=(start_dt, end_dt))
    )


def order_financials(order):
    services = list(order.service_set.all())
    revenue = parse_money(order.lead.selling_price)
    booking_cost = sum(parse_money(service.net) for service in services)
    purchase_cost = sum(
        parse_money(service.issue_price or service.net) for service in services
    )
    return {
        "revenue": revenue,
        "booking_cost": booking_cost,
        "purchase_cost": purchase_cost,
        "booking_profit": revenue - booking_cost,
        "post_issue_profit": revenue - purchase_cost,
    }


def _overlapping_months(start: date, end: date):
    cursor = start.replace(day=1)
    final = end.replace(day=1)
    while cursor <= final:
        yield cursor
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)


def _target_for_months(model, months, **filters):
    total = 0
    for month in months:
        row = model.objects.filter(
            month__year=month.year,
            month__month=month.month,
            **filters,
        ).first()
        total += row.target_profit if row else 0
    return total


def build_stats_dashboard_context(request):
    start, end, start_dt, end_dt = parse_date_range(request.GET)
    can_view_team = request.user.is_staff or request.user.is_superuser

    leads = Lead.objects.filter(modified_leads_q(start_dt, end_dt))
    orders = LeadTask.objects.filter(
        modified_orders_q(start_dt, end_dt),
        lead__sold=True,
    ).select_related("lead", "assigned_to").prefetch_related("service_set").distinct()

    if can_view_team:
        employees = User.objects.filter(is_sales=True, is_active=True).order_by(
            "first_name", "username"
        )
    else:
        employees = User.objects.filter(pk=request.user.pk)
        leads = leads.filter(assigned_to=request.user)
        orders = orders.filter(assigned_to=request.user)

    finances_by_employee = defaultdict(
        lambda: {"profit": 0.0, "revenue": 0.0, "sales": 0}
    )
    daily_profit = defaultdict(float)
    daily_revenue = defaultdict(float)
    total_profit = 0.0
    total_revenue = 0.0

    for order in orders:
        values = order_financials(order)
        total_profit += values["booking_profit"]
        total_revenue += values["revenue"]
        bucket = finances_by_employee[order.assigned_to_id]
        bucket["profit"] += values["booking_profit"]
        bucket["revenue"] += values["revenue"]
        bucket["sales"] += 1
        stamp = order.updated_at or order.lead.last_modified
        day = timezone.localtime(stamp).date() if stamp else start
        daily_profit[day] += values["booking_profit"]
        daily_revenue[day] += values["revenue"]

    months = list(_overlapping_months(start, end))
    team_target = _target_for_months(MonthlyTarget, months) if can_view_team else 0
    employee_stats = []
    for employee in employees:
        employee_leads = leads.filter(assigned_to=employee)
        sold_leads = employee_leads.filter(sold=True)
        values = finances_by_employee[employee.pk]
        target = _target_for_months(
            UserMonthlyTarget, months, user=employee
        )
        employee_stats.append({
            "employee": employee,
            "modified_leads": employee_leads.count(),
            "sold": sold_leads.count(),
            "sales": values["sales"],
            "profit": values["profit"],
            "revenue": values["revenue"],
            "target": target,
            "target_progress": (values["profit"] / target * 100) if target else 0,
            "sent_offers": Offer.objects.filter(
                created_by=employee,
                created_at__range=(start_dt, end_dt),
                sent=True,
            ).count(),
            "sold_offers": Offer.objects.filter(
                created_by=employee,
                sold_at__range=(start_dt, end_dt),
                sold=True,
            ).count(),
        })

    if not can_view_team:
        team_target = employee_stats[0]["target"] if employee_stats else 0

    lead_statuses = [
        ("Sold", leads.filter(sold=True).count()),
        ("Lost", leads.filter(lost=True).count()),
        ("Unqualified", leads.filter(status="done").count()),
        ("Active", leads.filter(sold=False, lost=False).exclude(status="done").count()),
    ]
    destinations = list(
        leads.exclude(destination="")
        .values_list("destination", flat=True)
    )
    destination_counts = defaultdict(int)
    for destination in destinations:
        destination_counts[destination] += 1
    top_destinations = sorted(
        destination_counts.items(), key=lambda item: item[1], reverse=True
    )[:8]

    day_count = (end - start).days + 1
    days = [start + timedelta(days=i) for i in range(day_count)]
    target_progress = (total_profit / team_target * 100) if team_target else 0
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "can_view_team": can_view_team,
        "period_label": f"{start:%d %b %Y} – {end:%d %b %Y}",
        "modified_leads": leads.count(),
        "sold_orders": orders.count(),
        "achieved_profit": total_profit,
        "period_revenue": total_revenue,
        "monthly_target": team_target,
        "progress_percentage": target_progress,
        "progress_display": min(max(target_progress, 0), 100),
        "employee_stats": employee_stats,
        "chart_data": {
            "trend_labels": [day.strftime("%d %b") for day in days],
            "profit": [round(daily_profit[day], 2) for day in days],
            "revenue": [round(daily_revenue[day], 2) for day in days],
            "status_labels": [label for label, _ in lead_statuses],
            "status_values": [value for _, value in lead_statuses],
            "employee_labels": [
                stat["employee"].get_full_name() or stat["employee"].username
                for stat in employee_stats
            ],
            "employee_profit": [round(stat["profit"], 2) for stat in employee_stats],
            "employee_target": [stat["target"] for stat in employee_stats],
            "destination_labels": [label for label, _ in top_destinations],
            "destination_values": [value for _, value in top_destinations],
        },
    }
