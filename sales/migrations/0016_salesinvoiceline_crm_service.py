from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0009_seed_client_pdf_policy'),
        ('sales', '0015_salesinvoiceline_notes_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesinvoiceline',
            name='crm_service',
            field=models.OneToOneField(
                blank=True,
                help_text='CRM service row this line mirrors (set by accounting bridge).',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='accounting_line',
                to='tasks.service',
            ),
        ),
    ]
