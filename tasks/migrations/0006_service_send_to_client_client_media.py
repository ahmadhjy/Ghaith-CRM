import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0005_supplier'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='send_to_client',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='ClientMediaUploadLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('client_name', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('leadtask', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='media_upload_links', to='tasks.leadtask')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ClientMediaFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='static/client_media/%Y/%m/%d/')),
                ('original_name', models.CharField(max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('upload_link', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='tasks.clientmediauploadlink')),
            ],
        ),
    ]
