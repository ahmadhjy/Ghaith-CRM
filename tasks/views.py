from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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
from .constants import get_supplier_choices
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
            form.save()
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
    if not service.due_time:
        return
    client_details = (
        f"Name: {service.leadtask.lead.name}\n"
        f"Phone: {service.leadtask.lead.phone}"
    )
    description = (
        f"Service Name: {service.service_name}\n"
        f"Supplier: {service.supplier}\n"
        f"Details: {service.details}\n"
        f"Net: ${service.net}\n"
        f"Selling: ${service.selling}\n"
        f"Client Details:\n{client_details}"
    )
    when_date = service.due_time.date() if hasattr(service.due_time, 'date') else service.due_time
    Event.objects.create(
        event_type='followup',
        user=service.leadtask.assigned_to,
        title=f"{service.supplier} - Supplier Payment - {service.leadtask.lead.name} (${service.net})",
        description=description,
        when=when_date,
        service=service,
    )



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
            'is_checked': request.POST.get('service_%s_is_checked' % pk) == 'on',
            'send_to_client': request.POST.get('service_%s_send_to_client' % pk) == 'on',
        }, instance=service)
        if form.is_valid():
            form.save()
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
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from .models import Service


@login_required(login_url="/login/")
def purchased_services(request):
    if request.user.is_staff:
        services = Service.objects.all().order_by('due_time')  # staff sees all
    else:
        # If Service had an assigned_to, filter by that field. Otherwise, staff-only logic is fine.
        services = Service.objects.filter(leadtask__assigned_to=request.user).order_by('due_time')

    search_query = request.GET.get('search', '')
    filter_status = request.GET.get('filter', '')

    # Search
    if search_query:
        services = services.filter(
            Q(service_name__icontains=search_query) |
            Q(supplier__icontains=search_query) |
            Q(details__icontains=search_query)
        )

    # If a filter is provided:
    if filter_status:
        if filter_status == 'paid':
            services = services.filter(is_checked=True)
        elif filter_status == 'unpaid':
            services = services.filter(is_checked=False)
        elif filter_status == 'overdue':
            services = services.filter(due_time__lt=timezone.now(), is_checked=False)
        elif filter_status == 'processed':
            services = services.filter(processed=True)
        elif filter_status == 'unprocessed':
            services = services.filter(processed=False)
    else:
        # No filter => hide processed
        # So "All" in your dropdown means "All unprocessed"
        services = services.filter(processed=False)

    return render(request, 'purchased_services.html', {'services': services, 'now': timezone.now()})


