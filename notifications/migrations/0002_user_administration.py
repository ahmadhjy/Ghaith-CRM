from django.db import migrations, models


def _existing_columns(schema_editor, table):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, table)
        }


def add_administration_field(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    table = User._meta.db_table
    if 'administration' in _existing_columns(schema_editor, table):
        return

    qn = schema_editor.quote_name
    if schema_editor.connection.vendor == 'sqlite':
        schema_editor.execute(
            f'ALTER TABLE {qn(table)} ADD COLUMN {qn("administration")} bool NOT NULL DEFAULT 0'
        )
    else:
        schema_editor.execute(
            f'ALTER TABLE {qn(table)} ADD COLUMN {qn("administration")} boolean NOT NULL DEFAULT false'
        )


def remove_administration_field(apps, schema_editor):
    if schema_editor.connection.vendor == 'sqlite':
        return
    User = apps.get_model('auth', 'User')
    table = User._meta.db_table
    qn = schema_editor.quote_name
    if 'administration' in _existing_columns(schema_editor, table):
        schema_editor.execute(
            f'ALTER TABLE {qn(table)} DROP COLUMN {qn("administration")}'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_administration_field, remove_administration_field),
    ]
