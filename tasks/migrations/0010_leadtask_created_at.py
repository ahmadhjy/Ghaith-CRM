from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0009_seed_client_pdf_policy'),
    ]

    operations = [
        migrations.AddField(
            model_name='leadtask',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