@login_required
@require_POST
def mark_service_processed(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service.processed = True
    service.save()
    return redirect('purchased_services')


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
    instance = get_object_or_404(
        LeadTask.objects.select_related('lead').prefetch_related('lead__passengers'),
        pk=pk,
    )
    services = Service.objects.filter(leadtask=instance)
    lead_task_payments = Payment.objects.filter(leadtask=instance)
    attachments = Attachment.objects.filter(parentleadtask=instance)

    if request.method == 'POST':
        old_status = instance.status
        form = LeadTaskForm(request.POST, instance=instance)
        if form.is_valid():
            updated = form.save()
            lead = updated.lead
            lead.finalization_notes = form.cleaned_data.get('finalization_notes', '') or ''
            lead.save(update_fields=['finalization_notes'])
            if old_status != 'cancelled' and updated.status == 'cancelled':
                # Delete related supplier payment events when order is cancelled.
                Event.objects.filter(service__leadtask=updated).delete()
    else:
        form = LeadTaskForm(instance=instance)

    supplier_choices = get_supplier_choices()
    predefined_supplier_values = [v for v, _ in supplier_choices]
    media_upload_links = ClientMediaUploadLink.objects.filter(leadtask=instance)
    return render(request, 'edit_leadtask.html', {
        'form': form,
        'leadid': pk,
        'lead': instance.lead,
        'services': services,
        'lead_task_payments': lead_task_payments,
        'attachments': attachments,
        'predefined_suppliers': supplier_choices,
        'predefined_supplier_values': predefined_supplier_values,
        'media_upload_links': media_upload_links,
        'supplier_form': SupplierForm(),
    })


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
    lead_task = get_object_or_404(LeadTask, pk=pk)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice - {lead_task.lead.name}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(A4), rightMargin=28, leftMargin=28, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    custom_colors = {'blue': '#0f4c81', 'light_blue': '#f5f7fa', 'grey': '#334e68'}

    # Custom styles
    styles.add(ParagraphStyle(name='MyTitleStyle', parent=styles['Title'], fontSize=16, leading=20, alignment=TA_CENTER, textColor=colors.HexColor(custom_colors['blue'])))
    styles.add(ParagraphStyle(name='MyHeading2', parent=styles['Heading2'], fontSize=12, leading=16, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor(custom_colors['grey'])))
    styles.add(ParagraphStyle(name='MyBodyText', parent=styles['BodyText'], fontSize=9, leading=11, textColor=colors.HexColor(custom_colors['grey'])))

    story = []

    # Function to add headers and footers
    def on_every_page(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawString(inch, 0.75 * inch, f"Page {doc.page}")
        canvas.restoreState()

    doc.build_on_first_page = on_every_page
    doc.build_on_later_pages = on_every_page

    services = Service.objects.filter(leadtask=lead_task)
    payments = Payment.objects.filter(leadtask=lead_task)

    # Add logo to the top left corner
    logo_path = 'ghaithleads/static/images/logo.png'  # Update this to the actual path of your logo
    story.append(Image(logo_path, width=100, height=100))  # Adjust width and height as needed
    story.append(Spacer(1, 12))

    # Title
    story.append(Paragraph(f'Order Details for {lead_task.lead.name}', styles['MyTitleStyle']))
    story.append(Spacer(1, 12))

    # LeadTask ID
    story.append(Paragraph(f'Invoice ID: {lead_task.pk}', styles['MyBodyText']))
    story.append(Spacer(1, 12))

    # Creation date and assigned user
    today = datetime.now().strftime("%Y-%m-%d")
    created_by = lead_task.assigned_to.username
    story.append(Paragraph(f"Created By: {created_by}", styles['MyBodyText']))
    story.append(Paragraph(f"Date Created: {today}", styles['MyBodyText']))
    if lead_task.travel_date:
        travel_date = lead_task.travel_date.strftime('%Y-%m-%d')
        story.append(Paragraph(f"Exact Travel Date: {travel_date}", styles['MyBodyText']))
    story.append(Spacer(1, 12))

    # Client Details
    story.append(Paragraph('Client Details', styles['MyHeading2']))
    client_details = [
        f"Name: {lead_task.lead.name}",
        f"Phone: {lead_task.lead.phone}",
        f"Channel: {lead_task.lead.channel}",
        f"Destination: {lead_task.lead.destination}",
        f"Special Request: {lead_task.lead.special_request}",
        f"Finalization Notes: {lead_task.lead.finalization_notes}"
    ]
    for detail in client_details:
        story.append(Paragraph(detail, styles['MyBodyText']))
    story.append(Spacer(1, 12))

    # Services
    if services.exists():
        story.append(Paragraph('Services', styles['MyHeading2']))
        services_data = [['Service Name', 'Supplier', 'Details', 'Net', 'Selling', 'Due Time', 'Checked']]
        for service in services:
            services_data.append([
                service.service_name, service.supplier, service.details,
                f"${service.net}", f"${service.selling}",
                service.due_time.strftime('%Y-%m-%d') if service.due_time else 'N/A',
                'Yes' if service.is_checked else 'No'
            ])
        services_table = Table(services_data, spaceBefore=6)
        services_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(custom_colors['blue'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bcccdc')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(custom_colors['light_blue'])]),
        ]))
        story.append(services_table)
        story.append(Spacer(1, 12))

    # Payments
    if payments.exists():
        story.append(Paragraph('Payments', styles['MyHeading2']))
        payments_data = [['Date', 'Amount', 'Paid']]
        for payment in payments:
            payments_data.append([
                payment.date.strftime('%Y-%m-%d'), f"${payment.amount}",
                'Yes' if payment.is_checked else 'No'
            ])
        payments_table = Table(payments_data, spaceBefore=6)
        payments_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(custom_colors['blue'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bcccdc')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(custom_colors['light_blue'])]),
        ]))
        story.append(payments_table)
        story.append(Spacer(1, 12))
    
    # Add selling price to the payments section
    story.append(Paragraph(f"Selling Price: {lead_task.lead.selling_price}", styles['MyBodyText']))
    story.append(Spacer(1, 12))

    doc.build(story)
    return response


