from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class Event(models.Model):

    TYPE_CHOICES = [
        ('user', 'Travel date reminder'),
        ('invoice', 'Follow-up reminder'),
        ('task', 'Payment Due Date'),
        ('followup', 'Supplier Payment'),
        ('anniversary', 'Birthday Anniversary'),  # New Event Type
    ]
    event_type = models.CharField(max_length=50,
                                  choices=TYPE_CHOICES,
                                   default='user')

    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name="events")
    title = models.CharField(max_length=200)
    description = models.TextField()
    when = models.DateField()
    done = models.BooleanField(default=False)
    # Link to tasks.Service: when service is deleted, this event is deleted (for new service-created events only)
    service = models.OneToOneField(
        'tasks.Service',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='calendar_event',
    )

    def save(self, *args, **kwargs):
        """
        Override the save method to set the user field to request.user if available.
        """
        if 'request' in kwargs:
            user = kwargs.pop('request').user
            if user.is_authenticated:
                self.user = user
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def get_html_url(self):
        edit_url = reverse('event_edit', args=(self.id,))
        done_url = reverse('event_done', args=(self.id,))

        if not self.done:
            # Show "Done" link
            return f'''
                <a href="{edit_url}" class="event-link">{self.title}</a> |
            <a href="{done_url}" class="done-link" style="color: white;">&times;</a>
            '''
        else:
            return f'''
            <a href="{edit_url}" class="event-link done-event">{self.title}</a>
            '''
