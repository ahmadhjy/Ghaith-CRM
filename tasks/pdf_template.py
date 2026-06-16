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
ROW_ALT = colors.HexColor('#f3f8f9')
INK = colors.HexColor('#0f2a3a')
BORDER = colors.HexColor('#cddde2')

# Usable content width on landscape A4 with 28pt left/right margins.
FULL_WIDTH = landscape(A4)[0] - 56

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


def make_document_header(doc_title, styles=None, subtitle=''):
    """Modern full-width title band + company contact bar (shared across CRM PDFs)."""
    styles = styles or _styles()
    return [
        _header_band(doc_title, subtitle, styles),
        Spacer(1, 10),
        _company_bar(styles),
        Spacer(1, 12),
    ]


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'InvTitle', parent=base['Heading1'], fontSize=30, leading=34,
            textColor=colors.white, fontName='Helvetica-Bold', spaceAfter=0,
        ),
        'subtitle': ParagraphStyle(
            'InvSubtitle', parent=base['Normal'], fontSize=12, leading=16,
            textColor=colors.HexColor('#cfe6ea'),
        ),
        'company_name': ParagraphStyle(
            'InvCoName', parent=base['Normal'], fontSize=12.5, leading=16,
            textColor=TEAL, fontName='Helvetica-Bold',
        ),
        'company_line': ParagraphStyle(
            'InvCoLine', parent=base['Normal'], fontSize=9.5, leading=14, textColor=GREY,
        ),
        'section': ParagraphStyle(
            'InvSection', parent=base['Heading2'], fontSize=13.5, leading=16,
            textColor=TEAL, fontName='Helvetica-Bold', spaceBefore=0, spaceAfter=0,
        ),
        'kv_label': ParagraphStyle(
            'InvKvLabel', parent=base['Normal'], fontSize=10, leading=13,
            textColor=GREY, fontName='Helvetica-Bold',
        ),
        'kv_value': ParagraphStyle(
            'InvKvValue', parent=base['Normal'], fontSize=10.5, leading=14, textColor=INK,
        ),
        'meta': ParagraphStyle(
            'InvMeta', parent=base['Normal'], fontSize=10, leading=15, textColor=INK,
        ),
        'policy': ParagraphStyle(
            'InvPolicy', parent=base['Normal'], fontSize=10, leading=14,
            textColor=colors.HexColor('#334e68'),
        ),
        # legacy aliases (kept for any external callers)
        'label': ParagraphStyle(
            'InvLabel', parent=base['Normal'], fontSize=10, textColor=GREY, fontName='Helvetica-Bold',
        ),
        'value': ParagraphStyle(
            'InvValue', parent=base['Normal'], fontSize=10.5, textColor=INK, leading=14,
        ),
        'company': ParagraphStyle(
            'InvCompany', parent=base['Normal'], fontSize=9.5, textColor=colors.white, leading=13,
        ),
    }


def _header_band(title, subtitle, styles):
    """Full-width teal band: big left-aligned title with optional subtitle."""
    cell = [Paragraph(title.upper(), styles['title'])]
    if subtitle:
        cell.append(Spacer(1, 3))
        cell.append(Paragraph(subtitle, styles['subtitle']))
    t = Table([[cell]], colWidths=[FULL_WIDTH])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), TEAL),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 22),
        ('RIGHTPADDING', (0, 0), (-1, -1), 22),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
    ]))
    return t


def _company_bar(styles):
    """Full-width light contact strip below the header (aligned, not on the side)."""
    name = Paragraph(COMPANY['name'], styles['company_name'])
    details = '&nbsp;&nbsp;|&nbsp;&nbsp;'.join([
        f"{COMPANY['address_line1']}, {COMPANY['address_line2']}",
        f"Tel: {COMPANY['phone']}",
        f"Email: {COMPANY['email']}",
        f"Reception: {COMPANY['hours']}",
        COMPANY['website'],
    ])
    line = Paragraph(details, styles['company_line'])
    t = Table([[[name, Spacer(1, 2), line]]], colWidths=[FULL_WIDTH])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), TEAL_LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -1), 2, TEAL),
    ]))
    return t


