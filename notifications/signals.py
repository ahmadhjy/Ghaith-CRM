from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from display.models import Lead
from tasks.models import ClientMediaFile

from .services import notify_media_upload, notify_takeover_lead


@receiver(pre_save, sender=Lead)
def _remember_takeover_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Lead.objects.get(pk=instance.pk)
            instance._prev_takeover = old.takeover
        except Lead.DoesNotExist:
            instance._prev_takeover = False
    else:
        instance._prev_takeover = False


@receiver(post_save, sender=Lead)
def lead_takeover_notification(sender, instance, created, **kwargs):
    if not instance.takeover:
        return
    prev = getattr(instance, '_prev_takeover', False)
    if created or (not prev and instance.takeover):
        notify_takeover_lead(instance)


@receiver(post_save, sender=ClientMediaFile)
def client_media_upload_notification(sender, instance, created, **kwargs):
    if created:
        notify_media_upload(instance)