@login_required
def generate_client_pdf(request, pk):
    lead_task = get_object_or_404(LeadTask, pk=pk)
    services = Service.objects.filter(leadtask=lead_task, send_to_client=True)
    payments = Payment.objects.filter(leadtask=lead_task).order_by("date")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Client Invoice - {lead_task.lead.name}.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=28,
        leftMargin=28,
        topMargin=24,
        bottomMargin=24
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ClientTitleStyle',
        parent=styles['Title'],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0f4c81')
    ))
    styles.add(ParagraphStyle(
        name='ClientHeading',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor('#334e68')
    ))
    styles.add(ParagraphStyle(
        name='ClientBody',
        parent=styles['BodyText'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334e68')
    ))
    styles.add(ParagraphStyle(
        name='PolicyBody',
        parent=styles['BodyText'],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334e68')
    ))

    story = []
    logo_path = 'ghaithleads/static/images/logo.png'
    story.append(Image(logo_path, width=100, height=100))
    story.append(Spacer(1, 8))

    story.append(Paragraph(f'Invoice for {lead_task.lead.name}', styles['ClientTitleStyle']))
    story.append(Spacer(1, 10))

    created_by = lead_task.assigned_to.get_full_name() or lead_task.assigned_to.username
    issue_date = timezone.now().strftime("%Y-%m-%d")
    exact_travel_date = lead_task.travel_date.strftime('%Y-%m-%d') if lead_task.travel_date else 'N/A'

    summary_data = [
        ['Invoice ID', str(lead_task.pk)],
        ['Created By', created_by],
        ['Issue Date', issue_date],
        ['Exact Travel Date', exact_travel_date],
    ]
    summary_table = Table(summary_data, colWidths=[160, 420], hAlign='LEFT')
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f7fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#334e68')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bcccdc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph('Client Details', styles['ClientHeading']))
    client_fields = [
        ('Name', lead_task.lead.name),
        ('Phone', lead_task.lead.phone),
        ('Email', getattr(lead_task.lead, 'email', None)),
        ('Channel', lead_task.lead.channel),
        ('Destination', lead_task.lead.destination),
        ('Request Details', lead_task.lead.special_request),
        ('Invoice Notes', lead_task.notes),
        ('Return Date', lead_task.return_date.strftime('%Y-%m-%d') if lead_task.return_date else None),
        ('Date of Birth', lead_task.date_of_birth.strftime('%Y-%m-%d') if lead_task.date_of_birth else None),
        ('Passport Expiry Date', lead_task.passport_expiry_date.strftime('%Y-%m-%d') if lead_task.passport_expiry_date else None),
        ('Payment Type', lead_task.payment),
    ]
    client_data = [[label, str(value)] for label, value in client_fields if value not in [None, '']]
    if client_data:
        client_table = Table(client_data, colWidths=[180, 560], hAlign='LEFT')
        client_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f7fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#334e68')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bcccdc')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(client_table)
        story.append(Spacer(1, 10))

    story.append(Paragraph('Services', styles['ClientHeading']))
    if services.exists():
        service_data = [['#', 'Service Type', 'Service Details']]
        for idx, service in enumerate(services, 1):
            service_data.append([str(idx), service.service_name or '—', service.details or '—'])
        service_table = Table(service_data, colWidths=[40, 220, 480], hAlign='LEFT')
        service_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f4c81')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bcccdc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
        ]))
        story.append(service_table)
    else:
        story.append(Paragraph('No services added.', styles['ClientBody']))
    story.append(Spacer(1, 10))

    story.append(Paragraph('Payments', styles['ClientHeading']))
    if payments.exists():
        payment_data = [['Date', 'Amount', 'Paid']]
        for payment in payments:
            payment_data.append([
                payment.date.strftime('%Y-%m-%d'),
                f"${payment.amount}",
                'Yes' if payment.is_checked else 'No',
            ])
        payment_table = Table(payment_data, colWidths=[180, 180, 120], hAlign='LEFT')
        payment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f4c81')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bcccdc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
        ]))
        story.append(payment_table)
    else:
        story.append(Paragraph('No payments added.', styles['ClientBody']))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f'Total Selling Price: {lead_task.lead.selling_price or "N/A"}', styles['ClientBody']))

    story.append(PageBreak())
    story.append(Paragraph('GHAITH TRAVEL - BOOKING TERMS & TRAVEL POLICY', styles['ClientHeading']))
    policy_lines = [
        "Dear Valued Client,",
        "Thank you for choosing Ghaith Travel to plan your vacation.",
        "We are honored to be part of your travel journey, and our priority is always to provide you with a smooth, secure, and enjoyable experience.",
        "To ensure complete clarity and transparency, we kindly ask you to review the following booking terms.",
        "These policies are designed not to worry you, but to help you clearly understand how your travel arrangements are protected and managed with professionalism and care.",
        "Our team is always here to guide you, support you, and provide the best possible solutions whenever changes arise.",
        "",
        "1. Booking Types: Refundable & Non-Refundable",
        "Travel services vary depending on airline, hotel, destination, and supplier conditions.",
        "Flights:",
        "- Charter flights, low-cost airlines, promotional fares, and special offers are generally non-refundable",
        "- Regular international airline tickets may be refundable depending on airline fare rules",
        "Hotels:",
        "- Hotel cancellation and refund conditions depend on each hotel's own policy",
        "Visa Fees:",
        "- Visa fees become non-refundable once the application has been submitted",
        "Tours & Activities:",
        "- Usually refundable up to 15 days before travel date",
        "- Some online or third-party booked activities may be non-refundable",
        "Before confirming your booking, our travel consultants will always explain the applicable conditions clearly.",
        "",
        "2. If an Airline Cancels Your Flight",
        "In case of airline cancellation, we work immediately to protect your travel plans and offer the best available solutions.",
        "Option 1: Alternative Travel Route",
        "- New routing depends on airline availability",
        "- Any fare difference will be communicated clearly before confirmation",
        "Option 2: Reschedule Your Trip",
        "- Within the same travel season, usually without extra charges",
        "- Voucher may be issued valid for up to 1 year",
        "Important: If new travel dates fall into high season (July, August, December), fare differences may apply.",
        "Option 3: Refund",
        "- Refund will be processed with a deduction of $250 total (office fees + international processing charges)",
        "Conditions:",
        "- Visa refundable only if not yet applied",
        "- Hotels refunded according to hotel booking rules",
        "- Non-refundable hotel rates remain non-refundable",
        "- Tours & transfers refunded where applicable",
        "",
        "3. If You Decide to Cancel Your Trip",
        "Flights: Airline cancellation rules apply; cancellation charges depend on fare type and airline conditions.",
        "Hotels: Hotel cancellation policy applies based on booking terms.",
        "Visa: Non-refundable once applied.",
        "Tours & Activities: Subject to supplier cancellation rules.",
        "A full booking invoice including payment deadlines and cancellation conditions will always be sent to you after confirmation.",
        "",
        "4. Charter & Low-Cost Packages (Including Sharm, Turkey, Georgia & Similar Destinations)",
        "These bookings are non-refundable, non-changeable, non-transferable, and non-voidable once confirmed.",
        "If Airline Cancels Charter Flight:",
        "Option A: Refund - deduction of $50 per person, remaining balance refunded.",
        "Option B: Reschedule - to another available date if possible, subject to airline approval and availability.",
        "",
        "5. Payment Commitment & Reservation Guarantee",
        "Payments must be completed according to agreed deadlines to secure reservation exactly as requested.",
        "Delayed payments may affect price and availability; we will always do our best to assist with alternatives.",
        "",
        "6. Refund Processing Timeline",
        "Approved refunds usually take between 60 to 90 days depending on airlines, hotels, embassies, and suppliers.",
        "Our Accounting Department will contact you with refund amount confirmation and expected refund timeline.",
        "",
        "7. Confirmation of Agreement",
        "Once payment is made, this confirms acceptance of all booking terms, cancellation and refund policies, and authorization for Ghaith Travel to proceed with reservations on your behalf.",
        "",
        "Our Commitment to You",
        "At Ghaith Travel, our role is not only to book your trip - it is to stand by your side before, during, and after your journey.",
        "We are committed to full transparency, honest guidance, fast support when changes happen, and protecting your travel investment as much as possible.",
        "",
        "Thank you for trusting us.",
        "Warm regards,",
        "Ghaith Travel Team",
    ]

    for line in policy_lines:
        safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(safe_line if safe_line else "&nbsp;", styles['PolicyBody']))

    doc.build(story)
    return response


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

    # Hide done tasks by default (only show when filtered or searched)
    if not selected_status and not search_query:
        lead_tasks = lead_tasks.exclude(status='done')

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
            return redirect("edit_lead_tasks", pk=pk)
    else:
        form = PaymentForm()
    return render(request, 'add_payment.html', {'form': form})


