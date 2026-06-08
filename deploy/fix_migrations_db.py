#!/usr/bin/env python
"""Insert missing django_migrations records (PostgreSQL or SQLite)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ghaithleads.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

MIGRATIONS = [
    ("tasks", "0002_leadtask_date_of_birth_leadtask_passport_expiry_date"),
    ("tasks", "0003_leadtask_return_date"),
    ("tasks", "0004_alter_leadtask_status"),
    ("tasks", "0005_supplier"),
    ("display", "0002_alter_lead_destination"),
    ("display", "0003_lead_special_takeover"),
    ("display", "0004_dailyreport_modified_leads_today"),
    ("display", "0005_lead_net_alter_lead_channel_alter_lead_duration_and_more"),
    ("display", "0006_lead_email_crmnotification"),
    ("display", "0007_alter_lead_destination"),
]

vendor = connection.vendor
if vendor == "postgresql":
    insert_sql = """
        INSERT INTO django_migrations (app, name, applied)
        SELECT %s, %s, NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM django_migrations WHERE app = %s AND name = %s
        )
    """
elif vendor == "sqlite":
    insert_sql = """
        INSERT INTO django_migrations (app, name, applied)
        SELECT %s, %s, datetime('now')
        WHERE NOT EXISTS (
            SELECT 1 FROM django_migrations WHERE app = %s AND name = %s
        )
    """
else:
    print(f"Unsupported database vendor: {vendor}", file=sys.stderr)
    sys.exit(1)

inserted = 0
with connection.cursor() as cursor:
    for app, name in MIGRATIONS:
        cursor.execute(insert_sql, [app, name, app, name])
        if cursor.rowcount:
            inserted += 1
            print(f"  + {app}.{name}")

print(f"Done. Inserted {inserted} migration record(s) on {vendor}.")
