# Generated manually for Event.service (link to tasks.Service)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_leadtask_date_of_birth_leadtask_passport_expiry_date'),
        ('dashboard', '0003_event_done'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='service',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='calendar_event',
                to='tasks.service',
            ),
        ),
    ]
