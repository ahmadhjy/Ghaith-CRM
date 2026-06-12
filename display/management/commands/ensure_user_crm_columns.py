"""
Add missing auth_user columns used by User.add_to_class(): is_sales, administration.

Safe to run anytime (idempotent). Use on production if migrate was skipped or
management commands fail with "no such column: auth_user.is_sales".
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import connection


def existing_user_columns():
    table = User._meta.db_table
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, table)
        }


def ensure_columns():
    table = User._meta.db_table
    vendor = connection.vendor
    qn = connection.ops.quote_name
    existing = existing_user_columns()
    added = []

    for name in ('is_sales', 'administration'):
        if name in existing:
            continue
        if vendor == 'sqlite':
            sql = f'ALTER TABLE {qn(table)} ADD COLUMN {qn(name)} bool NOT NULL DEFAULT 0'
        else:
            sql = f'ALTER TABLE {qn(table)} ADD COLUMN {qn(name)} boolean NOT NULL DEFAULT false'
        with connection.cursor() as cursor:
            cursor.execute(sql)
        added.append(name)
        existing.add(name)

    return added


class Command(BaseCommand):
    help = 'Ensure auth_user has is_sales and administration columns.'

    def handle(self, *args, **options):
        added = ensure_columns()
        if added:
            self.stdout.write(self.style.SUCCESS(f'Added: {", ".join(added)}'))
        else:
            self.stdout.write('OK — is_sales and administration already exist.')
