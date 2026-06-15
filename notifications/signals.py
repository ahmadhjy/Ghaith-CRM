from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from display.models import Lead
from tasks.models import LeadTask

from .services import notify_lead_assigned, notify_leadtask_assigned, notify_takeover_lead


@receiver(pre_save, sender=Lead)
def _remember_lead_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Lead.objects.get(pk=instance.pk)
            instance._prev_takeover = old.takeover
            instance._prev_assigned_to_id = old.assigned_to_id
        except Lead.DoesNotExist:
            instance._prev_takeover = False
            instance._prev_assigned_to_id = None
    else:
        instance._prev_takeover = False
        instance._prev_assigned_to_id = None


@receiver(post_save, sender=Lead)
def lead_notifications(sender, instance, created, **kwargs):
    prev_takeover = getattr(instance, '_prev_takeover', False)

    if instance.takeover:
        if created or (not prev_takeover and instance.takeover):
            notify_takeover_lead(instance)
        return

    prev_assigned = getattr(instance, '_prev_assigned_to_id', None)
    if not instance.assigned_to_id:
        return
    if prev_takeover and not instance.takeover:
        notify_lead_assigned(instance)
    elif created or prev_assigned != instance.assigned_to_id:
        notify_lead_assigned(instance)


@receiver(pre_save, sender=LeadTask)
def _remember_leadtask_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = LeadTask.objects.get(pk=instance.pk)
            instance._prev_assigned_to_id = old.assigned_to_id
        except LeadTask.DoesNotExist:
            instance._prev_assigned_to_id = None
    else:
        instance._prev_assigned_to_id = None


@receiver(post_save, sender=LeadTask)
def leadtask_calendar_sync(sender, instance, **kwargs):
    from tasks.calendar_sync import sync_travel_event
    sync_travel_event(instance)


@receiver(post_save, sender=LeadTask)
def leadtask_assigned_notification(sender, instance, created, **kwargs):
    prev_assigned = getattr(instance, '_prev_assigned_to_id', None)
    if instance.assigned_to_id and (created or prev_assigned != instance.assigned_to_id):
        notify_leadtask_assigned(instance)