def _info_stack(pairs, styles):
    """Full-width, left-aligned label/value rows (stacked, never on the side)."""
    rows = [
        [Paragraph(str(label), styles['kv_label']), Paragraph(str(value), styles['kv_value'])]
        for label, value in pairs if value not in (None, '')
    ]
    if not rows:
        return Spacer(0, 0)
    label_w = 2.3 * inch
    t = Table(rows, colWidths=[label_w, FULL_WIDTH - label_w])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, BORDER),
    ]))
    return t


def _info_row(left_pairs, right_pairs, styles):
    """Legacy signature: render all details as one aligned full-width stack."""
    return _info_stack(list(left_pairs) + list(right_pairs), styles)


def _data_table(headers, rows, compact=False, col_widths=None):
    base = getSampleStyleSheet()
    th = ParagraphStyle(
        'Th', parent=base['Normal'], fontName='Helvetica-Bold',
        fontSize=9.5 if compact else 10.5, leading=13, textColor=colors.white,
    )
    td = ParagraphStyle(
        'Td', parent=base['Normal'], fontName='Helvetica',
        fontSize=8.6 if compact else 10, leading=12.5, textColor=INK,
    )
    ncols = len(headers)
    if col_widths is None:
        widths = [FULL_WIDTH / ncols] * ncols
    else:
        scale = FULL_WIDTH / float(sum(col_widths))
        widths = [w * scale for w in col_widths]
    header_cells = [Paragraph(str(h), th) for h in headers]
    body = [[Paragraph('' if c is None else str(c), td) for c in r] for r in rows]
    data = [header_cells] + body
    pad = 6 if compact else 9
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL),
        ('TOPPADDING', (0, 0), (-1, 0), pad + 1),
        ('BOTTOMPADDING', (0, 0), (-1, 0), pad + 1),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), pad),
        ('BOTTOMPADDING', (0, 1), (-1, -1), pad),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDER),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
    ]))
    return t


def _totals_table(lines, total_label, total_value):
    """Full-width totals: secondary rows then a highlighted teal total bar."""
    base = getSampleStyleSheet()
    lab = ParagraphStyle('TtlLab', parent=base['Normal'], fontSize=10.5, leading=14, textColor=GREY)
    val = ParagraphStyle('TtlVal', parent=base['Normal'], fontSize=10.5, leading=14, textColor=INK, alignment=2)
    tlab = ParagraphStyle('TtlTLab', parent=base['Normal'], fontSize=13, leading=16,
                          textColor=colors.white, fontName='Helvetica-Bold')
    tval = ParagraphStyle('TtlTVal', parent=base['Normal'], fontSize=15, leading=18,
                          textColor=colors.white, fontName='Helvetica-Bold', alignment=2)
    data = [[Paragraph(str(label), lab), Paragraph(str(value), val)] for label, value in lines]
    data.append([Paragraph(str(total_label), tlab), Paragraph(str(total_value), tval)])
    t = Table(data, colWidths=[FULL_WIDTH * 0.7, FULL_WIDTH * 0.3])
    last = len(data) - 1
    style = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('BACKGROUND', (0, last), (-1, last), TEAL),
        ('TOPPADDING', (0, last), (-1, last), 11),
        ('BOTTOMPADDING', (0, last), (-1, last), 11),
    ]
    for i in range(last):
        style.append(('LINEBELOW', (0, i), (-1, i), 0.5, BORDER))
    t.setStyle(TableStyle(style))
    return t


