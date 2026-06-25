import logging

from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from sales.models import SalesInvoiceLine
from tasks.models import LeadTask, Service, ServiceType, Supplier

from accounting_bridge.models import AccountingConfig
from accounting_bridge.services.invoices import sync_crm_leadtask_to_accounting
from accounting_bridge.services.line_flags_sync import push_accounting_line_flags_to_crm
from accounting_bridge.services.master_data import (
    sync_all_crm_master_data,
    sync_employee_from_user,
    sync_master_data_from_leadtask,
    sync_master_data_from_service,
    sync_service_type,
    sync_supplier,
)

logger = logging.getLogger(__name__)


def _master_sync_enabled():
    return AccountingConfig.load().master_data_sync_enabled


def _safe_sync(label, fn, *args, **kwargs):
    if not _master_sync_enabled():
        return
    try:
        fn(*args, **kwargs)
    except Exception:
        logger.exception('Accounting sync failed (%s)', label)


@receiver(post_save, sender=User)
def sync_user_to_accounting_employee(sender, instance, **kwargs):
    _safe_sync('user', sync_employee_from_user, instance)


@receiver(post_save, sender=Supplier)
def sync_crm_supplier_row(sender, instance, **kwargs):
    _safe_sync('supplier', sync_supplier, instance.name)


@receiver(post_save, sender=ServiceType)
def sync_crm_service_type_row(sender, instance, **kwargs):
    _safe_sync('service_type', sync_service_type, instance.name)


@receiver(post_save, sender=LeadTask)
def sync_on_leadtask_save(sender, instance, **kwargs):
    _safe_sync('leadtask', sync_crm_leadtask_to_accounting, instance)


@receiver(post_save, sender=Service)
def sync_on_service_change(sender, instance, **kwargs):
    if not instance.leadtask_id:
        return
    _safe_sync('service', sync_crm_leadtask_to_accounting, instance.leadtask)


@receiver(post_delete, sender=Service)
def sync_on_service_delete(sender, instance, **kwargs):
    if not instance.leadtask_id:
        return
    try:
        leadtask = LeadTask.objects.get(pk=instance.leadtask_id)
    except LeadTask.DoesNotExist:
        return
    _safe_sync('service_delete', sync_crm_leadtask_to_accounting, leadtask)


@receiver(post_save, sender=SalesInvoiceLine)
def sync_accounting_line_flags_to_crm(sender, instance, **kwargs):
    """Push issued / sent-to-client / issue price from accounting back to CRM service rows."""
    if not _master_sync_enabled():
        return
    try:
        push_accounting_line_flags_to_crm(instance)
    except Exception:
        logger.exception('Failed to push accounting line flags to CRM service %s', instance.pk)


def run_initial_master_data_sync():
    return sync_all_crm_master_data()
