"""Shared invoice-style PDF layout for CRM exports."""
from datetime import datetime

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


TEAL = colors.HexColor('#1a5f6b')
TEAL_LIGHT = colors.HexColor('#e8f4f6')
GREY = colors.HexColor('#627d98')
ROW_ALT = colors.HexColor('#f5f7fa')

COMPANY = {
    'name': 'Ghaith Travel',
    'address_line1': 'Bechara El Khoury Highway',
    'address_line2': 'Beirut, Lebanon',
    'phone': '+961-81456406',
    'email': 'info@ghaithtravel.com',
    'website': 'www.ghaithtravel.com',
    'hours': '9:00 AM - 5:00 PM',
}


def company_contact_lines():
    """Right-side company block in the teal PDF header."""
    return [
        COMPANY['name'],
        COMPANY['address_line1'],
        COMPANY['address_line2'],
        f"Tel: {COMPANY['phone']}",
        f"Email: {COMPANY['email']}",
        f"Reception: {COMPANY['hours']}",
        COMPANY['website'],
    ]


def company_info_pairs():
    """Key/value rows shown under the header on list/report PDFs."""
    return [
        ('Reception Office', f"{COMPANY['address_line1']}, {COMPANY['address_line2']}"),
        ('Reception Hours', COMPANY['hours']),
        ('Phone', COMPANY['phone']),
        ('Email', COMPANY['email']),
    ]


def purchases_applied_filters(params):
    """Human-readable filters for Purchases PDF from query params."""
    filters = []
    month = (params.get('month') or '').strip()
    date = (params.get('date') or '').strip()
    issued = (params.get('issued') or params.get('paid') or '').strip()
    overdue = params.get('overdue') == 'on' or params.get('late') == 'on'
    supplier = (params.get('supplier') or '').strip()
    service = (params.get('service') or '').strip()
    show_cancelled = params.get('show_cancelled') == 'on'

    if month:
        filters.append(f'Month: {month}')
    if date:
        filters.append(f'Date: {date}')
    if overdue:
        filters.append('Overdue only')
    elif issued in ('issued', 'paid'):
        filters.append('Issued only')
    elif issued in ('unissued', 'unpaid'):
        filters.append('Unissued only')
    elif not month and not date:
        filters.append('Unissued only (default)')
    if supplier:
        filters.append(f'Supplier: {supplier}')
    if service:
        filters.append(f'Service: {service}')
    if show_cancelled:
        filters.append('Including cancelled orders')
    return filters


def client_payments_applied_filters(params):
    """Human-readable filters for Client Payments PDF from query params."""
    filters = []
    month = (params.get('month') or '').strip()
    date = (params.get('date') or '').strip()
    issued = (params.get('issued') or params.get('paid') or '').strip()
    overdue = params.get('overdue') == 'on' or params.get('late') == 'on'
    refund = params.get('refund') == 'on'
    show_cancelled = params.get('show_cancelled') == 'on'

    if refund:
        filters.append('Refunds only')
    if month:
        filters.append(f'Month: {month}')
    if date:
        filters.append(f'Date: {date}')
    if overdue:
        filters.append('Overdue only')
    elif issued in ('issued', 'paid'):
        filters.append('Received only')
    elif issued in ('unissued', 'unpaid'):
        filters.append('Outstanding only')
    elif not refund and not month and not date:
        filters.append('Outstanding & refunds (default)')
    if show_cancelled:
        filters.append('Including cancelled orders')
    return filters


