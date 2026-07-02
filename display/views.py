from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from .forms import (
    LeadForm,
    AttachmentForm,
    SearchLeadsForm,
    CreateLeadForm,
    QualificationForm,
    SendOfferForm,
    CloseDealForm,
    DailyReportForm,
    OfferForm,
)
from .models import (
    Lead,
    Attachment,
    DailyReport,
    Offer,
    MonthlyTarget,
    UserMonthlyTarget,
    Destination,
    CrmNotification,
)
from .passengers import save_lead_passengers
from .phone_utils import build_full_phone, find_duplicate_leads, local_phone_part
from django.db.models import Q
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from collections import Counter
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.timezone import now, timedelta
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
import io
from django.db.models import Count, Sum, F, Case, When, IntegerField
from django.utils.safestring import mark_safe
import json, calendar
from django.contrib.auth.models import User  # Import User model
from django.db.models import FloatField, Value
from django.db.models.functions import Cast


def _aware_month_bounds(year, month):
    start = timezone.datetime(year, month, 1)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
    end = start + timezone.timedelta(days=calendar.monthrange(year, month)[1])
    return start, end


@login_required(login_url="/login")
def logout_user(request):
    logout(request)
    return redirect('login_user')


@login_required(login_url="/login")
def lead_search(request):
    if request.method == 'GET':
        form = SearchLeadsForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            results = Lead.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )
            return render(request, 'search_results.html', {'results': results})
    else:
        form = SearchLeadsForm()
    return render(request, 'search_form.html', {'form': form})


@login_required(login_url="/login")
def input_data(request):
    if request.method == 'POST':
        form = LeadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('display_data')
    else:
        form = LeadForm()
    return render(request, 'input_data.html', {'form': form})


@login_required(login_url="/login")
def create_lead(request, pk=None):
    lead = get_object_or_404(Lead, pk=pk) if pk else None
    if request.method == 'POST':
        form = CreateLeadForm(request.POST, instance=lead)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            country_code = form.cleaned_data['country_code']
            full_phone = build_full_phone(country_code, phone)
            duplicates = find_duplicate_leads(country_code, phone, exclude_pk=pk)

            if duplicates and not request.POST.get('confirm'):
                duplicate_names = ', '.join([dup.name for dup in duplicates])
                return render(request, 'create_lead.html', {
                    'form': form,
                    'lead': lead or form.instance,
                    'passenger_names': request.POST.getlist('passenger_names'),
                    'duplicates': duplicates,
                    'duplicate_warning': (
                        f'This phone number is already used by: {duplicate_names}. '
                        'Submit again to create this request anyway.'
                    ),
                })

            lead = form.save(commit=False)
            lead.phone = full_phone
            # Set default values for removed fields
            if not lead.duration:
                lead.duration = ''
            if not lead.pax:
                lead.pax = ''
            if lead.period is None:
                lead.period = 20
            lead.save()
            save_lead_passengers(lead, request.POST.getlist('passenger_names'))

            if 'submit_next' in request.POST:
                return redirect('qualify_lead', lead_id=lead.pk)
            elif 'submit_exit' in request.POST:
                return redirect('display_data')
    else:
        form = CreateLeadForm(instance=lead)
        if lead and lead.phone:
            form.initial['phone'] = local_phone_part(lead.country_code, lead.phone)
    return render(request, 'create_lead.html', {
        'form': form,
        'lead': lead or form.instance,
        'duplicates': [],
        'passenger_names': [],
    })



