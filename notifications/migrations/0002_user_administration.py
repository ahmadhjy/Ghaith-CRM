from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='administration',
            field=models.BooleanField(
                default=False,
                help_text='Receives payment due notifications (client and supplier).',
            ),
        ),
    ]
