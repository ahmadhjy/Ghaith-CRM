from django.db.models.signals import post_save
from django.dispatch import receiver

from display.models import Lead


@receiver(post_save, sender=Lead)
def sync_lead_followup_calendar(sender, instance, **kwargs):
    if instance.status == 'followup' and instance.follow_up:
        from tasks.calendar_sync import sync_followup_event
        sync_followup_event(instance)
    elif instance.pk:
        from dashboard.models import Event
        if instance.status != 'followup':
            Event.objects.filter(lead=instance, event_type='invoice').delete()
