from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from datetime import datetime, timedelta, date
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.views import generic
from django.urls import reverse
from django.utils.safestring import mark_safe
import calendar
from django.db.models import Count, Q
from .models import Event
from .utils import Calendar
from .forms import EventForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from tasks.models import Task, LeadTask, Payment, Service
from tasks.constants import get_supplier_choices
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


def _build_modern_pdf(title, headers, rows, filename):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), leftMargin=28, rightMargin=28, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=19,
        textColor=colors.HexColor("#102a43"),
        spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        "ReportSub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#627d98"),
        spaceAfter=12,
    )

    data = [headers] + rows
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fbff")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#bcccdc")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
            ]
        )
    )

    story = [
        Paragraph(title, title_style),
        Paragraph(timezone.now().strftime("Generated on %Y-%m-%d %H:%M"), subtitle_style),
        table,
        Spacer(1, 8),
    ]
    doc.build(story)
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
        event_type = self.request.GET.get('event_type', None)

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

        # Filter by event_type if selected
        if event_type:
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
    """Calendar list: supplier payments from Service model (unpaid services). Default: unpaid upcoming. Columns: Supplier, Service, lead name, amount, due time, Order ID."""
    user = request.user
    today = timezone.now().date()

    if user.is_staff:
        services = Service.objects.filter(
            due_time__isnull=False
        ).select_related('leadtask', 'leadtask__lead').order_by('due_time')
    else:
        services = Service.objects.filter(
            leadtask__assigned_to=user,
            due_time__isnull=False
        ).select_related('leadtask', 'leadtask__lead').order_by('due_time')

    month_str = request.GET.get('month', '').strip()
    date_str = request.GET.get('date', '').strip()
    paid_filter = request.GET.get('paid', '').strip()  # 'paid' | 'unpaid' | ''
    late_filter = request.GET.get('late', '') == 'on'
    supplier_filter = request.GET.get('supplier', '').strip()  # case-insensitive match
    show_cancelled = request.GET.get('show_cancelled', '') == 'on'

    # Hide cancelled orders by default.
    if not show_cancelled:
        services = services.exclude(leadtask__status='cancelled')

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
    else:
        # Default: unpaid upcoming (from today on)
        if not late_filter:
            services = services.filter(due_time__date__gte=today)
            if paid_filter != 'paid':
                services = services.filter(is_checked=False)

    if paid_filter == 'paid':
        services = services.filter(is_checked=True)
    elif paid_filter == 'unpaid':
        services = services.filter(is_checked=False)

    if late_filter:
        services = services.filter(is_checked=False, due_time__date__lt=today)

    if supplier_filter:
        services = services.filter(supplier__iexact=supplier_filter)

    supplier_choices = get_supplier_choices()
    # Supplier filter dropdown from admin-managed suppliers
    return render(request, 'supplier_payments_list.html', {
        'services': services,
        'month': month_str,
        'date_filter': date_str,
        'paid_filter': paid_filter,
        'late_filter': late_filter,
        'supplier_filter': supplier_filter,
        'supplier_filter_options': supplier_choices,
        'supplier_choices': supplier_choices,
        'show_cancelled': show_cancelled,
    })


@login_required(login_url="/login/")
def supplier_payments_pdf(request):
    user = request.user
    today = timezone.now().date()
    if user.is_staff:
        services = Service.objects.filter(due_time__isnull=False).select_related("leadtask", "leadtask__lead").order_by("due_time")
    else:
        services = Service.objects.filter(leadtask__assigned_to=user, due_time__isnull=False).select_related("leadtask", "leadtask__lead").order_by("due_time")

    month_str = request.GET.get("month", "").strip()
    date_str = request.GET.get("date", "").strip()
    paid_filter = request.GET.get("paid", "").strip()
    late_filter = request.GET.get("late", "") == "on"
    supplier_filter = request.GET.get("supplier", "").strip()
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
    else:
        if not late_filter:
            services = services.filter(due_time__date__gte=today)
            if paid_filter != "paid":
                services = services.filter(is_checked=False)
    if paid_filter == "paid":
        services = services.filter(is_checked=True)
    elif paid_filter == "unpaid":
        services = services.filter(is_checked=False)
    if late_filter:
        services = services.filter(is_checked=False, due_time__date__lt=today)
    if supplier_filter:
        services = services.filter(supplier__iexact=supplier_filter)

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
        "Supplier Payments Report",
        ["Supplier", "Service", "Lead name", "Amount", "Due time", "Order ID", "Paid", "Order status"],
        rows,
        "supplier-payments-report.pdf",
    )