@login_required(login_url="/login/")
def client_payments(request):
    if request.user.is_staff:
        payments = Payment.objects.all().order_by('date')
    else:
        payments = Payment.objects.filter(leadtask__assigned_to=request.user).order_by('date')

    search_query = request.GET.get('search', '')
    filter_status = request.GET.get('filter', '')
    show_cancelled = request.GET.get('show_cancelled', '') == 'on'

    # Hide cancelled orders by default.
    if not show_cancelled:
        payments = payments.exclude(leadtask__status='cancelled')

    if search_query:
        payments = payments.filter(
            Q(leadtask__lead__name__icontains=search_query) |
            Q(leadtask__lead__passengers__name__icontains=search_query) |
            Q(leadtask__lead__phone__icontains=search_query) |
            Q(leadtask__lead__channel__icontains=search_query)
        ).distinct()

    if filter_status:
        if filter_status == 'paid':
            payments = payments.filter(is_checked=True)
        elif filter_status == 'unpaid':
            payments = payments.filter(is_checked=False)
        elif filter_status == 'overdue':
            payments = payments.filter(date__lt=timezone.now(), is_checked=False)
        elif filter_status == 'processed':
            payments = payments.filter(processed=True)
        elif filter_status == 'unprocessed':
            payments = payments.filter(processed=False)
    else:
        # Hide processed if no filter
        payments = payments.filter(processed=False)

    return render(request, 'client_payments.html', {
        'payments': payments,
        'now': timezone.now(),
        'show_cancelled': show_cancelled,
    })


