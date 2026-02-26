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
from tasks.constants import SUPPLIER_CHOICES
from display.models import Lead
from django.utils import timezone
from tasks.forms import TaskForm, LeadTaskForm
from display.forms import LeadForm
from collections import Counter
from django.shortcuts import redirect


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


def _supplier_matches_predefined(supplier_value):
    """Case-insensitive match against predefined supplier list."""
    if not supplier_value:
        return False
    sup = (supplier_value or '').strip()
    for choice_value, _ in SUPPLIER_CHOICES:
        if choice_value and sup.lower() == choice_value.lower():
            return True
    return False


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

    # Supplier filter dropdown: predefined list only (existing manual values not shown)
    return render(request, 'supplier_payments_list.html', {
        'services': services,
        'month': month_str,
        'date_filter': date_str,
        'paid_filter': paid_filter,
        'late_filter': late_filter,
        'supplier_filter': supplier_filter,
        'supplier_filter_options': SUPPLIER_CHOICES,
        'supplier_choices': SUPPLIER_CHOICES,
    })


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
    })