@login_required(login_url="/login/")
def client_payments_list(request):
    """Calendar list: client payments (Payment model). Default: unpaid from today on. Filter: late = unpaid in the past."""
    user = request.user
    today = timezone.now().date()

    if user.is_staff:
        payments = Payment.objects.all().select_related('leadtask', 'leadtask__lead').order_by('date')
    else:
        payments = Payment.objects.filter(leadtask__assigned_to=user).select_related('leadtask', 'leadtask__lead').order_by('date')

    month_str = request.GET.get('month', '').strip()
    date_str = request.GET.get('date', '').strip()
    paid_filter = request.GET.get('paid', '').strip()  # 'paid' | 'unpaid' | ''
    late_filter = request.GET.get('late', '') == 'on'   # unpaid from past dates
    show_cancelled = request.GET.get('show_cancelled', '') == 'on'

    # Hide cancelled orders by default.
    if not show_cancelled:
        payments = payments.exclude(leadtask__status='cancelled')

    if date_str:
        try:
            filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            payments = payments.filter(
                date__year=filter_date.year,
                date__month=filter_date.month,
                date__day=filter_date.day,
            )
        except ValueError:
            pass
    elif month_str:
        try:
            year, month = (int(x) for x in month_str.split('-'))
            payments = payments.filter(date__year=year, date__month=month)
        except (ValueError, TypeError):
            pass
    else:
        # Default: unpaid from current date onwards (do not show past payments)
        if not late_filter:
            payments = payments.filter(date__date__gte=today)
            if paid_filter != 'paid':
                payments = payments.filter(is_checked=False)

    if paid_filter == 'paid':
        payments = payments.filter(is_checked=True)
    elif paid_filter == 'unpaid':
        payments = payments.filter(is_checked=False)

    if late_filter:
        payments = payments.filter(is_checked=False, date__date__lt=today)

    return render(request, 'client_payments_list.html', {
        'payments': payments,
        'month': month_str,
        'date_filter': date_str,
        'paid_filter': paid_filter,
        'late_filter': late_filter,
        'show_cancelled': show_cancelled,
    })


@login_required(login_url="/login/")
def client_payments_pdf(request):
    user = request.user
    today = timezone.now().date()
    if user.is_staff:
        payments = Payment.objects.all().select_related("leadtask", "leadtask__lead").order_by("date")
    else:
        payments = Payment.objects.filter(leadtask__assigned_to=user).select_related("leadtask", "leadtask__lead").order_by("date")

    month_str = request.GET.get("month", "").strip()
    date_str = request.GET.get("date", "").strip()
    paid_filter = request.GET.get("paid", "").strip()
    late_filter = request.GET.get("late", "") == "on"
    show_cancelled = request.GET.get("show_cancelled", "") == "on"

    if not show_cancelled:
        payments = payments.exclude(leadtask__status="cancelled")
    if date_str:
        try:
            filter_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            payments = payments.filter(date__year=filter_date.year, date__month=filter_date.month, date__day=filter_date.day)
        except ValueError:
            pass
    elif month_str:
        try:
            year, month = (int(x) for x in month_str.split("-"))
            payments = payments.filter(date__year=year, date__month=month)
        except (ValueError, TypeError):
            pass
    else:
        if not late_filter:
            payments = payments.filter(date__date__gte=today)
            if paid_filter != "paid":
                payments = payments.filter(is_checked=False)
    if paid_filter == "paid":
        payments = payments.filter(is_checked=True)
    elif paid_filter == "unpaid":
        payments = payments.filter(is_checked=False)
    if late_filter:
        payments = payments.filter(is_checked=False, date__date__lt=today)

    rows = [
        [
            p.date.strftime("%Y-%m-%d"),
            p.leadtask.lead.name,
            str(p.amount),
            str(p.leadtask_id),
            "Yes" if p.is_checked else "No",
            p.leadtask.status,
        ]
        for p in payments
    ]
    return _build_modern_pdf(
        "Client Payments Report",
        ["Date", "Client", "Amount", "Order ID", "Paid", "Order status"],
        rows,
        "client-payments-report.pdf",
    )