def travellers_applied_filters(params):
    """Human-readable filters for Travellers PDF from query params."""
    filters = []
    destination = (params.get('destination') or '').strip()
    month = (params.get('month') or '').strip()
    travel_from = (params.get('travel_from') or '').strip()
    travel_to = (params.get('travel_to') or '').strip()
    return_from = (params.get('return_from') or '').strip()
    return_to = (params.get('return_to') or '').strip()
    show_past = params.get('show_past') == 'on'
    show_cancellations = params.get('show_cancellations') == 'on'

    if destination:
        filters.append(f'Destination: {destination}')
    if month:
        filters.append(f'Travel month: {month}')
    if travel_from:
        filters.append(f'Travel from: {travel_from}')
    if travel_to:
        filters.append(f'Travel to: {travel_to}')
    if return_from:
        filters.append(f'Return from: {return_from}')
    if return_to:
        filters.append(f'Return to: {return_to}')
    if show_past:
        filters.append('Including past travel')
    elif not any([destination, month, travel_from, travel_to, return_from, return_to]):
        filters.append('Upcoming travel only (default)')
    if show_cancellations:
        filters.append('Including cancelled orders')
    return filters


def make_document_header(doc_title, styles=None):
    """Teal title band + company contact lines (shared across all CRM PDFs)."""
    styles = styles or _styles()
    return [
        _header_table(doc_title, company_contact_lines(), styles),
        Spacer(1, 8),
    ]


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'InvTitle', parent=base['Heading1'], fontSize=22, textColor=colors.white,
            fontName='Helvetica-Bold', spaceAfter=0,
        ),
        'company': ParagraphStyle(
            'InvCompany', parent=base['Normal'], fontSize=9, textColor=colors.white,
            alignment=2, leading=12,
        ),
        'label': ParagraphStyle(
            'InvLabel', parent=base['Normal'], fontSize=8, textColor=GREY,
            fontName='Helvetica-Bold',
        ),
        'value': ParagraphStyle(
            'InvValue', parent=base['Normal'], fontSize=9, textColor=colors.HexColor('#102a43'),
        ),
        'policy': ParagraphStyle(
            'InvPolicy', parent=base['Normal'], fontSize=8.5, leading=11,
            textColor=colors.HexColor('#334e68'),
        ),
    }


def _header_table(title, company_lines, styles):
    company_html = '<br/>'.join(company_lines)
    data = [[
        Paragraph(title.upper(), styles['title']),
        Paragraph(company_html, styles['company']),
    ]]
    t = Table(data, colWidths=[4.2 * inch, 3.3 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), TEAL),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 16),
        ('RIGHTPADDING', (1, 0), (1, 0), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
    ]))
    return t


