from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from datetime import datetime, timedelta, date
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.views import generic
from django.urls import reverse
from django.utils.safestring import mark_safe
import calendar
from django.db.models import Count, Q, Sum
from .models import Event
from .utils import Calendar
from .forms import EventForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from tasks.models import Task, LeadTask, Payment, Service
from tasks.constants import get_supplier_choices, get_service_choices
from tasks.datetime_safety import purchases_services_queryset
from display.models import Lead
from django.utils import timezone
from tasks.forms import TaskForm, LeadTaskForm
from display.forms import LeadForm
from collections import Counter
from django.shortcuts import redirect
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


def _build_modern_pdf(title, headers, rows, filename, applied_filters=None):
    from tasks.pdf_template import build_report_pdf

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    build_report_pdf(
        response=response,
        doc_title=title,
        applied_filters=applied_filters,
        headers=headers,
        rows=rows,
    )
    return response


def index(request):
    return render(request, 'dashboard.html')


class CalendarView(LoginRequiredMixin, generic.ListView):
    model = Event
    template_name = 'calendar.html'
    login_url = '/login/'  # Redirect to login if not authenticated

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        d = get_date(self.request.GET.get('month', None))
        user = self.request.user
        # Default: travelling clients only; use event_type=all for everything
        event_type = self.request.GET.get('event_type', 'user')

        # Check if user wants to see done events
        show_done = self.request.GET.get('show_done')  # 'on' or None

        # Staff vs. non-staff logic
        if user.is_staff:
            events = Event.objects.filter(
                when__year=d.year,
                when__month=d.month
            ).exclude(
                Q(event_type='invoice') & ~Q(user=user)
            )
        else:
            events = Event.objects.filter(
                user=user,
                when__year=d.year,
                when__month=d.month
            )

        if event_type and event_type != 'all':
            events = events.filter(event_type=event_type)

        # Exclude done events unless "show_done=on"
        if show_done != 'on':
            events = events.filter(done=False)

        # Generate the calendar
        cal = Calendar(d.year, d.month)
        html_cal = cal.formatmonth(withyear=True, events=events)

        # Status counts
        lead_counts = Lead.objects.filter(assigned_to=user).values('status').annotate(total=Count('status'))
        task_counts = Task.objects.filter(assigned_to=user).values('status').annotate(total=Count('status'))
        lead_task_counts = LeadTask.objects.filter(assigned_to=user).values('status').annotate(total=Count('status'))

        context.update({
            'calendar': mark_safe(html_cal),
            'prev_month': prev_month(d),
            'next_month': next_month(d),
            'event_type': event_type,
            'type_choices': Event.TYPE_CHOICES,
            'filter_type_choices': [
                (v, n) for v, n in Event.TYPE_CHOICES if v != 'user'
            ],
            'lead_counts': {item['status']: item['total'] for item in lead_counts},
            'task_counts': {item['status']: item['total'] for item in task_counts},
            'lead_task_counts': {item['status']: item['total'] for item in lead_task_counts},
            'show_done': show_done,  # pass this so checkbox stays checked if set
        })
        return context


def get_date(req_month):
    if req_month:
        year, month = (int(x) for x in req_month.split('-'))
        return date(year, month, 1)
    return datetime.today()


def prev_month(d):
    first = d.replace(day=1)
    prev_month = first - timedelta(days=1)
    month = 'month=' + str(prev_month.year) + '-' + str(prev_month.month)
    return month


def next_month(d):
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    last = d.replace(day=days_in_month)
    next_month = last + timedelta(days=1)
    month = 'month=' + str(next_month.year) + '-' + str(next_month.month)
    return month