def _meta_block(generated_at, applied_filters, styles, detail_lines=None):
    """Full-width report meta: generated timestamp, optional details and filters."""
    lines = [f'<b>Generated:</b> {generated_at}']
    if detail_lines:
        lines.extend(detail_lines)
    if applied_filters:
        lines.append(f'<b>Filters:</b> {" &nbsp;·&nbsp; ".join(applied_filters)}')
    html = '<br/>'.join(lines)
    t = Table([[Paragraph(html, styles['meta'])]], colWidths=[FULL_WIDTH])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), ROW_ALT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -1), 2, TEAL),
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
    """Build a modern, full-width report PDF (Purchases, Client Payments, Travellers)."""
    styles = _styles()
    pagesize = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(
        response, pagesize=pagesize,
        leftMargin=28, rightMargin=28, topMargin=22, bottomMargin=24,
    )
    generated_at = subtitle or timezone.now().strftime('%Y-%m-%d %H:%M')
    story = [
        _header_band(doc_title, '', styles),
        Spacer(1, 10),
        _company_bar(styles),
        Spacer(1, 12),
        _meta_block(generated_at, applied_filters, styles),
        Spacer(1, 12),
        _data_table(headers, rows),
    ]
    if totals:
        story.append(Spacer(1, 12))
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
    t = Table([[Paragraph(text.upper(), styles['section'])]], colWidths=[FULL_WIDTH])
    t.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 1.4, TEAL),
    ]))
    return [t, Spacer(1, 8)]


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
    """Client-facing invoice PDF — modern, full-width, aligned layout."""
    styles = _styles()
    lead = lead_task.lead
    doc = SimpleDocTemplate(
        response, pagesize=landscape(A4),
        leftMargin=28, rightMargin=28, topMargin=22, bottomMargin=24,
    )

    created_by = lead_task.assigned_to.get_full_name() or lead_task.assigned_to.username
    issue_date = timezone.now().strftime('%Y-%m-%d')
    payment_label = lead_task.get_payment_display() if lead_task.payment else '—'

    story = [
        _header_band('CLIENT INVOICE', f'Invoice #{lead_task.pk}  •  {lead.name}', styles),
        Spacer(1, 10),
        _company_bar(styles),
        Spacer(1, 14),
        _info_stack([
            ('Issue date', issue_date),
            ('Prepared by', created_by),
            ('Destination', lead.destination or '—'),
            ('Travel date', _fmt_date(lead_task.travel_date)),
            ('Return date', _fmt_date(lead_task.return_date)),
            ('Payment', payment_label),
            ('Channel', lead.channel or '—'),
        ], styles),
        Spacer(1, 16),
    ]

    story.extend(_section_heading('Client Details', styles))
    story.append(_info_stack([
        ('Name', lead.name),
        ('Phone', lead.phone),
        ('Email', getattr(lead, 'email', None)),
        ('Request details', lead.special_request),
        ('Date of birth', lead_task.date_of_birth.strftime('%Y-%m-%d') if lead_task.date_of_birth else None),
        ('Passport expiry', lead_task.passport_expiry_date.strftime('%Y-%m-%d') if lead_task.passport_expiry_date else None),
    ], styles))
    story.append(Spacer(1, 16))

    story.extend(_section_heading('Services', styles))
    if services:
        service_rows = [
            [str(idx), service.service_name or '—', service.details or '—']
            for idx, service in enumerate(services, 1)
        ]
    else:
        service_rows = [['—', 'No services on this invoice', '—']]
    story.append(_data_table(['#', 'Service', 'Details'], service_rows, col_widths=[0.7, 3, 8]))
    story.append(Spacer(1, 16))

    story.extend(_section_heading('Payments', styles))
    if payments:
        payment_rows = [
            [_fmt_date(payment.date), f'${payment.amount}', 'Yes' if payment.is_checked else 'No']
            for payment in payments
        ]
    else:
        payment_rows = [['—', '—', 'No payments']]
    story.append(_data_table(['Date', 'Amount', 'Received'], payment_rows, col_widths=[3, 3, 3]))
    story.append(Spacer(1, 16))

    total = lead.selling_price
    total_str = _money_display(total) if total not in (None, '') else 'N/A'
    story.append(_totals_table([], 'Total Selling Price', total_str))

    story.append(PageBreak())
    story.extend(_section_heading('Booking Terms & Travel Policy', styles))
    story.extend(_policy_paragraphs(CLIENT_POLICY_LINES, styles))

    doc.build(story)
    return response


