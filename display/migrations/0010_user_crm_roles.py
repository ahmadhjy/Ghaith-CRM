"""
Add CRM role columns on auth_user: is_sales and administration.

Uses ALTER TABLE so SQLite does not rebuild auth_user and drop columns that
exist only via User.add_to_class() (not on the historical auth.User model).
"""
from django.db import migrations, models


class AddAuthUserField(migrations.AddField):
    """AddField that targets auth.User (add_to_class fields on the stock user model)."""

    def state_forwards(self, app_label, state):
        super().state_forwards('auth', state)


def _existing_columns(schema_editor, table):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, table)
        }


def add_crm_role_columns(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    table = User._meta.db_table
    existing = _existing_columns(schema_editor, table)
    qn = schema_editor.quote_name

    if 'is_sales' not in existing:
        if schema_editor.connection.vendor == 'sqlite':
            schema_editor.execute(
                f'ALTER TABLE {qn(table)} ADD COLUMN {qn("is_sales")} bool NOT NULL DEFAULT 0'
            )
        else:
            schema_editor.execute(
                f'ALTER TABLE {qn(table)} ADD COLUMN {qn("is_sales")} boolean NOT NULL DEFAULT false'
            )

    existing = _existing_columns(schema_editor, table)
    if 'administration' not in existing:
        if schema_editor.connection.vendor == 'sqlite':
            schema_editor.execute(
                f'ALTER TABLE {qn(table)} ADD COLUMN {qn("administration")} bool NOT NULL DEFAULT 0'
            )
        else:
            schema_editor.execute(
                f'ALTER TABLE {qn(table)} ADD COLUMN {qn("administration")} boolean NOT NULL DEFAULT false'
            )


def remove_crm_role_columns(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    table = User._meta.db_table
    existing = _existing_columns(schema_editor, table)
    qn = schema_editor.quote_name

    if schema_editor.connection.vendor == 'sqlite':
        # SQLite < 3.35 cannot DROP COLUMN; leave columns on downgrade for sqlite.
        return

    if 'administration' in existing:
        schema_editor.execute(
            f'ALTER TABLE {qn(table)} DROP COLUMN {qn("administration")}'
        )
    if 'is_sales' in existing:
        schema_editor.execute(
            f'ALTER TABLE {qn(table)} DROP COLUMN {qn("is_sales")}'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('display', '0009_leadpassenger'),
        ('notifications', '0002_user_administration'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                AddAuthUserField(
                    model_name='user',
                    name='is_sales',
                    field=models.BooleanField(default=False),
                ),
                AddAuthUserField(
                    model_name='user',
                    name='administration',
                    field=models.BooleanField(
                        default=False,
                        help_text='Receives client and supplier payment due notifications.',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_crm_role_columns, remove_crm_role_columns),
            ],
        ),
    ]
