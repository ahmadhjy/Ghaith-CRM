from django.db import migrations

GHAITH = {
    'name': 'Ghaith Travel',
    'address': 'Bechara El Khoury Highway, Beirut, Lebanon',
    'phone': '+961-81456406',
    'email': 'info@ghaithtravel.com',
    'footer_text': '© Ghaith Travel. All rights reserved.',
    'default_currency': 'USD',
}

STALE = {'', 'BEIRUT HAZMIEH', 'SAMA TOURS TRAVEL & TOURISM', 'Sama Tours'}


def apply_ghaith_branding(apps, schema_editor):
    CompanyBranding = apps.get_model('accounts_core', 'CompanyBranding')
    obj, _ = CompanyBranding.objects.get_or_create(pk=1)
    changed = False
    for field, value in GHAITH.items():
        current = (getattr(obj, field, '') or '').strip()
        lower = current.lower()
        if not current or current in STALE or 'sama' in lower:
            setattr(obj, field, value)
            changed = True
    if changed:
        obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts_core', '0012_userprofile_is_accountant'),
    ]

    operations = [
        migrations.RunPython(apply_ghaith_branding, migrations.RunPython.noop),
    ]
