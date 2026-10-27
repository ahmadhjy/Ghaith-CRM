from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0018_service_sort_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="attachment",
            name="sort_order",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AlterModelOptions(
            name="attachment",
            options={"ordering": ["sort_order", "pk"]},
        ),
    ]
