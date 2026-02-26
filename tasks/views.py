from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Task, LeadTask, Attachment, Service, Payment, TaskAttachment
from .forms import TaskForm, LeadTaskForm, PaymentForm, AttachmentForm, ServiceForm, TaskAttachmentForm
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect
from django.forms import inlineformset_factory, formset_factory
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from django.views.decorators.http import require_POST
from collections import Counter
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from django.http import HttpResponse
from datetime import datetime  # Make sure this line is included
from dashboard.models import Event
from .constants import SUPPLIER_CHOICES
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
    service = Service.objects.get(pk=pk)
    leadtask = service.leadtask.id
    if request.method == 'POST':
        service.is_checked = request.POST.get('is_checked', 'off') == 'on'
        service.save()
    return redirect('edit_lead_tasks', leadtask)  # Redirect to the main page


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
    """Mark a service as paid (is_checked=True) and linked calendar event as done. Redirect to next or supplier list."""
    service = get_object_or_404(Service, pk=pk)
    service.is_checked = True
    service.save()
    try:
        event = service.calendar_event
        event.done = True
        event.save()
    except Exception:
        pass  # No linked calendar event
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('supplier_payments_list')


@login_required(login_url="/login/")
def edit_lead_task(request, pk):
    instance = get_object_or_404(LeadTask, pk=pk)
    services = Service.objects.filter(leadtask=instance)
    lead_task_payments = Payment.objects.filter(leadtask=instance)
    attachments = Attachment.objects.filter(parentleadtask=instance)

    if request.method == 'POST':
        form = LeadTaskForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
    else:
        form = LeadTaskForm(instance=instance)

    predefined_supplier_values = [v for v, _ in SUPPLIER_CHOICES]
    return render(request, 'edit_leadtask.html', {
        'form': form,
        'leadid': pk,
        'lead': instance.lead,
        'services': services,
        'lead_task_payments': lead_task_payments,
        'attachments': attachments,
        'predefined_suppliers': SUPPLIER_CHOICES,
        'predefined_supplier_values': predefined_supplier_values,
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

    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    custom_colors = {'blue': '#0A317C', 'light_blue': '#E7EFF6', 'grey': '#505050'}

    # Custom styles
    styles.add(ParagraphStyle(name='MyTitleStyle', parent=styles['Title'], fontSize=18, leading=22, alignment=TA_CENTER, textColor=colors.HexColor(custom_colors['blue'])))
    styles.add(ParagraphStyle(name='MyHeading2', parent=styles['Heading2'], fontSize=14, leading=18, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor(custom_colors['grey'])))
    styles.add(ParagraphStyle(name='MyBodyText', parent=styles['BodyText'], fontSize=10, leading=12, textColor=colors.HexColor(custom_colors['grey'])))

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
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(custom_colors['light_blue'])),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
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
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(custom_colors['light_blue'])),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        story.append(payments_table)
        story.append(Spacer(1, 12))
    
    # Add selling price to the payments section
    story.append(Paragraph(f"Selling Price: {lead_task.lead.selling_price}", styles['MyBodyText']))
    story.append(Spacer(1, 12))

    doc.build(story)
    return response


@login_required(login_url="/login/")
def current_leadtasks(request):
    status_choices = LeadTask.STATUS_CHOICES
    selected_status = request.GET.get('status', '')
    search_query = request.GET.get('search', '')

    if request.user.is_staff:
        lead_tasks = LeadTask.objects.all()
    else:
        lead_tasks = LeadTask.objects.filter(assigned_to=request.user)

    # Hide done tasks by default (only show when filtered or searched)
    if not selected_status and not search_query:
        lead_tasks = lead_tasks.exclude(status='done')

    if selected_status:
        lead_tasks = lead_tasks.filter(status=selected_status)

    if search_query:
        lead_tasks = lead_tasks.filter(
            Q(pk__icontains=search_query) |
            Q(lead__name__icontains=search_query) |
            Q(lead__destination__icontains=search_query) |
            Q(lead__phone__icontains=search_query) |
            Q(notes__icontains=search_query) |
            Q(assigned_to__username__icontains=search_query)
        )

    # Sort LeadTasks from newest to oldest
    lead_tasks = lead_tasks.order_by('-pk')

    # Calculate counts for each status (include all tasks for counts)
    if request.user.is_staff:
        all_lead_tasks = LeadTask.objects.all()
    else:
        all_lead_tasks = LeadTask.objects.filter(assigned_to=request.user)
    status_counts = dict(Counter(all_lead_tasks.values_list('status', flat=True)))

    return render(request, 'leadtasks.html', {
        'data': lead_tasks,
        'status_choices': status_choices,
        'selected_status': selected_status,
        'search_query': search_query,  # Pass the search query to the template
        'status_counts': status_counts
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

    if search_query:
        payments = payments.filter(
            Q(leadtask__lead__name__icontains=search_query) |
            Q(leadtask__lead__phone__icontains=search_query) |
            Q(leadtask__lead__channel__icontains=search_query)
        )

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

    return render(request, 'client_payments.html', {'payments': payments, 'now': timezone.now()})


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

    # Filter: destination (from lead)
    destination = request.GET.get('destination', '').strip()
    if destination:
        qs = qs.filter(lead__destination__icontains=destination)

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

    travellers = qs.order_by('travel_date')

    # Unique destinations for filter dropdown (from Lead)
    from display.models import Lead
    destinations = Lead.objects.filter(
        destination__isnull=False
    ).exclude(destination='').values_list('destination', flat=True).distinct()[:200]

    return render(request, 'travellers.html', {
        'travellers': travellers,
        'now': now,
        'today': today,
        'destinations': sorted(set(destinations)),
        'request_destination': destination,
        'request_month': month_str,
        'request_travel_date': travel_date_str,
        'show_past': show_past,
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
    leadtask = LeadTask.objects.get(pk=pk)
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
