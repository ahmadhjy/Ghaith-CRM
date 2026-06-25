from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0016_salesinvoiceline_crm_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesinvoiceline',
            name='send_to_client',
            field=models.BooleanField(
                default=False,
                help_text='Mirrors CRM Send to client on the service line.',
            ),
        ),
        migrations.AddField(
            model_name='salesinvoiceline',
            name='crm_issued',
            field=models.BooleanField(
                default=False,
                help_text='Mirrors CRM Issued (is_checked) on the service line.',
            ),
        ),
    ]
