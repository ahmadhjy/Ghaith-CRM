from django.db import migrations, models


def add_administration_field(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    field = models.BooleanField(default=False)
    field.set_attributes_from_name('administration')
    schema_editor.add_field(User, field)


def remove_administration_field(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    field = models.BooleanField(default=False)
    field.set_attributes_from_name('administration')
    schema_editor.remove_field(User, field)


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_administration_field, remove_administration_field),
    ]
