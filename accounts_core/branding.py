"""Company branding for PDF exports (DB singleton with settings fallback)."""

from pathlib import Path

from django.conf import settings
from django.templatetags.static import static

from display.company_info import GHAITH_COMPANY


def get_company_branding(request=None):
    from accounts_core.models import CompanyBranding

    row = CompanyBranding.load()
    name = row.name or getattr(settings, 'COMPANY_LEGAL_NAME', '') or GHAITH_COMPANY['name']
    address = row.address or getattr(settings, 'COMPANY_ADDRESS', '') or GHAITH_COMPANY['address']
    phone = row.phone or getattr(settings, 'COMPANY_PHONE', '') or GHAITH_COMPANY['phone']
    email = row.email or getattr(settings, 'COMPANY_EMAIL', '') or GHAITH_COMPANY['email']
    financial_account_number = row.financial_account_number or getattr(
        settings, 'COMPANY_FINANCIAL_ACCOUNT', ''
    )
    footer_text = row.footer_text or getattr(settings, 'COMPANY_FOOTER_TEXT', '') or GHAITH_COMPANY['footer_text']
    tagline = getattr(settings, 'COMPANY_TAGLINE', '') or GHAITH_COMPANY['tagline']
    default_currency = row.default_currency or getattr(
        settings, 'COMPANY_DEFAULT_CURRENCY', GHAITH_COMPANY['default_currency']
    )

    logo_url = None
    logo_path = None
    if row.logo:
        try:
            path = Path(row.logo.path)
            if path.is_file():
                logo_path = str(path)
        except (ValueError, OSError):
            pass
        if not logo_path:
            url = row.logo.url
            logo_url = request.build_absolute_uri(url) if request else url

    favicon = settings.BASE_DIR / 'static' / 'img' / 'favicon.svg'
    if not logo_path and favicon.is_file():
        logo_path = str(favicon)

    if logo_path and Path(logo_path).is_file():
        logo_url = Path(logo_path).as_uri()
    elif not logo_url:
        rel = static('img/favicon.svg')
        logo_url = request.build_absolute_uri(rel) if request else rel

    return {
        'name': name,
        'address': address,
        'phone': phone,
        'email': email,
        'financial_account_number': financial_account_number,
        'footer_text': footer_text,
        'tagline': tagline,
        'default_currency': default_currency,
        'logo_url': logo_url,
        'logo_path': logo_path,
        'has_uploaded_logo': bool(row.logo),
    }
