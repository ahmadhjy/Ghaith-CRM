# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_leadtask_date_of_birth_leadtask_passport_expiry_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='leadtask',
            name='return_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