@login_required(login_url="/login/")
def event(request, event_id=None):
    instance = Event()
    if event_id:
        instance = get_object_or_404(Event, pk=event_id)
    else:
        instance = Event()

    form = EventForm(request.POST or None, instance=instance)
    if request.POST and form.is_valid():
        event = form.save(commit=False)
        event.user = request.user
        event.save()

        # Check if the event type is 'anniversary' to create recurring events
        if event.event_type == 'anniversary':
            create_recurring_anniversary_events(event)

        return HttpResponseRedirect(reverse('calendar'))
    return render(request, 'event.html', {'form': form})


@login_required
def mark_event_done(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    # Always mark as done, even on GET:
    event.done = True
    event.save()
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('calendar')





def create_recurring_anniversary_events(event):
    """
    Creates the same event for the same month and day for the next 50 years.
    """
    current_year = event.when.year
    month = event.when.month
    day = event.when.day

    for year in range(current_year + 1, current_year + 51):
        try:
            # Handle leap years (e.g., Feb 29)
            event_date = date(year, month, day)
        except ValueError:
            # If Feb 29 doesn't exist in the year, skip creating the event
            continue

        Event.objects.create(
            event_type=event.event_type,
            user=event.user,
            title=event.title,
            description=event.description,
            when=event_date
        )
    
@login_required(login_url="/login/")
def dashboard_view(request):
    user = request.user
    lead_counts = Lead.objects.filter(assigned_to=user).values('status').annotate(total=Count('status'))
    task_counts = Task.objects.filter(assigned_to=user).values('status').annotate(total=Count('status'))
    lead_task_counts = LeadTask.objects.filter(assigned_to=user).values('status').annotate(total=Count('status'))

    context = {
        'lead_counts': {item['status']: item['total'] for item in lead_counts},
        'task_counts': {item['status']: item['total'] for item in task_counts},
        'lead_task_counts': {item['status']: item['total'] for item in lead_task_counts},
    }
    return render(request, 'calendar.html', context)


def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        event.delete()
        return redirect('calendar')
    else:
        # Perform a redirect to calendar or other view if GET request
        return redirect('calendar')


@login_required(login_url="/login/")
def supplier_payments_list(request):
    """Purchases list: supplier services to issue. Default shows all unissued including overdue."""
    user = request.user
    now = timezone.now()
    today = now.date()

    if user.is_staff:
        services = Service.objects.filter(due_time__isnull=False)
    else:
        services = Service.objects.filter(
            leadtask__assigned_to=user,
            due_time__isnull=False,
        )

    services = purchases_services_queryset(services).order_by('due_time')

    month_str = request.GET.get('month', '').strip()
    date_str = request.GET.get('date', '').strip()
    issued_filter = request.GET.get('issued', request.GET.get('paid', '')).strip()
    overdue_filter = request.GET.get('overdue', '') == 'on' or request.GET.get('late', '') == 'on'
    supplier_filter = request.GET.get('supplier', '').strip()
    service_filter = request.GET.get('service', '').strip()
    show_cancelled = request.GET.get('show_cancelled', '') == 'on'

    base_qs = services
    if not show_cancelled:
        services = services.exclude(leadtask__status='cancelled')

    overdue_q = dict(is_checked=False, due_time__lt=now)
    overdue_count = base_qs.filter(**overdue_q).count()
    if not show_cancelled:
        overdue_count = base_qs.exclude(leadtask__status='cancelled').filter(**overdue_q).count()

    issued_count = base_qs.filter(is_checked=True).count()
    if not show_cancelled:
        issued_count = base_qs.exclude(leadtask__status='cancelled').filter(is_checked=True).count()

    if date_str:
        try:
            filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            services = services.filter(due_time__date=filter_date)
        except ValueError:
            pass
    elif month_str:
        try:
            year, month = (int(x) for x in month_str.split('-'))
            services = services.filter(due_time__year=year, due_time__month=month)
        except (ValueError, TypeError):
            pass
    elif overdue_filter:
        services = services.filter(is_checked=False, due_time__lt=now)
    elif not issued_filter:
        services = services.filter(is_checked=False)

    if issued_filter == 'issued':
        services = services.filter(is_checked=True)
    elif issued_filter == 'unissued':
        services = services.filter(is_checked=False)

    if supplier_filter:
        services = services.filter(supplier__iexact=supplier_filter)
    if service_filter:
        services = services.filter(service_name__iexact=service_filter)

    supplier_choices = get_supplier_choices()
    service_choices = get_service_choices()
    return render(request, 'supplier_payments_list.html', {
        'services': services,
        'month': month_str,
        'date_filter': date_str,
        'issued_filter': issued_filter,
        'overdue_filter': overdue_filter,
        'overdue_count': overdue_count,
        'issued_count': issued_count,
        'supplier_filter': supplier_filter,
        'service_filter': service_filter,
        'supplier_filter_options': supplier_choices,
        'service_filter_options': service_choices,
        'supplier_choices': supplier_choices,
        'show_cancelled': show_cancelled,
        'today': today,
        'now': now,
    })


@login_required(login_url="/login/")
def supplier_payments_pdf(request):
    user = request.user
    now = timezone.now()
    today = now.date()
    if user.is_staff:
        services = Service.objects.filter(due_time__isnull=False)
    else:
        services = Service.objects.filter(leadtask__assigned_to=user, due_time__isnull=False)
    services = purchases_services_queryset(services).order_by("due_time")

    month_str = request.GET.get("month", "").strip()
    date_str = request.GET.get("date", "").strip()
    paid_filter = request.GET.get("paid", request.GET.get("issued", "")).strip()
    late_filter = request.GET.get("late", "") == "on" or request.GET.get("overdue", "") == "on"
    supplier_filter = request.GET.get("supplier", "").strip()
    service_filter = request.GET.get("service", "").strip()
    show_cancelled = request.GET.get("show_cancelled", "") == "on"

    if not show_cancelled:
        services = services.exclude(leadtask__status="cancelled")
    if date_str:
        try:
            filter_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            services = services.filter(due_time__date=filter_date)
        except ValueError:
            pass
    elif month_str:
        try:
            year, month = (int(x) for x in month_str.split("-"))
            services = services.filter(due_time__year=year, due_time__month=month)
        except (ValueError, TypeError):
            pass
    elif late_filter:
        services = services.filter(is_checked=False, due_time__lt=now)
    elif not paid_filter:
        services = services.filter(is_checked=False)
    if paid_filter == "paid":
        services = services.filter(is_checked=True)
    elif paid_filter == "unpaid":
        services = services.filter(is_checked=False)
    elif paid_filter == "issued":
        services = services.filter(is_checked=True)
    elif paid_filter == "unissued":
        services = services.filter(is_checked=False)
    if supplier_filter:
        services = services.filter(supplier__iexact=supplier_filter)
    if service_filter:
        services = services.filter(service_name__iexact=service_filter)

    from tasks.pdf_template import purchases_applied_filters
    applied_filters = purchases_applied_filters(request.GET)

    rows = [
        [
            s.supplier or "—",
            s.service_name or "—",
            s.leadtask.lead.name,
            s.net or "—",
            s.due_time.strftime("%Y-%m-%d %H:%M") if s.due_time else "—",
            str(s.leadtask_id),
            "Yes" if s.is_checked else "No",
            s.leadtask.status,
        ]
        for s in services
    ]
    return _build_modern_pdf(
        "Purchases Report",
        ["Supplier", "Service", "Lead name", "Amount", "Due time", "Order ID", "Issued", "Order status"],
        rows,
        "supplier-payments-report.pdf",
        applied_filters=applied_filters,
    )


def _client_payments_queryset(user):
    if user.is_staff:
        return Payment.objects.all().select_related('leadtask', 'leadtask__lead').order_by('date')
    return Payment.objects.filter(leadtask__assigned_to=user).select_related('leadtask', 'leadtask__lead').order_by('date')


def _apply_cancelled_visibility(qs, show_cancelled):
    """Keep refund rows even when cancelled orders are hidden."""
    if show_cancelled:
        return qs
    return qs.exclude(leadtask__status='cancelled', is_refund=False)


def _filter_client_payments(qs, params, now):
    """Apply client-payments list filters from query params. Returns (qs, context_bits)."""
    month_str = (params.get('month') or '').strip()
    date_str = (params.get('date') or '').strip()
    issued_filter = (params.get('issued') or params.get('paid') or '').strip()
    overdue_filter = params.get('overdue') == 'on' or params.get('late') == 'on'
    refund_filter = params.get('refund') == 'on'
    show_cancelled = params.get('show_cancelled') == 'on'

    base_qs = qs
    qs = _apply_cancelled_visibility(qs, show_cancelled)

    overdue_count = base_qs.filter(is_checked=False, is_refund=False, date__lt=now)
    if not show_cancelled:
        overdue_count = overdue_count.exclude(leadtask__status='cancelled', is_refund=False)
    overdue_count = overdue_count.count()

    refund_count = base_qs.filter(is_refund=True).count()

    if refund_filter:
        qs = qs.filter(is_refund=True)
    elif overdue_filter:
        qs = qs.filter(is_checked=False, is_refund=False, date__lt=now)
    elif not date_str and not month_str and not issued_filter:
        qs = qs.filter(Q(is_checked=False) | Q(is_refund=True))

    if date_str:
        try:
            filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            qs = qs.filter(
                date__year=filter_date.year,
                date__month=filter_date.month,
                date__day=filter_date.day,
            )
        except ValueError:
            pass
    elif month_str:
        try:
            year, month = (int(x) for x in month_str.split('-'))
            qs = qs.filter(date__year=year, date__month=month)
        except (ValueError, TypeError):
            pass

    if issued_filter in ('issued', 'paid'):
        qs = qs.filter(is_checked=True)
    elif issued_filter in ('unissued', 'unpaid'):
        qs = qs.filter(is_checked=False)

    return qs, {
        'month': month_str,
        'date_filter': date_str,
        'issued_filter': issued_filter,
        'overdue_filter': overdue_filter,
        'overdue_count': overdue_count,
        'refund_filter': refund_filter,
        'refund_count': refund_count,
        'show_cancelled': show_cancelled,
    }


@login_required(login_url="/login/")
def client_payments_list(request):
    """Client payments schedule. Default: unissued + refunds (including overdue)."""
    now = timezone.now()
    payments, ctx = _filter_client_payments(_client_payments_queryset(request.user), request.GET, now)

    refund_stats = None
    if ctx['refund_filter']:
        agg = payments.aggregate(total=Sum('amount'))
        refund_stats = {
            'count': payments.count(),
            'total_amount': agg['total'] or 0,
            'pending': payments.filter(is_checked=False).count(),
            'received': payments.filter(is_checked=True).count(),
        }

    return render(request, 'client_payments_list.html', {
        'payments': payments,
        'refund_stats': refund_stats,
        'today': now.date(),
        'now': now,
        **ctx,
    })


@login_required(login_url="/login/")
def client_payments_pdf(request):
    now = timezone.now()
    payments, _ctx = _filter_client_payments(_client_payments_queryset(request.user), request.GET, now)

    from tasks.pdf_template import client_payments_applied_filters
    applied_filters = client_payments_applied_filters(request.GET)

    rows = [
        [
            p.date.strftime("%Y-%m-%d"),
            p.leadtask.lead.name,
            str(p.amount),
            "Refund" if p.is_refund else "Payment",
            str(p.leadtask_id),
            "Yes" if p.is_checked else "No",
            p.leadtask.status,
        ]
        for p in payments
    ]
    title = "Refunds Report" if _ctx.get('refund_filter') else "Client Payments Report"
    return _build_modern_pdf(
        title,
        ["Date", "Client", "Amount", "Type", "Order ID", "Received", "Order status"],
        rows,
        "client-payments-report.pdf",
        applied_filters=applied_filters,
    )