from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0017_leadtask_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="sort_order",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
    ]
