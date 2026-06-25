from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts_core', '0011_alter_client_contact_person_alter_client_name_en'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_accountant',
            field=models.BooleanField(
                default=False,
                help_text='Allow access to the embedded accounting module and accounting admin models.',
            ),
        ),
    ]
