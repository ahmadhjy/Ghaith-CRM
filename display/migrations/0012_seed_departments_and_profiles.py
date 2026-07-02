from django.db import migrations


DEPARTMENT_DEFINITIONS = [
    ("reservation", "Reservation Department"),
    ("honeymoon_far_east", "Honeymoon & Far East Department"),
    ("sharm", "Sharm Department"),
    ("civil_marriage", "Civil Marriage Department"),
    ("turkey", "Turkey Department"),
]


def seed_departments(apps, schema_editor):
    Department = apps.get_model("display", "Department")
    for sort_order, (code, name) in enumerate(DEPARTMENT_DEFINITIONS):
        Department.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_active": True, "sort_order": sort_order},
        )


def backfill_crm_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    CrmUserProfile = apps.get_model("display", "CrmUserProfile")
    for user in User.objects.all().iterator():
        CrmUserProfile.objects.get_or_create(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0011_department_lead_chat_summary_lead_external_id_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_departments, migrations.RunPython.noop),
        migrations.RunPython(backfill_crm_profiles, migrations.RunPython.noop),
    ]
