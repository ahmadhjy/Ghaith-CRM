"""Business intelligence / Overview dashboard for staff."""
import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from display.models import Lead
from tasks.constants import effective_service_net, parse_money
from tasks.models import LeadTask, Payment, Service


def staff_required(user):
    return user.is_staff or user.is_superuser


@login_required(login_url='/login/')
@user_passes_test(staff_required)
def overview_dashboard(request):
    today = timezone.localdate()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    preset = request.GET.get('preset', 'ytd').strip()

    if preset == 'ytd' and not date_from:
        date_from = f'{today.year}-01-01'
        date_to = f'{today.year}-12-31'
    elif preset == 'month' and not date_from:
        date_from = today.replace(day=1).isoformat()
        date_to = today.isoformat()
    elif preset == 'last30' and not date_from:
        date_from = (today - timedelta(days=30)).isoformat()
        date_to = today.isoformat()

    try:
        d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None
        d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None
    except ValueError:
        d_from, d_to = today.replace(day=1), today
        date_from, date_to = d_from.isoformat(), d_to.isoformat()

    leads_qs = Lead.objects.all()
    orders_qs = LeadTask.objects.select_related('lead', 'assigned_to')
    services_qs = Service.objects.select_related('leadtask', 'leadtask__lead')
    payments_qs = Payment.objects.select_related('leadtask', 'leadtask__lead')

    if d_from:
        leads_qs = leads_qs.filter(created_at__date__gte=d_from)
        orders_qs = orders_qs.filter(lead__created_at__date__gte=d_from)
    if d_to:
        leads_qs = leads_qs.filter(created_at__date__lte=d_to)
        orders_qs = orders_qs.filter(lead__created_at__date__lte=d_to)

    sold_leads = leads_qs.filter(sold=True)
    revenue = sum(parse_money(l.selling_price) for l in sold_leads)
    cost = sum(parse_money(l.net) for l in sold_leads)
    gross_profit = revenue - cost

    active_leads = leads_qs.exclude(status='done').count()
    takeover_count = Lead.objects.filter(takeover=True).count()
    orders_active = orders_qs.exclude(status__in=['done', 'cancelled']).count()
    orders_cancelled = orders_qs.filter(status='cancelled').count()

    overdue_receivables = Payment.objects.filter(
        is_checked=False, is_refund=False, date__date__lt=today,
    ).exclude(leadtask__status='cancelled').count()
    overdue_payables = Service.objects.filter(
        is_checked=False, due_time__date__lt=today,
    ).exclude(leadtask__status='cancelled').count()

    refund_total = sum(
        p.amount for p in Payment.objects.filter(is_refund=True)
    )

    # Sales by month (last 6 months)
    six_months_ago = today - timedelta(days=180)
    monthly_sales = defaultdict(float)
    for lead in Lead.objects.filter(sold=True, created_at__date__gte=six_months_ago):
        key = lead.created_at.strftime('%b %Y')
        monthly_sales[key] += parse_money(lead.selling_price)
    sales_chart_labels = list(monthly_sales.keys())[-6:]
    sales_chart_values = [monthly_sales[k] for k in sales_chart_labels]

    # Salesman performance
    salesman_stats = []
    for user in User.objects.filter(is_active=True, is_sales=True).order_by('username'):
        user_leads = sold_leads.filter(assigned_to=user)
        sales = sum(parse_money(l.selling_price) for l in user_leads)
        user_cost = sum(parse_money(l.net) for l in user_leads)
        salesman_stats.append({
            'user': user,
            'sales': sales,
            'cost': user_cost,
            'profit': sales - user_cost,
        })
    salesman_stats.sort(key=lambda x: x['sales'], reverse=True)

    # Top destinations
    dest_counts = (
        leads_qs.exclude(destination='')
        .values('destination')
        .annotate(c=Count('id'))
        .order_by('-c')[:8]
    )

    # Top supplier balances (unissued)
    supplier_balances = defaultdict(float)
    for svc in Service.objects.filter(is_checked=False).exclude(leadtask__status='cancelled'):
        supplier_balances[svc.supplier or 'Unknown'] += parse_money(effective_service_net(svc))
    top_suppliers = sorted(supplier_balances.items(), key=lambda x: x[1], reverse=True)[:8]

    # Lead status breakdown
    status_counts = dict(
        leads_qs.values('status').annotate(c=Count('id')).values_list('status', 'c')
    )

    # Travellers upcoming (30 days)
    upcoming_travel = LeadTask.objects.filter(
        travel_date__date__gte=today,
        travel_date__date__lte=today + timedelta(days=30),
    ).exclude(status='cancelled').count()

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'preset': preset,
        'revenue': revenue,
        'gross_profit': gross_profit,
        'net_profit': gross_profit,
        'cost': cost,
        'active_leads': active_leads,
        'takeover_count': takeover_count,
        'orders_active': orders_active,
        'orders_cancelled': orders_cancelled,
        'overdue_receivables': overdue_receivables,
        'overdue_payables': overdue_payables,
        'refund_total': refund_total,
        'sales_chart_labels': json.dumps(sales_chart_labels),
        'sales_chart_values': json.dumps(sales_chart_values),
        'salesman_stats': salesman_stats,
        'dest_counts': dest_counts,
        'top_suppliers': top_suppliers,
        'status_counts': status_counts,
        'upcoming_travel': upcoming_travel,
        'total_leads': leads_qs.count(),
        'sold_count': sold_leads.count(),
    }
    return render(request, 'overview.html', context)
