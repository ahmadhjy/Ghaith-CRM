from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import os

from .models import (
    Task, LeadTask, Attachment, Service, Payment, TaskAttachment,
    Supplier, ClientMediaUploadLink, ClientMediaFile,
)
from .forms import (
    TaskForm, LeadTaskForm, PaymentForm, AttachmentForm, ServiceForm,
    TaskAttachmentForm, SupplierForm,
)
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect
from django.forms import inlineformset_factory, formset_factory
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from django.views.decorators.http import require_POST
from collections import Counter
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from django.http import HttpResponse
from datetime import datetime  # Make sure this line is included
from dashboard.models import Event
from .constants import get_supplier_choices, get_service_choices, effective_service_net, parse_money, service_has_issue_override
from .calendar_sync import sync_payment_event, sync_service_event
from .invoice_save import save_invoice_from_post
from .datetime_safety import get_leadtask_for_edit, services_for_leadtask
from django.db.models.signals import post_save
from django.dispatch import receiver
from reportlab.lib.units import inch 
# TASK
# @ user


@login_required(login_url="/login/")
def display_current_tasks(request):
    status_choices = Task.STATUS_CHOICES
    selected_status = request.GET.get('status', '')  # Get selected status from query parameters
    search_query = request.GET.get('search', '')  # Get search query from query parameters

    # Filter by status
    tasks = Task.objects.filter(assigned_to=request.user)
    if selected_status:
        tasks = tasks.filter(status=selected_status)

    # Smart Search
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) |
            Q(details__icontains=search_query)
        )

    # Calculate counts for each status
    status_counts = dict(Counter(tasks.values_list('status', flat=True)))

    return render(request, 'display_task.html', {'data': tasks, 'status_choices': status_choices, 'selected_status': selected_status, 'status_counts': status_counts})


# display expired tasks
@login_required(login_url="/login/")
def expired_tasks(request):
    status_choices = Task.STATUS_CHOICES
    selected_status = request.GET.get('status', '')  # Get selected status from query parameters
    search_query = request.GET.get('search', '')  # Get search query from query parameters
    expired_tasks = Task.objects.filter(due_time__lt=timezone.now(), assigned_to=request.user)

    # Filter by status
    tasks = Task.objects.filter(assigned_to=request.user)
    if selected_status:
        tasks = tasks.filter(status=selected_status)

    # Smart Search
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) |
            Q(details__icontains=search_query)
        )

    # Calculate counts for each status
    status_counts = dict(Counter(tasks.values_list('status', flat=True)))

    return render(request, 'expired_tasks.html', { 'status_choices': status_choices, 'selected_status': selected_status, 'status_counts': status_counts,'expired_tasks': expired_tasks})

# display done tasks
@login_required(login_url="/login/")
def display_done_tasks(request):
    data = Task.objects.filter(assigned_to=request.user, status='done')
    return render(request, 'done_tasks.html', {'data': data})


@login_required(login_url="/login/")
def edit_task(request, pk):
    task = get_object_or_404(Task, pk=pk)  # Ensures the task exists
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, instance=task)  # Ensure you handle file uploads if your task form includes file fields
        if form.is_valid():
            form.save()
            return redirect('current tasks')  # Redirect to the list of current tasks
    else:
        form = TaskForm(instance=task)

    # Fetch attachments using the related_name from the TaskAttachment model
    # Make sure the related_name is set to something like 'task_attachments' in the TaskAttachment model
    attachments = task.task_attachments.all()  

    return render(request, 'edit_task.html', {
        'form': form,
        'task': task,
        'attachments': attachments  # Pass attachments to the template
    })


