import re

from .models import Lead


def digits_only(value):
    return re.sub(r'\D', '', value or '')


def build_full_phone(country_code, phone):
    phone = (phone or '').strip()
    country_code = (country_code or '').strip()
    if not phone:
        return ''
    if phone.startswith('+'):
        return phone
    if country_code:
        return f"{country_code}{phone}"
    return phone


def local_phone_part(country_code, stored_phone):
    """Return the local part of a stored full phone for form display."""
    full = (stored_phone or '').strip()
    cc = (country_code or '').strip()
    if cc and full.startswith(cc):
        return full[len(cc):]
    cc_digits = digits_only(cc)
    full_digits = digits_only(full)
    if cc_digits and full_digits.startswith(cc_digits):
        return full_digits[len(cc_digits):]
    return full


def find_duplicate_leads(country_code, phone, exclude_pk=None):
    """
    Find leads that share the same phone number, tolerating format differences
    (+961…, 961…, local-only, etc.).
    """
    raw = (phone or '').strip()
    if raw.startswith('+'):
        local_digits = digits_only(local_phone_part(country_code, raw))
    else:
        local_digits = digits_only(raw)
    full_digits = digits_only(build_full_phone(country_code, phone))

    if not local_digits:
        return []

    qs = Lead.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    duplicates = []
    seen = set()
    for lead in qs:
        lead_digits = digits_only(lead.phone)
        if not lead_digits:
            continue
        matched = False
        if full_digits and lead_digits == full_digits:
            matched = True
        elif len(local_digits) >= 7 and (
            lead_digits == local_digits or lead_digits.endswith(local_digits)
        ):
            matched = True
        if matched and lead.pk not in seen:
            duplicates.append(lead)
            seen.add(lead.pk)
    return duplicates