@login_required(login_url="/login")
def qualify_lead(request, lead_id):
    main_lead = Lead.objects.get(pk=lead_id)
    if request.method == 'POST':
        form = QualificationForm(request.POST, instance=main_lead)
        if form.is_valid():
            lead = form.save(commit=False)
            # Ensure default values for removed fields
            if not lead.type_of_service:
                lead.type_of_service = ''
            if not lead.duration:
                lead.duration = ''
            if not lead.pax:
                lead.pax = ''
            # travel_date_from and travel_date_to can remain null as they have null=True
            if "submit_next" in request.POST:
                lead.status = "negotiation"
                lead.status_changed_at = now()
                lead.period = 10
                lead.save()
                save_lead_passengers(lead, request.POST.getlist('passenger_names'))
                return redirect('deal_lead', lead_id=lead.pk)
            elif "submit_exit" in request.POST:
                lead.status = "processing"
                lead.status_changed_at = now()
                lead.save()
                save_lead_passengers(lead, request.POST.getlist('passenger_names'))
                return redirect('display_data')
            elif "submit_unqualified" in request.POST:
                lead.status = "done"
                lead.lost = True
                lead.save()
                save_lead_passengers(lead, request.POST.getlist('passenger_names'))
                return redirect('display_data')
    else:
        form = QualificationForm(instance=main_lead)
    return render(request, "qualification_form.html", {'lead': main_lead,
                                                       'form': form})


@login_required(login_url="/login")
def send_offer(request, lead_id):
    """Deprecated — redirect to Close Deal."""
    return redirect('deal_lead', lead_id=lead_id)


@login_required(login_url="/login")
def closing_deal(request, lead_id):
    main_lead = Lead.objects.get(pk=lead_id)
    if request.method == 'POST':
        form = CloseDealForm(request.POST, instance=main_lead)
        if form.is_valid():
            lead = form.save(commit=False)
            
            # Calculate profit automatically if sold
            if "sold" in request.POST:
                selling_price_str = request.POST.get('selling_price', '')
                net_str = request.POST.get('net', '')
                if selling_price_str and net_str:
                    try:
                        # Remove any non-numeric characters and calculate
                        selling_price_clean = float(''.join(c for c in selling_price_str if c.isdigit() or c == '.'))
                        net_clean = float(''.join(c for c in net_str if c.isdigit() or c == '.'))
                        profit_value = selling_price_clean - net_clean
                        lead.profit = str(profit_value)
                    except (ValueError, TypeError):
                        pass  # Keep existing profit if calculation fails
            
            if "lost" in request.POST or "sold" in request.POST:
                lead.status = "finalized"
            if "postpone" in request.POST:
                lead.status = "followup"
                from tasks.calendar_sync import sync_followup_event
                if lead.follow_up:
                    sync_followup_event(lead, user=request.user)
            lead.save()
            save_lead_passengers(lead, request.POST.getlist('passenger_names'))
            return redirect('display_data')
    else:
        form = CloseDealForm(instance=main_lead)
    return render(request, "closedeal.html", {'lead': main_lead, 'form': form})


@login_required(login_url="/login/")
def add_attachment(request, pk):
    lead = Lead.objects.get(pk=pk)
    if request.method == 'POST':
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save()
            lead.attachments.add(attachment)
            # Check referer to redirect back to the correct page
            referer = request.META.get('HTTP_REFERER', '')
            if 'qualify' in referer or lead.status in ['onhold', 'processing']:
                return redirect('qualify_lead', lead_id=pk)
            else:
                return redirect("/sendoffer/" + str(pk))
    else:
        form = AttachmentForm()
    return render(request, 'add_attachment.html', {'form': form})


