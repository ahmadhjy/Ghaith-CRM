import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class AccountingConfig(models.Model):
    """Singleton settings for CRM ↔ accounting integration."""

    invoice_sync_from = models.DateField(
        default=timezone.localdate,
        help_text='CRM orders created on or after this date auto-sync to accounting invoices.',
    )
    master_data_sync_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Accounting integration settings'

    def __str__(self):
        return 'Accounting integration settings'

    @classmethod
    def load(cls):
        row, _ = cls.objects.get_or_create(pk=1)
        return row

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class LeadClientLink(models.Model):
    lead = models.OneToOneField('display.Lead', on_delete=models.CASCADE, related_name='accounting_client_link')
    client = models.OneToOneField(
        'accounts_core.Client', on_delete=models.CASCADE, related_name='crm_lead_link'
    )
    phone_key = models.CharField(max_length=32, db_index=True, help_text='Normalized phone digits for matching.')
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lead → client link'

    def __str__(self):
        return f'{self.lead_id} → {self.client.client_code}'


class CrmSupplierLink(models.Model):
    crm_supplier = models.OneToOneField(
        'tasks.Supplier', on_delete=models.CASCADE, related_name='accounting_link'
    )
    acc_supplier = models.OneToOneField(
        'accounts_core.Supplier', on_delete=models.CASCADE, related_name='crm_supplier_link'
    )
    synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.crm_supplier.name} → {self.acc_supplier.supplier_code}'


class CrmDestinationLink(models.Model):
    destination_name = models.CharField(max_length=200, unique=True)
    acc_destination = models.ForeignKey(
        'catalog.Destination', on_delete=models.CASCADE, related_name='crm_links'
    )
    synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.destination_name


class CrmServiceTypeLink(models.Model):
    crm_service_type = models.OneToOneField(
        'tasks.ServiceType', on_delete=models.CASCADE, related_name='accounting_link'
    )
    acc_service_type = models.OneToOneField(
        'catalog.ServiceType', on_delete=models.CASCADE, related_name='crm_service_type_link'
    )
    synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.crm_service_type.name} → {self.acc_service_type.name}'


class CrmEmployeeLink(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounting_employee_link')
    employee = models.OneToOneField(
        'accounts_core.Employee', on_delete=models.CASCADE, related_name='crm_user_link'
    )
    synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} → {self.employee.name}'


class PartyOpeningBalance(models.Model):
    class PartyType(models.TextChoices):
        CLIENT = 'CLIENT', 'Client'
        SUPPLIER = 'SUPPLIER', 'Supplier'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    party_type = models.CharField(max_length=10, choices=PartyType.choices)
    client = models.ForeignKey(
        'accounts_core.Client', null=True, blank=True, on_delete=models.CASCADE, related_name='opening_balances'
    )
    supplier = models.ForeignKey(
        'accounts_core.Supplier', null=True, blank=True, on_delete=models.CASCADE, related_name='opening_balances'
    )
    as_of_date = models.DateField(default=timezone.localdate)
    debit_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Debit side of opening balance (USD).',
    )
    credit_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Credit side of opening balance (USD).',
    )
    amount_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Legacy net amount; kept in sync from debit/credit on save.',
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='opening_balances_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-as_of_date', '-created_at']

    def net_balance_usd(self) -> Decimal:
        """Client: debit − credit (they owe you). Supplier: credit − debit (you owe them)."""
        debit = self.debit_usd or Decimal('0.00')
        credit = self.credit_usd or Decimal('0.00')
        if self.party_type == self.PartyType.SUPPLIER:
            return credit - debit
        return debit - credit

    def save(self, *args, **kwargs):
        self.amount_usd = self.net_balance_usd().quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        party = self.client or self.supplier
        return f'{self.party_type} opening D{self.debit_usd} C{self.credit_usd} ({party})'


class InvoiceSyncQueue(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = 'PENDING_REVIEW', 'Pending review'
        APPROVED = 'APPROVED', 'Approved (draft in accounting)'
        REJECTED = 'REJECTED', 'Rejected'
        PUBLISHED = 'PUBLISHED', 'Published in accounting'
        SKIPPED = 'SKIPPED', 'Skipped'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leadtask = models.OneToOneField('tasks.LeadTask', on_delete=models.CASCADE, related_name='accounting_sync')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_REVIEW)
    sales_invoice = models.OneToOneField(
        'sales.SalesInvoice',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='crm_sync_queue',
    )
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_invoice_syncs',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    last_crm_snapshot_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'CRM invoice sync queue'
        verbose_name_plural = 'CRM invoice sync queue'

    def __str__(self):
        return f'Invoice sync #{self.leadtask_id} ({self.status})'
