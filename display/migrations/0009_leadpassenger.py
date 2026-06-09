import re

from django.db import migrations, models
import django.db.models.deletion


def migrate_text_passengers(apps, schema_editor):
    Lead = apps.get_model('display', 'Lead')
    LeadPassenger = apps.get_model('display', 'LeadPassenger')
    for lead in Lead.objects.all():
        text = getattr(lead, 'other_passengers', '') or ''
        if not text.strip():
            continue
        names = [n.strip() for n in re.split(r'[,;\n]+', text) if n.strip()]
        for name in names:
            LeadPassenger.objects.create(lead=lead, name=name[:100])


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0008_lead_other_passengers'),
    ]

    operations = [
        migrations.CreateModel(
            name='LeadPassenger',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='passengers', to='display.lead')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.RunPython(migrate_text_passengers, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='lead',
            name='other_passengers',
        ),
    ]