def delete_attachment(request, lead_id, attachment_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    attachment = get_object_or_404(Attachment, pk=attachment_id)
    if attachment in lead.attachments.all():
        lead.attachments.remove(attachment)
        attachment.delete()
        # Check referer to redirect back to the correct page
        referer = request.META.get('HTTP_REFERER', '')
        if 'qualify' in referer or lead.status in ['onhold', 'processing']:
            return redirect('qualify_lead', lead_id=lead_id)
        elif 'sendoffer' in referer or lead.status == 'negotiation':
            return redirect('deal_lead', lead_id=lead_id)
        else:
            return redirect('edit-model', pk=lead_id)
    else:
        return redirect('edit-model', pk=lead_id)


@login_required(login_url="/login/")
def display_attached_files(request, pk):
    instance = Lead.objects.get(pk=pk)
    if request.method == 'POST':
        form = LeadForm(request.POST, instance=instance)
        if form.is_valid():
            lead = form.save()
            save_lead_passengers(lead, request.POST.getlist('passenger_names'))
            return redirect('display_data')
    else:
        form = LeadForm(instance=instance)
    return render(request, 'edit_model.html', {'form': form, 'lead': instance, 'leadid': instance.pk})


@login_required(login_url="/login/")
def edit_model(request, pk):
    instance = Lead.objects.get(pk=pk)
    if instance.status == "onhold" or instance.status == "followup" or instance.status == "processing" or instance.status == "done":
        return redirect('qualify_lead', lead_id=pk)
    if instance.status == "negotiation":
        return redirect('deal_lead', lead_id=pk)
    if instance.status == "finalized":
        return redirect('deal_lead', lead_id=pk)
    else:
        return redirect('create_lead')


@login_required(login_url="/login/")
def takeover_list(request):
    search_query = request.GET.get('search', '')

    leads = Lead.objects.filter(takeover=True).order_by('-created_at')

    if search_query:
        leads = leads.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(channel__icontains=search_query) |
            Q(reason_of_travel__icontains=search_query)
        )

    for lead in leads:
        if lead.takeover_added_at and lead.takeover_added_at < timezone.now() - timedelta(hours=5):
            lead.is_highlighted = True
        else:
            lead.is_highlighted = False

    return render(request, 'takeover_list.html', {
        'leads': leads,
    })


