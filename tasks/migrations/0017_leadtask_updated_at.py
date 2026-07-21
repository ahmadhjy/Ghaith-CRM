from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0016_seed_all_default_service_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadtask",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