def build_internal_invoice_pdf(*, response, lead_task, services, payments, attachments=None):
    """Staff-facing invoice PDF — modern layout with full booking and finance detail."""
    from tasks.constants import effective_service_net, parse_money, service_has_issue_override

    styles = _styles()
    lead = lead_task.lead
    doc = SimpleDocTemplate(
        response, pagesize=landscape(A4),
        leftMargin=28, rightMargin=28, topMargin=22, bottomMargin=24,
    )

    assigned = lead_task.assigned_to.get_full_name() or lead_task.assigned_to.username
    generated_at = timezone.now().strftime('%Y-%m-%d %H:%M')
    status_label = lead_task.get_status_display()
    payment_label = lead_task.get_payment_display() if lead_task.payment else '—'
    services_list = list(services)
    services_issued = sum(1 for s in services_list if s.is_checked)
    # Profit uses booking net only; post-issue profit uses issue prices when they differ.
    total_net = sum(parse_money(s.net) for s in services_list)
    total_selling = parse_money(lead.selling_price)
    total_profit = total_selling - total_net
    total_issue_net = sum(parse_money(effective_service_net(s)) for s in services_list)
    has_mismatch = any(service_has_issue_override(s) for s in services_list)
    post_issue_profit = total_selling - total_issue_net

    story = [
        _header_band('INTERNAL INVOICE', f'Invoice #{lead_task.pk}  •  {lead.name}  •  {status_label}', styles),
        Spacer(1, 10),
        _company_bar(styles),
        Spacer(1, 12),
        _meta_block(
            generated_at, None, styles,
            detail_lines=[f'<b>Assigned to:</b> {assigned} &nbsp;&nbsp; <b>Payment:</b> {payment_label}'],
        ),
        Spacer(1, 14),
        _info_stack([
            ('Travel date', _fmt_datetime(lead_task.travel_date)),
            ('Return date', _fmt_datetime(lead_task.return_date)),
            ('Services issued', f'{services_issued} / {len(services_list)}'),
            ('Lead created', _fmt_datetime(lead.created_at)),
            ('Last updated', _fmt_datetime(lead.last_modified)),
            ('Passengers', str(lead.passengers.count())),
        ], styles),
        Spacer(1, 16),
    ]

    story.extend(_section_heading('Invoice Details', styles))
    story.append(_info_stack([
        ('Status', status_label),
        ('Assigned to', assigned),
        ('Payment type', payment_label),
        ('Invoice notes', lead_task.notes),
        ('What happened', lead.finalization_notes),
    ], styles))
    story.append(Spacer(1, 16))

    passenger_names = [p.name for p in lead.passengers.all()]
    story.extend(_section_heading('Customer Details', styles))
    story.append(_info_stack([
        ('Name', lead.name),
        ('Phone', lead.phone),
        ('Email', getattr(lead, 'email', None)),
        ('Channel', lead.channel),
        ('Destination', lead.destination),
        ('Date of birth', lead_task.date_of_birth.strftime('%Y-%m-%d') if lead_task.date_of_birth else None),
        ('Passport expiry', lead_task.passport_expiry_date.strftime('%Y-%m-%d') if lead_task.passport_expiry_date else None),
        ('Request details', lead.special_request),
        ('Passengers', ', '.join(passenger_names) if passenger_names else None),
    ], styles))
    story.append(Spacer(1, 16))

    story.extend(_section_heading('Services', styles))
    if services_list:
        service_rows = [
            [
                service.service_name or '—',
                service.supplier or '—',
                service.details or '—',
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
        col_widths=[1.5, 1.3, 2.4, 0.9, 0.9, 1.0, 1.4, 1.2, 0.8, 0.8],
    ))
    story.append(Spacer(1, 16))

    story.extend(_section_heading('Finance Summary', styles))
    if has_mismatch:
        story.append(_totals_table(
            [
                ('Total net (services)', f'${total_net:,.2f}'),
                ('Total selling', _money_display(lead.selling_price)),
                ('Profit (net basis)', f'${total_profit:,.2f}'),
                ('Total net at issue price', f'${total_issue_net:,.2f}'),
            ],
            'Post Issue Profit',
            f'${post_issue_profit:,.2f}',
        ))
    else:
        story.append(_totals_table(
            [
                ('Total net (services)', f'${total_net:,.2f}'),
                ('Total selling', _money_display(lead.selling_price)),
            ],
            'Profit',
            f'${total_profit:,.2f}',
        ))
    story.append(Spacer(1, 16))

    story.extend(_section_heading('Payments', styles))
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
    story.append(_data_table(['Date', 'Amount', 'Received', 'Refund'], payment_rows, col_widths=[3, 2, 2, 2]))

    if attachments:
        story.append(Spacer(1, 16))
        story.extend(_section_heading('Attachments', styles))
        story.append(_data_table(
            ['File', 'Uploaded'],
            [[a.attachment_name or '—', _fmt_datetime(a.uploaded_at)] for a in attachments],
            col_widths=[6, 4],
        ))

    doc.build(story)
    return response