@login_required(login_url="/login/")
def takeover_lead(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    if request.method == 'POST' or request.method == 'GET':
        lead.assigned_to = request.user
        lead.status = 'processing'
        lead.status_changed_at = now()
        lead.takeover = False
        lead.save()
        return redirect('takeover_list')


@login_required(login_url="/login/")
def display_data(request):
    status_choices = Lead.STATUS_CHOICES
    selected_status = request.GET.get('status', '')
    search_query = request.GET.get('search', '')

    leads = Lead.objects.filter(assigned_to=request.user, is_archived=False).order_by('-created_at')
    
    if selected_status:
        if selected_status == 'sold':
            leads = leads.filter(sold=True, status='finalized')
        elif selected_status == 'lost':
            leads = leads.filter(lost=True, status='finalized')
        else:
            leads = leads.filter(status=selected_status)
    else:
        leads = leads.exclude(status__in=['done', 'finalized'])

    if search_query:
        leads = leads.filter(
            Q(name__icontains=search_query) |
            Q(passengers__name__icontains=search_query) |
            Q(destination__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(finalization_notes__icontains=search_query)
        ).distinct()

    paginator = Paginator(leads, 30)  # Show 30 leads per page
    page = request.GET.get('page')
    try:
        leads = paginator.page(page)
    except PageNotAnInteger:
        leads = paginator.page(1)
    except EmptyPage:
        leads = paginator.page(paginator.num_pages)

    all_leads = Lead.objects.filter(assigned_to=request.user, is_archived=False).exclude(status='done')
    status_counts = dict(Counter(all_leads.values_list('status', flat=True)))
    sold_count = all_leads.filter(status='finalized', sold=True).count()
    lost_count = all_leads.filter(status='finalized', lost=True).count()

    status_choices = list(status_choices)
    status_choices.extend([
        ('sold', 'Sold'),
        ('lost', 'Lost')
    ])

    return render(request, 'display_data.html', {
        'data': leads,
        'status_choices': status_choices,  # Now includes 'Sold' and 'Lost'
        'selected_status': selected_status,
        'status_counts': status_counts,
        'page': page,
        'sold_count': sold_count,
        'lost_count': lost_count
    })

@login_required(login_url="/login/")
def display_archived(request):
    status_choices = Lead.STATUS_CHOICES
    selected_status = request.GET.get('status', '')
    search_query = request.GET.get('search', '')

    leads = Lead.objects.filter(assigned_to=request.user, is_archived=True).order_by('-created_at')
    
    if selected_status:
        leads = leads.filter(status=selected_status)
    if search_query:
        leads = leads.filter(
            Q(name__icontains=search_query) |
            Q(passengers__name__icontains=search_query) |
            Q(destination__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(finalization_notes__icontains=search_query)
        ).distinct()

    paginator = Paginator(leads, 30)  # Show 30 leads per page
    page = request.GET.get('page')
    try:
        leads = paginator.page(page)
    except PageNotAnInteger:
        leads = paginator.page(1)
    except EmptyPage:
        leads = paginator.page(paginator.num_pages)

    all_leads = Lead.objects.filter(assigned_to=request.user, is_archived=True).exclude(status='done')
    status_counts = dict(Counter(all_leads.values_list('status', flat=True)))
    sold_count = all_leads.filter(status='finalized', sold=True).count()
    lost_count = all_leads.filter(status='finalized', lost=True).count()

    status_choices = list(status_choices)
    status_choices.extend([
        ('sold', 'Sold'),
        ('lost', 'Lost')
    ])

    return render(request, 'archived_leads.html', {
        'data': leads,
        'status_choices': status_choices,  # Now includes 'Sold' and 'Lost'
        'selected_status': selected_status,
        'status_counts': status_counts,
        'page': page,
        'sold_count': sold_count,
        'lost_count': lost_count
    })


@login_required(login_url="/login/")
def archive_lead(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    lead.is_archived = True
    lead.save()
    return redirect('display_data')


@login_required(login_url="/login/")
def unarchive_lead(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    lead.is_archived = False
    lead.save()
    return redirect('archived_leads')


@login_required
def daily_report(request):
    user = request.user
    today = timezone.now().date()

    took_over_leads_today = Lead.objects.filter(
        assigned_to=user,
        assigned_at__date=today
    )

    offers_prepared = Offer.objects.filter(
        created_by=user,
        created_at__date=today
    ).count()

    offers_sent = Offer.objects.filter(
        created_by=user,
        created_at__date=today,
        sent=True
    ).count()

    offers_sold = Offer.objects.filter(
        created_by=user,
        created_at__date=today,
        sold=True
    ).count()

    unqualified_leads_count = Lead.objects.filter(
        assigned_to=user,
        status='done',
        lost=True,
        status_changed_at__date=today
    ).count()

    modified_leads_today = Lead.objects.filter(
        assigned_to=user,
        last_modified__date=today
    ).count()  # New field

    if request.method == 'POST':
        form = DailyReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = user
            report.date = today
            report.took_over_leads_today = took_over_leads_today.count()
            report.offers_prepared = offers_prepared
            report.offers_sent = offers_sent
            report.offers_sold = offers_sold
            report.unqualified_leads = unqualified_leads_count
            report.modified_leads_today = modified_leads_today  # New field
            report.save()
            return redirect('list_daily_reports')
    else:
        form = DailyReportForm()

    context = {
        'form': form,
        'username': user.username,
        'today': today,
        'took_over_leads_today': took_over_leads_today.count(),
        'offers_prepared': offers_prepared,
        'offers_sent': offers_sent,
        'offers_sold': offers_sold,
        'unqualified_leads_count': unqualified_leads_count,
        'modified_leads_today': modified_leads_today,  # New field
    }

    return render(request, 'daily_report.html', context)


@login_required(login_url="/login/")
def list_daily_reports(request):
    user = request.user
    reports = DailyReport.objects.filter(user=user).order_by('-created_at')
    
    date_filter = request.GET.get('date', '')
    if date_filter:
        reports = reports.filter(date=date_filter)

    context = {
        'reports': reports,
        'date_filter': date_filter
    }

    return render(request, 'list_daily_reports.html', context)


@login_required(login_url="/login/")
def view_daily_report(request, pk):
    report = get_object_or_404(DailyReport, pk=pk)
    
    # Fetch took over leads and unqualified leads for that day
    took_over_leads = Lead.objects.filter(
        assigned_to=report.user,
        assigned_at__date=report.date
    )

    unqualified_leads = Lead.objects.filter(
        assigned_to=report.user,
        status='done',
        lost=True,
        status_changed_at__date=report.date
    )

    offers_prepared = report.offers_prepared.split('\n') if report.offers_prepared else []
    offers_sent = report.offers_sent.split('\n') if report.offers_sent else []
    offers_sold = report.offers_sold.split('\n') if report.offers_sold else []

    context = {
        'report': report,
        'took_over_leads': took_over_leads,
        'unqualified_leads': unqualified_leads,
        'offers_prepared': offers_prepared,
        'offers_sent': offers_sent,
        'offers_sold': offers_sold,
    }

    return render(request, 'view_daily_report.html', context)


@login_required(login_url="/login")
def create_offer(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    if request.method == 'POST':
        form = OfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.lead = lead
            offer.created_by = request.user
            offer.assigned_to = request.user  # Ensure assigned_to is set
            offer.save()
            return redirect('list_offers')
    else:
        form = OfferForm()
    return render(request, 'create_offer.html', {'form': form, 'lead': lead})


@login_required(login_url="/login")
def view_offer(request, pk):
    offer = get_object_or_404(Offer, pk=pk)
    if request.method == 'POST':
        form = OfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            return redirect('list_offers')
    else:
        form = OfferForm(instance=offer)
    return render(request, 'view_offer.html', {'offer': offer, 'form': form})


@login_required(login_url="/login")
def list_offers(request):
    if request.user.is_staff:
        offers = Offer.objects.all()
    else:
        offers = Offer.objects.filter(created_by=request.user)
    
    date_filter = request.GET.get('date', '')
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if date_filter:
        offers = offers.filter(created_at__date=date_filter)
    if search_query:
        offers = offers.filter(
            Q(title__icontains=search_query) |
            Q(created_by__username__icontains=search_query)
        )
    if status_filter:
        offers = offers.filter(status=status_filter)

    offers = offers.order_by('-created_at')  # Sort by newly created

    return render(request, 'list_offers.html', {'offers': offers})




def footer(canvas, doc):
    canvas.saveState()
    width, height = letter
    canvas.setFont('Helvetica-Bold', 9)
    canvas.setFillColor(colors.HexColor('#0A317C'))
    canvas.rect(0, 0, width, 0.5 * inch, fill=True)
    canvas.setFillColor(colors.white)
    footer_text = 'Tel: +961 71 941100 / +961 3320022 / https://ghaithtravel.com/'
    text_width = canvas.stringWidth(footer_text, 'Helvetica-Bold', 9)
    canvas.drawString((width - text_width) / 2.0, 0.2 * inch, footer_text)
    canvas.restoreState()

@login_required
def download_offer_pdf(request, pk):
    offer = get_object_or_404(Offer, pk=pk)
    destination = offer.lead.destination
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{destination} Offer - {offer.pk}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter, bottomMargin=inch)
    styles = getSampleStyleSheet()
    custom_styles = {
        'title': ParagraphStyle(
            'title',
            parent=styles['Title'],
            fontSize=18,
            textColor=colors.HexColor('#0A317C'),
            alignment=1,
        ),
        'heading': ParagraphStyle(
            'heading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.whitesmoke,
            alignment=1,
        ),
        'body': ParagraphStyle(
            'body',
            parent=styles['BodyText'],
            fontSize=12,
        )
    }

    story = []

    banner_path = 'ghaithleads/static/images/banner.jpg'
    banner = Image(banner_path, width=doc.width, height=1.5 * inch)
    banner.hAlign = 'CENTER'
    story.append(banner)
    story.append(Spacer(1, 12))

    logo_path = 'ghaithleads/static/images/logo.png'
    story.append(Image(logo_path, width=100, height=90))
    story.append(Spacer(1, 12))

    story.append(Paragraph(offer.title, custom_styles['title']))
    story.append(Spacer(1, 12))

    # Description section
    description_paragraphs = [
        Paragraph(line, custom_styles['body']) for line in offer.description.splitlines()
    ]
    for paragraph in description_paragraphs:
        story.append(paragraph)
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))

    section_data = {
        'Itinerary': {'content': offer.itinerary.splitlines(), 'bg_color': colors.HexColor('#0A317C'), 'row_color': colors.HexColor('#E0F1F8')},
        'Pricing': {'content': offer.pricing_usd.splitlines(), 'bg_color': colors.HexColor('#D3D3D3'), 'row_color': colors.HexColor('#F2F2F2')},
        'Inclusions': {'content': offer.inclusions.splitlines(), 'bg_color': colors.HexColor('#006400'), 'row_color': colors.HexColor('#E0FFE0')},
        'Exclusions': {'content': offer.exclusions.splitlines(), 'bg_color': colors.HexColor('#FF0000'), 'row_color': colors.HexColor('#FFE0E0')},
        'Flight Details': {'content': offer.flight_details.splitlines(), 'bg_color': colors.HexColor('#4682B4'), 'row_color': colors.HexColor('#E0F1F8')},
        'Accommodation Options': {'content': offer.accommodation_options.splitlines(), 'bg_color': colors.HexColor('#8B4513'), 'row_color': colors.HexColor('#F5E8D4')}
    }

    for section_title, section_details in section_data.items():
        if section_details['content']:
            # Table title as a row with dark background color
            table_title = Table(
                [[Paragraph(section_title, custom_styles['heading'])]],
                colWidths=[6.5 * inch]
            )
            table_title.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), section_details['bg_color']),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ]))
            story.append(table_title)
            story.append(Spacer(1, 6))

            table_data = [
                [Paragraph(line, custom_styles['body'])] for line in section_details['content']
            ]

            table = Table(table_data, colWidths=[6.5 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), section_details['row_color']),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))

            # Alternate row colors using the section's row color
            for i in range(len(table_data)):
                bg_color = section_details['row_color']
                table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), bg_color)]))

            story.append(table)
            story.append(Spacer(1, 12))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return response



