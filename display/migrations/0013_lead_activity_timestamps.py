from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0012_seed_departments_and_profiles"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="last_agent_action_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last CRM agent action synced from the WhatsApp dashboard.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="last_customer_message_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last inbound customer message time from the WhatsApp dashboard.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="lead",
            name="destination",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
