from decimal import Decimal, InvalidOperation

from display.phone_utils import digits_only


def parse_money(value) -> Decimal:
    if value is None:
        return Decimal('0.00')
    cleaned = str(value).replace(',', '').replace('$', '').strip()
    if not cleaned:
        return Decimal('0.00')
    try:
        return Decimal(cleaned).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return Decimal('0.00')


def normalize_phone_key(phone: str) -> str:
    return digits_only(phone or '')


CRM_PACKAGE_TYPE_MAP = {
    'hotel': 'HOTEL',
    'ticket': 'TICKET',
    'visa': 'VISA',
    'package': 'FULL_PACKAGE',
    'travel insurance': 'INSURANCE',
}