def get_numeric_profit(self):
    try:
        # Extract numeric values from the profit string
        numeric_value = re.sub(r'[^\d.]', '', self.profit)
        return float(numeric_value) if numeric_value else 0.0
    except ValueError:
        return 0.0



@login_required(login_url="/login/")
def stats_dashboard(request):
    current_year = timezone.now().year

    # Calculate data for general stats
    sold_over_modified = []
    sold_over_negotiation = []
    unqualified_over_modified = []

    for month in range(1, 13):
        month_start, month_end = _aware_month_bounds(current_year, month)

        modified_leads = Lead.objects.filter(last_modified__range=(month_start, month_end))
        sold_leads = modified_leads.filter(sold=True)
        negotiation_leads = modified_leads.filter(moved_to_negotiation=True)
        unqualified_leads = modified_leads.filter(status='done', lost=True)

        if modified_leads.count() > 0:
            sold_over_modified.append((sold_leads.count() / modified_leads.count()) * 100)
        else:
            sold_over_modified.append(0)

        if negotiation_leads.count() > 0:
            sold_over_negotiation.append((sold_leads.count() / negotiation_leads.count()) * 100)
        else:
            sold_over_negotiation.append(0)

        if modified_leads.count() > 0:
            unqualified_over_modified.append((unqualified_leads.count() / modified_leads.count()) * 100)
        else:
            unqualified_over_modified.append(0)

    # Example data for monthly target progress
    month_list = [calendar.month_name[i] for i in range(1, 13)]
    selected_month = request.GET.get('month', month_list[timezone.now().month - 1])  # Default to current month
    selected_month_index = month_list.index(selected_month) + 1
    month_start, month_end = _aware_month_bounds(current_year, selected_month_index)

    monthly_target_obj = MonthlyTarget.objects.filter(month__year=current_year, month__month=selected_month_index).first()
    monthly_target = monthly_target_obj.target_profit if monthly_target_obj else 0

    sold_leads_this_month = Lead.objects.filter(last_modified__range=(month_start, month_end), sold=True)
    achieved_profit = sum(lead.get_numeric_profit() for lead in sold_leads_this_month)
    progress_percentage = (achieved_profit / monthly_target) * 100 if monthly_target else 0
    progress_display = min(progress_percentage, 100)

    # Additional stats
    employee_stats = []
    employees = User.objects.filter(is_sales=True)
    total_team_sales = sold_leads_this_month.count()

    for employee in employees:
        employee_modified_leads = Lead.objects.filter(assigned_to=employee, last_modified__range=(month_start, month_end))
        employee_sold_leads = employee_modified_leads.filter(sold=True)
        employee_overtaken_leads = Lead.objects.filter(assigned_to=employee, assigned_at__range=(month_start, month_end)).count()

        employee_profit = sum(lead.get_numeric_profit() for lead in employee_sold_leads)

        if employee_modified_leads.count() > 0:
            percentage_sold_over_modified = (employee_sold_leads.count() / employee_modified_leads.count()) * 100
        else:
            percentage_sold_over_modified = 0

        if total_team_sales > 0:
            percentage_of_total_team_sales = (employee_sold_leads.count() / total_team_sales) * 100
        else:
            percentage_of_total_team_sales = 0

        user_monthly_target = UserMonthlyTarget.objects.filter(user=employee, month__year=current_year, month__month=selected_month_index).first()
        user_target_profit = user_monthly_target.target_profit if user_monthly_target else 0
        user_progress_percentage = (employee_profit / user_target_profit) * 100 if user_target_profit else 0

        if percentage_sold_over_modified < 20:
            color = 'red'
        elif 20 <= percentage_sold_over_modified < 70:
            color = 'orange'
        else:
            color = 'green'

        employee_stats.append({
            'employee': employee,
            'percentage_sold_over_modified': round(percentage_sold_over_modified, 2),
            'percentage_of_total_team_sales': round(percentage_of_total_team_sales, 2),
            'overtaken_leads': employee_overtaken_leads,
            'profit': employee_profit,
            'color': color,
            'modified_leads': employee_modified_leads.count(),
            'sent_offers': Offer.objects.filter(created_by=employee, created_at__range=(month_start, month_end), sent=True).count(),
            'sold_offers': Offer.objects.filter(created_by=employee, created_at__range=(month_start, month_end), sold=True).count(),
            'user_target_profit': user_target_profit,
            'user_progress_percentage': user_progress_percentage if request.user.is_staff or request.user == employee else 'NA'
        })

    # Calculate conversion rates for top destinations
    top_destinations = Lead.objects.filter(last_modified__range=(month_start, month_end)).values('destination').annotate(
        destination_count=Count('destination'),
        conversion_rate=Sum(Case(
            When(sold=True, then=1),
            default=0,
            output_field=FloatField()
        )) * 100 / Count('destination')
    ).order_by('-destination_count')[:5]

    # Lead counts by status, sold, lost, and is_takeover
    status_counts = Lead.objects.values('status').annotate(count=Count('status'))
    sold_count = Lead.objects.filter(status='finalized', sold=True).count()
    lost_count = Lead.objects.filter(status='finalized', lost=True).count()
    is_takeover_count = Lead.objects.filter(takeover=True).count()
    
    status_labels = [status['status'] for status in status_counts] + ['Sold', 'Lost', 'Takeover']
    status_counts_data = [status['count'] for status in status_counts] + [sold_count, lost_count, is_takeover_count]

    context = {
        'current_year': current_year,
        'sold_over_modified': mark_safe(json.dumps(sold_over_modified)),
        'sold_over_negotiation': mark_safe(json.dumps(sold_over_negotiation)),
        'unqualified_over_modified': mark_safe(json.dumps(unqualified_over_modified)),
        'month_list': month_list,
        'selected_month': selected_month,
        'monthly_target': monthly_target,
        'achieved_profit': achieved_profit,
        'progress_percentage': progress_percentage,
        'progress_display': progress_display,
        'employee_stats': employee_stats,
        'top_destinations': top_destinations,
        'status_labels': mark_safe(json.dumps(status_labels)),
        'status_counts': mark_safe(json.dumps(status_counts_data)),
    }

    return render(request, 'stats_dashboard.html', context)
