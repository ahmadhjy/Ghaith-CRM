"""Admin-managed PDF policy blocks (rich HTML → ReportLab flowables)."""
import html
import re
from html import unescape

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import ListFlowable, ListItem, Paragraph, Spacer

PDF_TARGET_CLIENT_INVOICE = 'client_invoice'
PDF_TARGET_INTERNAL_INVOICE = 'internal_invoice'
PDF_TARGET_PURCHASES_REPORT = 'purchases_report'
PDF_TARGET_CLIENT_PAYMENTS_REPORT = 'client_payments_report'
PDF_TARGET_TRAVELLERS_REPORT = 'travellers_report'

PDF_TARGET_LABELS = {
    PDF_TARGET_CLIENT_INVOICE: 'Client invoice PDF',
    PDF_TARGET_INTERNAL_INVOICE: 'Internal invoice PDF',
    PDF_TARGET_PURCHASES_REPORT: 'Purchases report PDF',
    PDF_TARGET_CLIENT_PAYMENTS_REPORT: 'Client payments report PDF',
    PDF_TARGET_TRAVELLERS_REPORT: 'Travellers report PDF',
}

PDF_TARGET_FIELD = {
    PDF_TARGET_CLIENT_INVOICE: 'show_on_client_invoice',
    PDF_TARGET_INTERNAL_INVOICE: 'show_on_internal_invoice',
    PDF_TARGET_PURCHASES_REPORT: 'show_on_purchases_report',
    PDF_TARGET_CLIENT_PAYMENTS_REPORT: 'show_on_client_payments_report',
    PDF_TARGET_TRAVELLERS_REPORT: 'show_on_travellers_report',
}

DEFAULT_CLIENT_POLICY_LINES = [
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


def lines_to_policy_html(lines):
    """Convert plain-text policy lines to simple HTML for the rich editor seed."""
    parts = []
    for line in lines:
        text = line.strip()
        if not text:
            parts.append('<p>&nbsp;</p>')
            continue
        if text.startswith('- '):
            parts.append(f'<p>• {html.escape(text[2:])}</p>')
        elif re.match(r'^\d+\.\s', text):
            parts.append(f'<p><strong>{html.escape(text)}</strong></p>')
        else:
            parts.append(f'<p>{html.escape(text)}</p>')
    return '\n'.join(parts)


DEFAULT_CLIENT_POLICY_HTML = lines_to_policy_html(DEFAULT_CLIENT_POLICY_LINES)


def get_pdf_policies(target):
    from tasks.models import PdfPolicy

    field = PDF_TARGET_FIELD.get(target)
    if not field:
        return PdfPolicy.objects.none()
    return PdfPolicy.objects.filter(is_active=True, **{field: True}).order_by('sort_order', 'pk')


def _normalize_inline_html(fragment):
    fragment = unescape(fragment or '')
    fragment = re.sub(r'<strong\b[^>]*>', '<b>', fragment, flags=re.I)
    fragment = re.sub(r'</strong>', '</b>', fragment, flags=re.I)
    fragment = re.sub(r'<em\b[^>]*>', '<i>', fragment, flags=re.I)
    fragment = re.sub(r'</em>', '</i>', fragment, flags=re.I)
    fragment = re.sub(r'<br\s*/?>', '<br/>', fragment, flags=re.I)

    def _tag_replacer(match):
        tag = match.group(1).lower()
        if tag in ('b', 'i', 'u', 'br'):
            return match.group(0)
        if match.group(0).startswith('</'):
            return ''
        return ''

    fragment = re.sub(r'</?([a-z0-9]+)\b[^>]*>', _tag_replacer, fragment, flags=re.I)
    fragment = fragment.replace('&', '&amp;')
    fragment = fragment.replace('&amp;amp;', '&amp;')
    fragment = fragment.replace('&amp;lt;', '&lt;').replace('&amp;gt;', '&gt;')
    fragment = fragment.replace('<b>', '\x00B\x00').replace('</b>', '\x01/B\x01')
    fragment = fragment.replace('<i>', '\x00I\x00').replace('</i>', '\x01/I\x01')
    fragment = fragment.replace('<u>', '\x00U\x00').replace('</u>', '\x01/U\x01')
    fragment = fragment.replace('<br/>', '\x00BR\x00')
    fragment = html.escape(fragment)
    fragment = fragment.replace('\x00B\x00', '<b>').replace('\x01/B\x01', '</b>')
    fragment = fragment.replace('\x00I\x00', '<i>').replace('\x01/I\x01', '</i>')
    fragment = fragment.replace('\x00U\x00', '<u>').replace('\x01/U\x01', '</u>')
    fragment = fragment.replace('\x00BR\x00', '<br/>')
    return fragment.strip()


def html_to_policy_flowables(html_content, base_style):
    """Turn CKEditor HTML into ReportLab paragraphs and lists."""
    if not (html_content or '').strip():
        return []

    content = html_content.strip()
    flowables = []
    heading_style = ParagraphStyle(
        'PolicyHeading', parent=base_style,
        fontName='Helvetica-Bold', fontSize=base_style.fontSize + 1.5,
        leading=base_style.leading + 2, spaceBefore=8, spaceAfter=4,
    )
    bullet_style = ParagraphStyle(
        'PolicyBullet', parent=base_style, leftIndent=12, bulletIndent=0, spaceBefore=2,
    )

    ul_blocks = re.findall(r'<ul[^>]*>(.*?)</ul>', content, flags=re.I | re.DOTALL)
    for ul_inner in ul_blocks:
        items = re.findall(r'<li[^>]*>(.*?)</li>', ul_inner, flags=re.I | re.DOTALL)
        if items:
            list_items = [
                ListItem(Paragraph(_normalize_inline_html(item) or '&nbsp;', bullet_style))
                for item in items
            ]
            flowables.append(ListFlowable(list_items, bulletType='bullet', leftIndent=14))
            flowables.append(Spacer(1, 4))

    content_no_lists = re.sub(r'<ul[^>]*>.*?</ul>', '', content, flags=re.I | re.DOTALL)
    blocks = re.findall(
        r'<(p|h[1-6])[^>]*>(.*?)</\1>',
        content_no_lists,
        flags=re.I | re.DOTALL,
    )

    if blocks:
        for tag, inner in blocks:
            inner_html = _normalize_inline_html(inner)
            if not inner_html or inner_html == '&nbsp;':
                flowables.append(Spacer(1, 6))
                continue
            if tag.lower().startswith('h'):
                flowables.append(Paragraph(inner_html, heading_style))
            else:
                flowables.append(Paragraph(inner_html, base_style))
        return flowables

    plain = re.sub(r'<[^>]+>', '\n', content)
    plain = unescape(plain)
    for line in plain.splitlines():
        text = line.strip()
        if text:
            flowables.append(Paragraph(html.escape(text), base_style))
        else:
            flowables.append(Spacer(1, 6))
    return flowables


def append_policies_to_story(story, target, styles, section_heading_fn):
    """Append all active policies for a PDF target to a ReportLab story."""
    policies = list(get_pdf_policies(target))
    if not policies:
        return
    for policy in policies:
        story.extend(section_heading_fn(policy.title, styles))
        story.extend(html_to_policy_flowables(policy.content, styles['policy']))
        story.append(Spacer(1, 12))
