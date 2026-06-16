from django.db import migrations


def seed_client_policy(apps, schema_editor):
    PdfPolicy = apps.get_model('tasks', 'PdfPolicy')
    if PdfPolicy.objects.filter(show_on_client_invoice=True).exists():
        return
    from tasks.pdf_policy import DEFAULT_CLIENT_POLICY_HTML

    PdfPolicy.objects.create(
        title='Booking Terms & Travel Policy',
        content=DEFAULT_CLIENT_POLICY_HTML,
        show_on_client_invoice=True,
        is_active=True,
        sort_order=0,
    )


def unseed_client_policy(apps, schema_editor):
    PdfPolicy = apps.get_model('tasks', 'PdfPolicy')
    PdfPolicy.objects.filter(
        title='Booking Terms & Travel Policy',
        show_on_client_invoice=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0008_pdf_policy'),
    ]

    operations = [
        migrations.RunPython(seed_client_policy, unseed_client_policy),
    ]