@login_required
def add_task_attachment(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        form = TaskAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.task = task
            attachment.save()
            return redirect('edit_task', pk=pk)
        else:
            # If form is not valid, render the page with the form errors
            return render(request, 'add_task_attachment.html', {'form': form, 'pk': pk})
    else:
        form = TaskAttachmentForm()
    return render(request, 'add_task_attachment.html', {'form': form, 'pk': pk})



@login_required(login_url="/login/")
def delete_task_attachment(request, attachment_id, pk):
    attachment = get_object_or_404(TaskAttachment, pk=attachment_id)
    if attachment:
        attachment.delete()
    return redirect('edit_task', pk=pk)

# create task by user
@login_required(login_url="/login")
def input_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('current tasks')
    else:
        form = TaskForm()
    return render(request, 'input_task.html', {'form': form})


# LEAD TASK : do not give access of creation to anyone
# auto create of lead task

@login_required(login_url="/login/")
def delete_service(request, pk):
    service = Service.objects.get(pk=pk)
    leadid = service.leadtask.pk
    service.delete()
    return redirect('edit_lead_tasks', leadid)



def service_form(request):
    services = Service.objects.all()
    instance = LeadTask.objects.get(pk=2)
    
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            new = form.save(commit=False)
            new.leadtask = instance
            new.save()
            return redirect('service_form')
    else:
        form = ServiceForm()
    
    return render(request, 'service_form.html', {'form': form, 'services': services})


@login_required(login_url="/login/")
def update_service(request, pk):
    """Full update of a service (all fields). Used by the Edit service form on edit leadtask page."""
    service = get_object_or_404(Service, pk=pk)
    leadtask_id = service.leadtask_id
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            saved = form.save()
            sync_service_event(saved)
        # Always redirect back; checkbox can be toggled via AJAX elsewhere
        return redirect('edit_lead_tasks', pk=leadtask_id)
    # GET: show edit form (handled by inline edit on page)
    return redirect('edit_lead_tasks', pk=leadtask_id)


@login_required(login_url="/login/")
def update_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    leadtask = payment.leadtask.pk
    if request.method == 'POST':
        payment.is_checked = request.POST.get('payment_checked', 'off') == 'on'
        payment.save()
        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('edit_lead_tasks', leadtask)
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('edit_lead_tasks', leadtask)


def delete_payment(request, pk):
    payment = Payment.objects.get(pk=pk)
    leadtask = payment.leadtask.pk
    payment.delete()
    return redirect('edit_lead_tasks', leadtask)  # Redirect to the main page

#
# def update_service(request, pk):
 #   service = Service.objects.get(pk=pk)
 #   leadid = service.leadtask
 #   form = ServiceForm(request.POST or None, instance=service)
 #   if form.is_valid():
 #       # Explicitly handle the checkbox
 #       service.is_checked = request.POST.get('is_checked', '') == 'on'
 #       service.save()
 #       return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
 #   return redirect('edit_lead_tasks', leadid)
 #

def create_event_for_service(service):
    sync_service_event(service)



@login_required(login_url="/login/")
@require_POST
def save_all_services(request, leadid):
    """Update existing services from service_<pk>_* and create new ones from service_name[], etc. So 'Submit Services' saves edits and new rows."""
    leadtask = get_object_or_404(LeadTask, pk=leadid)
    prefix = 'service_'
    # Collect existing service IDs we have in POST (from hidden or visible inputs)
    seen_ids = set()
    for key in request.POST:
        if key.startswith(prefix) and '_' in key[len(prefix):]:
            sid = key[len(prefix):].split('_')[0]
            if sid.isdigit():
                seen_ids.add(int(sid))
    for pk in seen_ids:
        try:
            service = Service.objects.get(pk=pk, leadtask=leadtask)
        except Service.DoesNotExist:
            continue
        form = ServiceForm({
            'service_name': request.POST.get('service_%s_service_name' % pk, ''),
            'supplier': request.POST.get('service_%s_supplier' % pk, ''),
            'details': request.POST.get('service_%s_details' % pk, ''),
            'net': request.POST.get('service_%s_net' % pk, ''),
            'selling': request.POST.get('service_%s_selling' % pk, ''),
            'due_time': request.POST.get('service_%s_due_time' % pk) or None,
            'voucher_id': request.POST.get('service_%s_voucher_id' % pk, ''),
            'issue_price': request.POST.get('service_%s_issue_price' % pk, ''),
            'is_checked': request.POST.get('service_%s_is_checked' % pk) == 'on',
            'send_to_client': request.POST.get('service_%s_send_to_client' % pk) == 'on',
        }, instance=service)
        if form.is_valid():
            saved = form.save()
            sync_service_event(saved)
    # New rows: service_name[], supplier[], ...
    names = request.POST.getlist('service_name[]')
    suppliers = request.POST.getlist('supplier[]')
    details = request.POST.getlist('details[]')
    nets = request.POST.getlist('net[]')
    sellings = request.POST.getlist('selling[]')
    due_times = request.POST.getlist('due_time[]')
    voucher_ids = request.POST.getlist('voucher_id[]')
    send_to_clients = request.POST.getlist('send_to_client[]')
    new_services = []
    for i in range(len(names)):
        form = ServiceForm({
            'service_name': names[i] if i < len(names) else '',
            'supplier': suppliers[i] if i < len(suppliers) else '',
            'details': details[i] if i < len(details) else '',
            'net': nets[i] if i < len(nets) else '',
            'selling': sellings[i] if i < len(sellings) else '',
            'due_time': due_times[i] if i < len(due_times) else None,
            'voucher_id': voucher_ids[i] if i < len(voucher_ids) else '',
            'send_to_client': (send_to_clients[i] if i < len(send_to_clients) else '') == 'on',
        })
        if form.is_valid():
            service = form.save(commit=False)
            service.leadtask = leadtask
            new_services.append(service)
    if new_services:
        Service.objects.bulk_create(new_services)
        for service in new_services:
            create_event_for_service(service)
    return redirect('edit_lead_tasks', leadid)


@require_POST
def add_multiple_services(request, leadid):
    leadtask = get_object_or_404(LeadTask, pk=leadid)
    services_data = zip(
        request.POST.getlist('service_name[]'),
        request.POST.getlist('supplier[]'),
        request.POST.getlist('details[]'),
        request.POST.getlist('net[]'),
        request.POST.getlist('selling[]'),
        request.POST.getlist('due_time[]'),
        request.POST.getlist('voucher_id[]')
    )

    services = []
    for data in services_data:
        form = ServiceForm({
            'leadtask': leadid,
            'service_name': data[0],
            'supplier': data[1],
            'details': data[2],
            'net': data[3],
            'selling': data[4],
            'due_time': data[5],
            'voucher_id': data[6],
        })
        if form.is_valid():
            service = form.save(commit=False)
            service.leadtask = leadtask
            services.append(service)

    Service.objects.bulk_create(services)
    for service in services:
        create_event_for_service(service)  # Manually trigger what the signal would do

    return redirect('edit_lead_tasks', leadid)

@require_POST
def update_checked_status(request, service_id):
    service = Service.objects.get(pk=service_id)
    service.is_checked = request.POST.get('is_checked', 'off') == 'on'
    service.save()
    return JsonResponse({'status': 'success'}, status=200)


@login_required(login_url="/login/")
@require_POST
def update_send_to_client(request, service_id):
    service = get_object_or_404(Service, pk=service_id)
    service.send_to_client = request.POST.get('send_to_client', 'off') == 'on'
    service.save()
    return JsonResponse({'status': 'success'}, status=200)


@login_required(login_url="/login/")
@require_POST
def create_supplier(request):
    form = SupplierForm(request.POST)
    if form.is_valid():
        supplier = form.save()
        return JsonResponse({
            'status': 'success',
            'name': supplier.name,
            'is_active': supplier.is_active,
        })
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

# views.py
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import Service


@login_required(login_url="/login/")
def purchased_services(request):
    """Legacy URL — issued services live on the Purchases page."""
    params = {}
    legacy = request.GET.get('filter', '').strip()
    if legacy == 'unpaid':
        params['issued'] = 'unissued'
    elif legacy == 'overdue':
        params['overdue'] = 'on'
    elif legacy in ('paid', 'processed', 'unprocessed'):
        params['issued'] = 'issued'
    else:
        params['issued'] = 'issued'
    if request.GET.get('show_cancelled') == 'on':
        params['show_cancelled'] = 'on'
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    return redirect(f"{reverse('supplier_payments_list')}?{query}")


@login_required
@require_POST
def mark_service_processed(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service.processed = True
    service.save()
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('supplier_payments_list')


@login_required
@require_POST
def service_mark_done(request, pk):
    """Toggle service paid status and sync linked calendar event. Redirect to next or supplier list."""
    service = get_object_or_404(Service, pk=pk)
    service.is_checked = request.POST.get('is_checked') == 'on'
    service.save()
    try:
        event = service.calendar_event
        event.done = service.is_checked
        event.save()
    except Exception:
        pass  # No linked calendar event
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('supplier_payments_list')


@login_required(login_url="/login/")
def edit_lead_task(request, pk):
    instance = get_leadtask_for_edit(pk)
    services = services_for_leadtask(instance)
    lead_task_payments = Payment.objects.filter(leadtask=instance)
    attachments = Attachment.objects.filter(parentleadtask=instance)

    if request.method == 'POST':
        updated, form = save_invoice_from_post(request, instance)
        if updated:
            return redirect('edit_lead_tasks', pk)
    else:
        form = LeadTaskForm(instance=instance)

    supplier_choices = get_supplier_choices()
    service_choices = get_service_choices()
    from display.models import get_destination_choices
    destination_choices = get_destination_choices()
    predefined_supplier_values = [v for v, _ in supplier_choices]
    predefined_service_values = [v for v, _ in service_choices]
    predefined_destination_values = [v for v, _ in destination_choices if v]
    services_total = services.count()
    services_issued = services.filter(is_checked=True).count()
    services_list = list(services)
    # Profit uses the booking net only (issue price excluded).
    total_net = sum(parse_money(s.net) for s in services_list)
    total_selling = parse_money(instance.lead.selling_price)
    total_profit = total_selling - total_net
    # Post-issue profit recalculates using issue prices when they differ from net.
    total_issue_net = sum(parse_money(effective_service_net(s)) for s in services_list)
    has_issue_mismatch = any(service_has_issue_override(s) for s in services_list)
    post_issue_profit = total_selling - total_issue_net
    media_upload_links = ClientMediaUploadLink.objects.filter(leadtask=instance)
    from accounting_bridge.services.invoices import leadtask_accounting_sync_context
    accounting_ctx = leadtask_accounting_sync_context(instance)
    return render(request, 'edit_leadtask.html', {
        'form': form,
        'leadid': pk,
        'lead': instance.lead,
        'services': services,
        'lead_task_payments': lead_task_payments,
        'attachments': attachments,
        'predefined_suppliers': supplier_choices,
        'predefined_supplier_values': predefined_supplier_values,
        'predefined_services': service_choices,
        'predefined_service_values': predefined_service_values,
        'destination_choices': destination_choices,
        'predefined_destination_values': predefined_destination_values,
        'services_total': services_total,
        'services_issued': services_issued,
        'total_net': total_net,
        'total_selling': total_selling,
        'total_profit': total_profit,
        'total_issue_net': total_issue_net,
        'has_issue_mismatch': has_issue_mismatch,
        'post_issue_profit': post_issue_profit,
        'media_upload_links': media_upload_links,
        'supplier_form': SupplierForm(),
        **accounting_ctx,
    })


@login_required(login_url="/login/")
@require_POST
def sync_leadtask_accounting(request, pk):
    from accounting_bridge.permissions import user_is_accountant
    from accounting_bridge.services.invoices import force_sync_crm_leadtask_to_accounting

    if not user_is_accountant(request.user):
        messages.error(request, 'Only main accountant users can sync invoices with accounting.')
        return redirect('edit_lead_tasks', pk)

    leadtask = get_object_or_404(LeadTask, pk=pk)
    if not leadtask.service_set.exists():
        messages.error(request, 'Add at least one service line before syncing with accounting.')
        return redirect('edit_lead_tasks', pk)

    try:
        queue = force_sync_crm_leadtask_to_accounting(leadtask)
    except Exception:
        messages.error(request, 'Could not sync this invoice with accounting. Check server logs.')
        return redirect('edit_lead_tasks', pk)

    if not queue or not queue.sales_invoice_id:
        messages.error(request, 'Accounting sync is disabled or this invoice could not be linked.')
        return redirect('edit_lead_tasks', pk)

    messages.success(
        request,
        f'Invoice synced with accounting ({queue.sales_invoice.invoice_no}). '
        'Future edits to this CRM invoice will update the accounting copy.',
    )
    return redirect('edit_lead_tasks', pk)


@login_required
@require_POST
def update_service_supplier(request, pk):
    """Update only the supplier field of a service. Redirect back to edit leadtask."""
    service = get_object_or_404(Service, pk=pk)
    supplier = (request.POST.get('supplier') or '').strip()
    service.supplier = supplier
    service.save()
    return redirect('edit_lead_tasks', pk=service.leadtask_id)




@login_required
def generate_pdf(request, pk):
    from tasks.models import Attachment
    from tasks.pdf_template import build_internal_invoice_pdf

    lead_task = get_object_or_404(
        LeadTask.objects.select_related('lead', 'assigned_to').prefetch_related('lead__passengers'),
        pk=pk,
    )
    services = Service.objects.filter(leadtask=lead_task).order_by('pk')
    payments = Payment.objects.filter(leadtask=lead_task).order_by('date')
    attachments = Attachment.objects.filter(parentleadtask=lead_task).order_by('-uploaded_at')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice - {lead_task.lead.name}.pdf"'
    return build_internal_invoice_pdf(
        response=response,
        lead_task=lead_task,
        services=services,
        payments=payments,
        attachments=attachments,
    )


@login_required
def generate_client_pdf(request, pk):
    from tasks.pdf_template import build_client_invoice_pdf
    from .datetime_safety import services_for_client_pdf

    lead_task = get_object_or_404(LeadTask, pk=pk)
    services = list(services_for_client_pdf(lead_task))
    payments = Payment.objects.filter(leadtask=lead_task).order_by('date')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Client Invoice - {lead_task.lead.name}.pdf"'
    return build_client_invoice_pdf(
        response=response,
        lead_task=lead_task,
        services=services,
        payments=payments,
    )


@login_required(login_url="/login/")
def current_leadtasks(request):
    status_choices = LeadTask.STATUS_CHOICES
    selected_status = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    travel_date_only = request.GET.get('travel_date_only', '') == 'on'
    assigned_to_me = request.GET.get('assigned_to_me', '') == 'on'

    if request.user.is_staff and not assigned_to_me:
        lead_tasks = LeadTask.objects.all()
    else:
        lead_tasks = LeadTask.objects.filter(assigned_to=request.user)

    if selected_status:
        lead_tasks = lead_tasks.filter(status=selected_status)

    if travel_date_only:
        lead_tasks = lead_tasks.filter(travel_date__isnull=False)

    if search_query:
        lead_tasks = lead_tasks.filter(
            Q(pk__icontains=search_query) |
            Q(lead__name__icontains=search_query) |
            Q(lead__passengers__name__icontains=search_query) |
            Q(lead__destination__icontains=search_query) |
            Q(lead__phone__icontains=search_query) |
            Q(notes__icontains=search_query) |
            Q(lead__finalization_notes__icontains=search_query) |
            Q(assigned_to__username__icontains=search_query)
        ).distinct()

    # Sort LeadTasks from newest to oldest
    lead_tasks = lead_tasks.select_related('lead', 'assigned_to').prefetch_related('lead__passengers').order_by('-pk')

    # Calculate counts for each status (include all tasks for counts)
    if request.user.is_staff and not assigned_to_me:
        all_lead_tasks = LeadTask.objects.all()
    else:
        all_lead_tasks = LeadTask.objects.filter(assigned_to=request.user)
    status_counts = dict(Counter(all_lead_tasks.values_list('status', flat=True)))

    return render(request, 'leadtasks.html', {
        'data': lead_tasks,
        'status_choices': status_choices,
        'selected_status': selected_status,
        'search_query': search_query,  # Pass the search query to the template
        'status_counts': status_counts,
        'travel_date_only': travel_date_only,
        'assigned_to_me': assigned_to_me,
        'is_staff': request.user.is_staff,
    })

@login_required(login_url="/login/")
def done_leadtasks(request):
    # Sort done LeadTasks from newest to oldest
    data = LeadTask.objects.filter(assigned_to=request.user, status='done').order_by('-pk')
    return render(request, 'doneleadtasks.html', {'data': data})


@login_required(login_url="/login/")
def add_payment(request, pk):
    leadtask = LeadTask.objects.get(pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.leadtask = leadtask
            payment.save()
            sync_payment_event(payment)
            return redirect("edit_lead_tasks", pk=pk)
    else:
        form = PaymentForm()
    return render(request, 'add_payment.html', {'form': form})


@login_required(login_url="/login/")
def client_payments(request):
    """Legacy URL — use calendar client payments list."""
    params = {}
    legacy = request.GET.get('filter', '').strip()
    if legacy == 'paid':
        params['issued'] = 'issued'
    elif legacy == 'unpaid':
        params['issued'] = 'unissued'
    elif legacy == 'overdue':
        params['overdue'] = 'on'
    if request.GET.get('show_cancelled') == 'on':
        params['show_cancelled'] = 'on'
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    url = reverse('client_payments_list')
    if query:
        url = f'{url}?{query}'
    return redirect(url)


@login_required(login_url="/login/")
def travellers_list(request):
    """List leadtasks with a travel date (travellers)."""
    from django.db.models import Count, Q
    from datetime import datetime as dt

    now = timezone.now()
    today = now.date() if hasattr(now, 'date') else now

    if request.user.is_staff:
        qs = LeadTask.objects.filter(travel_date__isnull=False).select_related('lead', 'assigned_to')
    else:
        qs = LeadTask.objects.filter(
            travel_date__isnull=False,
            assigned_to=request.user,
        ).select_related('lead', 'assigned_to')

    qs = qs.annotate(
        services_total=Count('service', distinct=True),
        services_issued=Count('service', filter=Q(service__is_checked=True), distinct=True),
    )

    show_cancellations = request.GET.get('show_cancellations', '') == 'on'
    if not show_cancellations:
        qs = qs.exclude(status='cancelled')

    destination = request.GET.get('destination', '').strip()
    if destination:
        qs = qs.filter(lead__destination=destination)

    month_str = request.GET.get('month', '').strip()
    if month_str:
        try:
            year, month = (int(x) for x in month_str.split('-'))
            qs = qs.filter(travel_date__year=year, travel_date__month=month)
        except (ValueError, TypeError):
            pass

    travel_from = request.GET.get('travel_from', '').strip()
    travel_to = request.GET.get('travel_to', '').strip()
    if travel_from:
        try:
            parsed = dt.strptime(travel_from, '%Y-%m-%d').date()
            qs = qs.filter(travel_date__date__gte=parsed)
        except ValueError:
            pass
    if travel_to:
        try:
            parsed = dt.strptime(travel_to, '%Y-%m-%d').date()
            qs = qs.filter(travel_date__date__lte=parsed)
        except ValueError:
            pass

    show_past = request.GET.get('show_past', '') == 'on'
    if not show_past:
        qs = qs.filter(travel_date__date__gte=today)

    return_from = request.GET.get('return_from', '').strip()
    return_to = request.GET.get('return_to', '').strip()
    if return_from:
        try:
            parsed = dt.strptime(return_from, '%Y-%m-%d').date()
            qs = qs.filter(return_date__date__gte=parsed)
        except ValueError:
            pass
    if return_to:
        try:
            parsed = dt.strptime(return_to, '%Y-%m-%d').date()
            qs = qs.filter(return_date__date__lte=parsed)
        except ValueError:
            pass

    travellers = qs.order_by('travel_date')

    from display.models import Destination
    destinations = list(Destination.objects.all().order_by('name').values_list('name', flat=True))

    return render(request, 'travellers.html', {
        'travellers': travellers,
        'now': now,
        'today': today,
        'destinations': destinations,
        'request_destination': destination,
        'request_month': month_str,
        'travel_from': travel_from,
        'travel_to': travel_to,
        'show_past': show_past,
        'return_from': return_from,
        'return_to': return_to,
        'show_cancellations': show_cancellations,
    })


@login_required(login_url="/login/")
def travellers_pdf(request):
    from datetime import datetime as dt
    from django.db.models import Count, Q
    from tasks.pdf_template import build_report_pdf, travellers_applied_filters

    now = timezone.now()
    today = now.date()

    if request.user.is_staff:
        qs = LeadTask.objects.filter(travel_date__isnull=False).select_related('lead', 'assigned_to')
    else:
        qs = LeadTask.objects.filter(
            travel_date__isnull=False,
            assigned_to=request.user,
        ).select_related('lead', 'assigned_to')

    qs = qs.annotate(
        services_total=Count('service', distinct=True),
        services_issued=Count('service', filter=Q(service__is_checked=True), distinct=True),
    )

    show_cancellations = request.GET.get('show_cancellations', '') == 'on'
    if not show_cancellations:
        qs = qs.exclude(status='cancelled')

    destination = request.GET.get('destination', '').strip()
    if destination:
        qs = qs.filter(lead__destination=destination)

    month_str = request.GET.get('month', '').strip()
    if month_str:
        try:
            year, month = (int(x) for x in month_str.split('-'))
            qs = qs.filter(travel_date__year=year, travel_date__month=month)
        except (ValueError, TypeError):
            pass

    travel_from = request.GET.get('travel_from', '').strip()
    travel_to = request.GET.get('travel_to', '').strip()
    if travel_from:
        try:
            parsed = dt.strptime(travel_from, '%Y-%m-%d').date()
            qs = qs.filter(travel_date__date__gte=parsed)
        except ValueError:
            pass
    if travel_to:
        try:
            parsed = dt.strptime(travel_to, '%Y-%m-%d').date()
            qs = qs.filter(travel_date__date__lte=parsed)
        except ValueError:
            pass

    show_past = request.GET.get('show_past', '') == 'on'
    if not show_past:
        qs = qs.filter(travel_date__date__gte=today)

    return_from = request.GET.get('return_from', '').strip()
    return_to = request.GET.get('return_to', '').strip()
    if return_from:
        try:
            parsed = dt.strptime(return_from, '%Y-%m-%d').date()
            qs = qs.filter(return_date__date__gte=parsed)
        except ValueError:
            pass
    if return_to:
        try:
            parsed = dt.strptime(return_to, '%Y-%m-%d').date()
            qs = qs.filter(return_date__date__lte=parsed)
        except ValueError:
            pass

    qs = qs.order_by('travel_date')
    applied_filters = travellers_applied_filters(request.GET)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="travellers-report.pdf"'

    rows = [
        [
            lt.lead.name,
            lt.lead.destination or '—',
            lt.travel_date.strftime('%Y-%m-%d') if lt.travel_date else '—',
            lt.return_date.strftime('%Y-%m-%d') if lt.return_date else '—',
            f'{lt.services_issued} / {lt.services_total}',
            lt.assigned_to.get_full_name() or lt.assigned_to.username,
            str(lt.pk),
        ]
        for lt in qs[:500]
    ]
    from tasks.pdf_policy import PDF_TARGET_TRAVELLERS_REPORT
    build_report_pdf(
        response=response,
        doc_title='Travellers',
        applied_filters=applied_filters,
        headers=['Client', 'Destination', 'Travel', 'Return', 'Services', 'Assigned', 'Order'],
        rows=rows,
        pdf_target=PDF_TARGET_TRAVELLERS_REPORT,
    )
    return response


@login_required
@require_POST
def mark_payment_processed(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    payment.processed = True
    payment.save()
    return redirect('client_payments_list')


# create attachment and upload
@login_required(login_url="/login/")
def add_attachment(request, pk):
    """Single-file upload (legacy): form with attachment_name + file. Redirects back to edit leadtask."""
    leadtask = get_object_or_404(LeadTask, pk=pk)
    if request.method == 'POST':
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attach = form.save(commit=False)
            attach.parentleadtask = leadtask
            attach.save()
            return redirect("edit_lead_tasks", pk=pk)
    else:
        form = AttachmentForm()
    return render(request, 'add_attachment.html', {'form': form})


@login_required(login_url="/login/")
def add_attachments_multiple(request, pk):
    """Upload multiple files at once; attachment_name = original file name. Keeps existing data unchanged."""
    leadtask = get_object_or_404(LeadTask, pk=pk)
    if request.method == 'POST':
        files = request.FILES.getlist('files')
        for f in files:
            if not f.name:
                continue
            # Use original file name; sanitize for storage if needed
            name = f.name
            if len(name) > 120:
                import os
                base, ext = os.path.splitext(name)
                name = base[: 120 - len(ext)] + ext
            Attachment.objects.create(
                parentleadtask=leadtask,
                attachment_name=name,
                file=f,
            )
        return redirect("edit_lead_tasks", pk=pk)
    return redirect("edit_lead_tasks", pk=pk)


@login_required(login_url="/login/")
def delete_attachment(request, attachment_id, pk):
    # get the attachment (and delete directly)
    attachment = get_object_or_404(Attachment, pk=attachment_id)

    if attachment:
        attachment.delete()
        return redirect('edit_lead_tasks', pk=pk)
    else:
        return redirect('edit_lead_tasks', pk=pk)


# get attachments of a specific invoice
def attachment_list(request, invoiceid):
    attachments = Attachment.objects.filter(parentleadtask=invoiceid)
    return render(request, 'attachment_list.html', {'attachments': attachments})


def _get_active_upload_link(token):
    return get_object_or_404(
        ClientMediaUploadLink,
        token=token,
        is_active=True,
    )


def _sanitize_filename(name, max_len=255):
    if len(name) <= max_len:
        return name
    base, ext = os.path.splitext(name)
    return base[: max_len - len(ext)] + ext


@login_required(login_url="/login/")
@require_POST
def create_client_media_link(request, pk):
    leadtask = get_object_or_404(LeadTask, pk=pk)
    upload_link = ClientMediaUploadLink.objects.create(
        leadtask=leadtask,
        client_name=leadtask.lead.name,
        created_by=request.user,
    )
    upload_url = request.build_absolute_uri(
        f'/tasks/client-media/{upload_link.token}/'
    )
    return JsonResponse({
        'status': 'success',
        'token': str(upload_link.token),
        'url': upload_url,
    })


def client_media_upload_page(request, token):
    upload_link = _get_active_upload_link(token)
    files = upload_link.files.all().order_by('-uploaded_at')
    return render(request, 'client_media_upload.html', {
        'upload_link': upload_link,
        'files': files,
        'is_submitted': upload_link.is_submitted,
    })


@require_POST
def client_media_upload_files(request, token):
    upload_link = _get_active_upload_link(token)
    if upload_link.is_submitted:
        return JsonResponse({'status': 'error', 'message': 'Uploads are closed.'}, status=403)

    uploaded = []
    for f in request.FILES.getlist('files'):
        if not f.name:
            continue
        media_file = ClientMediaFile.objects.create(
            upload_link=upload_link,
            file=f,
            original_name=_sanitize_filename(f.name),
        )
        uploaded.append({
            'id': media_file.pk,
            'name': media_file.original_name,
            'url': media_file.file.url,
            'is_video': media_file.original_name.lower().endswith(
                ('.mp4', '.mov', '.avi', '.webm', '.mkv')
            ),
        })

    if uploaded:
        from notifications.services import notify_media_upload_link
        notify_media_upload_link(upload_link, files_added=len(uploaded))

    return JsonResponse({'status': 'success', 'files': uploaded})


@require_POST
def client_media_delete_file(request, token, file_id):
    upload_link = _get_active_upload_link(token)
    if upload_link.is_submitted:
        return JsonResponse({'status': 'error', 'message': 'Uploads are closed.'}, status=403)

    media_file = get_object_or_404(ClientMediaFile, pk=file_id, upload_link=upload_link)
    media_file.file.delete(save=False)
    media_file.delete()
    return JsonResponse({'status': 'success'})


@require_POST
def client_media_submit(request, token):
    upload_link = _get_active_upload_link(token)
    if upload_link.is_submitted:
        return JsonResponse({'status': 'error', 'message': 'Already submitted.'}, status=400)

    if not upload_link.files.exists():
        return JsonResponse(
            {'status': 'error', 'message': 'Please upload at least one file.'},
            status=400,
        )

    upload_link.submitted_at = timezone.now()
    upload_link.save(update_fields=['submitted_at'])
    return JsonResponse({'status': 'success'})


@login_required(login_url="/login/")
def client_media_uploads_list(request):
    links = ClientMediaUploadLink.objects.select_related(
        'leadtask', 'leadtask__lead', 'created_by'
    ).prefetch_related('files')
    return render(request, 'client_media_uploads_list.html', {'links': links})


@login_required(login_url="/login/")
def client_media_upload_detail(request, token):
    upload_link = get_object_or_404(
        ClientMediaUploadLink.objects.select_related('leadtask', 'leadtask__lead'),
        token=token,
    )
    files = upload_link.files.all().order_by('-uploaded_at')
    return render(request, 'client_media_upload_detail.html', {
        'upload_link': upload_link,
        'files': files,
    })
