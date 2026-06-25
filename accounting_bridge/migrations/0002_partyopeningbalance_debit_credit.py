from decimal import Decimal

from django.db import migrations, models


def migrate_amount_to_debit_credit(apps, schema_editor):
    PartyOpeningBalance = apps.get_model('accounting_bridge', 'PartyOpeningBalance')
    for row in PartyOpeningBalance.objects.all():
        amount = row.amount_usd or Decimal('0.00')
        if amount <= 0:
            continue
        if row.party_type == 'CLIENT':
            row.debit_usd = amount
            row.credit_usd = Decimal('0.00')
        else:
            row.debit_usd = Decimal('0.00')
            row.credit_usd = amount
        row.save(update_fields=['debit_usd', 'credit_usd'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounting_bridge', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='partyopeningbalance',
            name='credit_usd',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Credit side of opening balance (USD).',
                max_digits=14,
            ),
        ),
        migrations.AddField(
            model_name='partyopeningbalance',
            name='debit_usd',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Debit side of opening balance (USD).',
                max_digits=14,
            ),
        ),
        migrations.RunPython(migrate_amount_to_debit_credit, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='partyopeningbalance',
            name='amount_usd',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Legacy net amount; kept in sync from debit/credit on save.',
                max_digits=14,
            ),
        ),
    ]