def _info_row(left_pairs, right_pairs, styles):
    left = '<br/>'.join(
        f'<b>{k}:</b> {v}' for k, v in left_pairs
    )
    right = '<br/>'.join(
        f'<b>{k}:</b> {v}' for k, v in right_pairs
    )
    data = [[
        Paragraph(left, styles['value']),
        Paragraph(right, styles['value']),
    ]]
    t = Table(data, colWidths=[3.75 * inch, 3.75 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), TEAL_LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t


def _data_table(headers, rows, compact=False):
    data = [headers] + rows
    head_size = 8 if compact else 9
    body_size = 7 if compact else 8
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9e8ec')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#102a43')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), head_size),
        ('FONTSIZE', (0, 1), (-1, -1), body_size),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bcccdc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def _totals_table(lines, total_label, total_value):
    data = []
    for label, val in lines:
        data.append([label, val])
    data.append(['', ''])
    data.append([total_label, total_value])
    t = Table(data, colWidths=[2.5 * inch, 1.2 * inch])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#cce5ff')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _meta_block(generated_at, applied_filters, styles, detail_lines=None):
    """Full-width report meta: generated timestamp, optional details and filters."""
    lines = [f'<b>Generated:</b> {generated_at}']
    if detail_lines:
        lines.extend(detail_lines)
    if applied_filters:
        lines.append(f'<b>Filters:</b> {" · ".join(applied_filters)}')
    html = '<br/>'.join(lines)
    data = [[Paragraph(html, styles['value'])]]
    t = Table(data, colWidths=[7.5 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), TEAL_LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


def build_report_pdf(
    *,
    response,
    doc_title='REPORT',
    subtitle='',
    applied_filters=None,
    left_info=None,
    right_info=None,
    headers,
    rows,
    totals=None,
    landscape_mode=True,
):
    """Build a PDF matching the invoice template style."""
    styles = _styles()
    pagesize = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(
        response, pagesize=pagesize,
        leftMargin=28, rightMargin=28, topMargin=20, bottomMargin=20,
    )
    company = company_contact_lines()
    if left_info is None and right_info is None:
        pairs = company_info_pairs()
        left_info = pairs[:2]
        right_info = pairs[2:]
    elif left_info is None:
        left_info = company_info_pairs()[:2]
    elif right_info is None:
        right_info = company_info_pairs()[2:]
    story = [
        _header_table(doc_title, company, styles),
        Spacer(1, 8),
    ]
    if left_info or right_info:
        story.append(_info_row(left_info or [], right_info or [], styles))
        story.append(Spacer(1, 8))
    generated_at = timezone.now().strftime('%Y-%m-%d %H:%M')
    if subtitle:
        generated_at = subtitle
    story.append(_meta_block(generated_at, applied_filters, styles))
    story.append(Spacer(1, 10))
    story.append(_data_table(headers, rows))
    if totals:
        story.append(Spacer(1, 10))
        story.append(_totals_table(
            totals.get('lines', []),
            totals.get('total_label', 'Total'),
            totals.get('total_value', ''),
        ))
    doc.build(story)
    return response


CLIENT_POLICY_LINES = [
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


def _section_heading(text, styles):
    return [Paragraph(text, styles['label']), Spacer(1, 4)]


def _fmt_datetime(value):
    if not value:
        return '—'
    return value.strftime('%Y-%m-%d %H:%M')


def _fmt_date(value):
    if not value:
        return '—'
    return value.strftime('%Y-%m-%d')


def _money_display(value):
    if value in (None, ''):
        return '—'
    text = str(value).strip()
    return text if text.startswith('$') else f'${text}'


def _kv_rows(pairs):
    return [[label, str(value)] for label, value in pairs if value not in (None, '')]


def _policy_paragraphs(lines, styles):
    story = []
    for line in lines:
        safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(safe_line if safe_line else '&nbsp;', styles['policy']))
    return story


def build_client_invoice_pdf(*, response, lead_task, services, payments):
    """Client-facing invoice PDF using the shared teal report layout."""
    styles = _styles()
    lead = lead_task.lead
    doc = SimpleDocTemplate(
        response, pagesize=landscape(A4),
        leftMargin=28, rightMargin=28, topMargin=20, bottomMargin=20,
    )

    created_by = lead_task.assigned_to.get_full_name() or lead_task.assigned_to.username
    issue_date = timezone.now().strftime('%Y-%m-%d')
    travel_date = lead_task.travel_date.strftime('%Y-%m-%d') if lead_task.travel_date else '—'
    return_date = lead_task.return_date.strftime('%Y-%m-%d') if lead_task.return_date else '—'
    generated_at = timezone.now().strftime('%Y-%m-%d %H:%M')

    pairs = company_info_pairs()
    detail_lines = [
        f'<b>Invoice #:</b> {lead_task.pk} &nbsp;&nbsp; <b>Client:</b> {lead.name}',
        f'<b>Prepared by:</b> {created_by} &nbsp;&nbsp; <b>Issue date:</b> {issue_date}',
    ]

    story = [
        _header_table('CLIENT INVOICE', company_contact_lines(), styles),
        Spacer(1, 8),
        _info_row(pairs[:2], pairs[2:], styles),
        Spacer(1, 8),
        _meta_block(generated_at, None, styles, detail_lines=detail_lines),
        Spacer(1, 8),
        _info_row(
            [
                ('Travel date', travel_date),
                ('Return date', return_date),
                ('Payment', lead_task.payment or '—'),
            ],
            [
                ('Destination', lead.destination or '—'),
                ('Channel', lead.channel or '—'),
            ],
            styles,
        ),
        Spacer(1, 10),
    ]

    client_rows = []
    for label, value in [
        ('Name', lead.name),
        ('Phone', lead.phone),
        ('Email', getattr(lead, 'email', None)),
        ('Request details', lead.special_request),
        ('Date of birth', lead_task.date_of_birth.strftime('%Y-%m-%d') if lead_task.date_of_birth else None),
        ('Passport expiry', lead_task.passport_expiry_date.strftime('%Y-%m-%d') if lead_task.passport_expiry_date else None),
    ]:
        if value not in (None, ''):
            client_rows.append([label, str(value)])

    if client_rows:
        story.extend(_section_heading('CLIENT DETAILS', styles))
        story.append(_data_table(['Field', 'Value'], client_rows))
        story.append(Spacer(1, 10))

    story.extend(_section_heading('SERVICES', styles))
    if services:
        service_rows = [
            [str(idx), service.service_name or '—', service.details or '—']
            for idx, service in enumerate(services, 1)
        ]
    else:
        service_rows = [['—', 'No services', '—']]
    story.append(_data_table(['#', 'Service', 'Details'], service_rows))
    story.append(Spacer(1, 10))

    story.extend(_section_heading('PAYMENTS', styles))
    if payments:
        payment_rows = [
            [
                payment.date.strftime('%Y-%m-%d'),
                f'${payment.amount}',
                'Yes' if payment.is_checked else 'No',
            ]
            for payment in payments
        ]
    else:
        payment_rows = [['—', '—', 'No payments']]
    story.append(_data_table(['Date', 'Amount', 'Received'], payment_rows))
    story.append(Spacer(1, 10))

    total = lead.selling_price
    total_str = f'${total}' if total is not None else 'N/A'
    story.append(_totals_table([], 'Total selling price', total_str))

    story.append(PageBreak())
    story.extend(_section_heading('BOOKING TERMS & TRAVEL POLICY', styles))
    story.extend(_policy_paragraphs(CLIENT_POLICY_LINES, styles))

    doc.build(story)
    return response


def build_internal_invoice_pdf(*, response, lead_task, services, payments, attachments=None):
    """Staff-facing invoice PDF with full booking, finance, and service detail."""
    from tasks.constants import effective_service_net, parse_money

    styles = _styles()
    lead = lead_task.lead
    doc = SimpleDocTemplate(
        response, pagesize=landscape(A4),
        leftMargin=28, rightMargin=28, topMargin=20, bottomMargin=20,
    )

    assigned = lead_task.assigned_to.get_full_name() or lead_task.assigned_to.username
    generated_at = timezone.now().strftime('%Y-%m-%d %H:%M')
    status_label = lead_task.get_status_display()
    payment_label = lead_task.get_payment_display() if lead_task.payment else '—'
    services_list = list(services)
    services_issued = sum(1 for s in services_list if s.is_checked)
    total_net = sum(parse_money(effective_service_net(s)) for s in services_list)
    total_selling = parse_money(lead.selling_price)
    total_profit = total_selling - total_net

    pairs = company_info_pairs()
    detail_lines = [
        f'<b>Invoice #:</b> {lead_task.pk} &nbsp;&nbsp; <b>Client:</b> {lead.name} &nbsp;&nbsp; <b>Status:</b> {status_label}',
        f'<b>Assigned to:</b> {assigned} &nbsp;&nbsp; <b>Payment:</b> {payment_label}',
    ]

    story = [
        _header_table('INTERNAL INVOICE', company_contact_lines(), styles),
        Spacer(1, 8),
        _info_row(pairs[:2], pairs[2:], styles),
        Spacer(1, 8),
        _meta_block(generated_at, None, styles, detail_lines=detail_lines),
        Spacer(1, 8),
        _info_row(
            [
                ('Travel date', _fmt_datetime(lead_task.travel_date)),
                ('Return date', _fmt_datetime(lead_task.return_date)),
                ('Services issued', f'{services_issued} / {len(services_list)}'),
            ],
            [
                ('Lead created', _fmt_datetime(lead.created_at)),
                ('Last updated', _fmt_datetime(lead.last_modified)),
                ('Passengers', str(lead.passengers.count())),
            ],
            styles,
        ),
        Spacer(1, 10),
    ]

    invoice_rows = _kv_rows([
        ('Status', status_label),
        ('Assigned to', assigned),
        ('Payment type', payment_label),
        ('Travel date', _fmt_datetime(lead_task.travel_date)),
        ('Return date', _fmt_datetime(lead_task.return_date)),
        ('Invoice notes', lead_task.notes),
        ('What happened', lead.finalization_notes),
    ])
    if invoice_rows:
        story.extend(_section_heading('INVOICE DETAILS', styles))
        story.append(_data_table(['Field', 'Value'], invoice_rows))
        story.append(Spacer(1, 10))

    passenger_names = [p.name for p in lead.passengers.all()]
    customer_rows = _kv_rows([
        ('Name', lead.name),
        ('Phone', lead.phone),
        ('Email', getattr(lead, 'email', None)),
        ('Channel', lead.channel),
        ('Destination', lead.destination),
        ('Date of birth', _fmt_date(lead_task.date_of_birth)),
        ('Passport expiry', _fmt_date(lead_task.passport_expiry_date)),
        ('Request details', lead.special_request),
        ('Passengers', ', '.join(passenger_names) if passenger_names else None),
    ])
    if customer_rows:
        story.extend(_section_heading('CUSTOMER DETAILS', styles))
        story.append(_data_table(['Field', 'Value'], customer_rows))
        story.append(Spacer(1, 10))

    story.extend(_section_heading('SERVICES', styles))
    if services_list:
        service_rows = [
            [
                service.service_name or '—',
                service.supplier or '—',
                (service.details or '—')[:120],
                _money_display(service.net),
                _money_display(service.issue_price),
                _money_display(service.selling),
                _fmt_datetime(service.due_time),
                service.voucher_id or '—',
                'Yes' if service.send_to_client else 'No',
                'Yes' if service.is_checked else 'No',
            ]
            for service in services_list
        ]
    else:
        service_rows = [['—', '—', 'No services', '—', '—', '—', '—', '—', '—', '—']]
    story.append(_data_table(
        ['Service', 'Supplier', 'Details', 'Net', 'Issue', 'Selling', 'Due', 'Voucher', 'Client', 'Issued'],
        service_rows,
        compact=True,
    ))
    story.append(Spacer(1, 10))

    story.extend(_section_heading('FINANCE SUMMARY', styles))
    story.append(_totals_table(
        [
            ('Total net (services)', f'${total_net:,.2f}'),
            ('Total selling', _money_display(lead.selling_price)),
        ],
        'Profit',
        f'${total_profit:,.2f}',
    ))
    story.append(Spacer(1, 10))

    story.extend(_section_heading('PAYMENTS', styles))
    payments_list = list(payments)
    if payments_list:
        payment_rows = [
            [
                _fmt_datetime(payment.date),
                f'${payment.amount}',
                'Yes' if payment.is_checked else 'No',
                'Yes' if payment.is_refund else 'No',
            ]
            for payment in payments_list
        ]
    else:
        payment_rows = [['—', '—', 'No payments', '—']]
    story.append(_data_table(['Date', 'Amount', 'Received', 'Refund'], payment_rows))
    story.append(Spacer(1, 10))

    if attachments:
        attachment_rows = [[a.attachment_name or '—', _fmt_datetime(a.uploaded_at)] for a in attachments]
        story.extend(_section_heading('ATTACHMENTS', styles))
        story.append(_data_table(['File', 'Uploaded'], attachment_rows))

    doc.build(story)
    return response
