from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from tasks.babylon_sync import is_babylon_supplier, sync_entry_from_service, sync_service_from_entry
from tasks.models import BabylonHotelEntry, Service


@receiver(pre_save, sender=Service)
def babylon_remove_entry_when_supplier_changes(sender, instance, **kwargs):
    if not instance.pk or is_babylon_supplier(instance.supplier):
        return
    try:
        previous = Service.objects.get(pk=instance.pk)
    except Service.DoesNotExist:
        return
    if is_babylon_supplier(previous.supplier):
        BabylonHotelEntry.objects.filter(service_id=instance.pk).delete()


@receiver(post_save, sender=Service)
def babylon_sync_on_service_save(sender, instance, **kwargs):
    if getattr(instance, '_babylon_skip_sync', False):
        return
    sync_entry_from_service(instance)


@receiver(post_delete, sender=Service)
def babylon_sync_on_service_delete(sender, instance, **kwargs):
    BabylonHotelEntry.objects.filter(service_id=instance.pk).delete()


@receiver(post_save, sender=BabylonHotelEntry)
def babylon_sync_on_entry_save(sender, instance, **kwargs):
    if getattr(instance, '_babylon_skip_sync', False):
        return
    sync_service_from_entry(instance)