@login_required(login_url="/login/")
def travellers_list(request):
    """List leadtasks with a travel date (travellers). Shows all orders with travel date, not only done."""
    now = timezone.now()
    today = now.date() if hasattr(now, 'date') else now

    if request.user.is_staff:
        qs = LeadTask.objects.filter(travel_date__isnull=False).select_related('lead', 'assigned_to')
    else:
        qs = LeadTask.objects.filter(
            travel_date__isnull=False,
            assigned_to=request.user,
        ).select_related('lead', 'assigned_to')

    show_cancellations = request.GET.get('show_cancellations', '') == 'on'
    if not show_cancellations:
        qs = qs.exclude(status='cancelled')

    # Filter: destination (dropdown, exact match)
    destination = request.GET.get('destination', '').strip()
    if destination:
        qs = qs.filter(lead__destination=destination)

    # Filter: month (YYYY-MM)
    month_str = request.GET.get('month', '').strip()
    if month_str:
        try:
            year, month = (int(x) for x in month_str.split('-'))
            qs = qs.filter(travel_date__year=year, travel_date__month=month)
        except (ValueError, TypeError):
            pass

    # Filter: travel date (exact)
    travel_date_str = request.GET.get('travel_date', '').strip()
    if travel_date_str:
        try:
            from datetime import datetime as dt
            parsed = dt.strptime(travel_date_str, '%Y-%m-%d').date()
            qs = qs.filter(travel_date__date=parsed)
        except ValueError:
            pass

    # Filter: exclude already traveled (past travel date)
    show_past = request.GET.get('show_past', '') == 'on'
    if not show_past:
        qs = qs.filter(travel_date__date__gte=today)

    # Filter: return date from–to (date range)
    return_from = request.GET.get('return_from', '').strip()
    return_to = request.GET.get('return_to', '').strip()
    if return_from:
        try:
            from datetime import datetime as dt
            parsed = dt.strptime(return_from, '%Y-%m-%d').date()
            qs = qs.filter(return_date__date__gte=parsed)
        except ValueError:
            pass
    if return_to:
        try:
            from datetime import datetime as dt
            parsed = dt.strptime(return_to, '%Y-%m-%d').date()
            qs = qs.filter(return_date__date__lte=parsed)
        except ValueError:
            pass

    travellers = qs.order_by('travel_date')

    # Destination filter dropdown: use Destination model (admin panel) so new destinations appear without restart
    from display.models import Destination
    destinations = list(Destination.objects.all().order_by('name').values_list('name', flat=True))

    return render(request, 'travellers.html', {
        'travellers': travellers,
        'now': now,
        'today': today,
        'destinations': destinations,
        'request_destination': destination,
        'request_month': month_str,
        'request_travel_date': travel_date_str,
        'show_past': show_past,
        'return_from': return_from,
        'return_to': return_to,
        'show_cancellations': show_cancellations,
    })


@login_required
@require_POST
def mark_payment_processed(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    payment.processed = True
    payment.save()
    return redirect('client_payments')


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
