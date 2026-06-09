from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0007_alter_lead_destination'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='other_passengers',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Additional travelers (companions, company members, etc.)',
            ),
        ),
    ]
