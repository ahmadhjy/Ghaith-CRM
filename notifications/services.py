from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import NotificationKind, UserNotification


def active_users():
    return User.objects.filter(is_active=True)


def staff_users():
    return active_users().filter(is_staff=True)


def recipients_for_assigned_lead(lead, leadtask=None):
    """Admins plus the user assigned to the lead/order."""
    users = set(staff_users())
    assigned = None
    if leadtask and leadtask.assigned_to_id:
        assigned = leadtask.assigned_to
    elif lead and lead.assigned_to_id:
        assigned = lead.assigned_to
    if assigned and assigned.is_active:
        users.add(assigned)
    return users


def create_notification(
    *,
    recipient,
    kind,
    title,
    message='',
    url='',
    lead=None,
    leadtask=None,
    dedupe_key='',
    send_push=True,
):
    if not recipient or not recipient.is_active:
        return None

    defaults = {
        'kind': kind,
        'title': title,
        'message': message,
        'url': url,
        'lead': lead,
        'leadtask': leadtask,
    }

    if dedupe_key:
        notification, created = UserNotification.objects.get_or_create(
            recipient=recipient,
            dedupe_key=dedupe_key,
            defaults=defaults,
        )
        if not created:
            return notification
    else:
        notification = UserNotification.objects.create(
            recipient=recipient,
            dedupe_key='',
            **defaults,
        )

    if send_push:
        from .push import send_push_to_user

        send_push_to_user(recipient, title, message or title, url)

    return notification


def notify_all_users(*, kind, title, message='', url='', lead=None, leadtask=None, dedupe_prefix):
    for user in active_users():
        create_notification(
            recipient=user,
            kind=kind,
            title=title,
            message=message,
            url=url,
            lead=lead,
            leadtask=leadtask,
            dedupe_key=f'{dedupe_prefix}:{user.pk}',
        )


def notify_takeover_lead(lead):
    notify_all_users(
        kind=NotificationKind.TAKEOVER_LEAD,
        title=f'New lead on Take Over: {lead.name}',
        message=f'{lead.destination or "No destination"} · {lead.phone}',
        url=reverse('takeover_list'),
        lead=lead,
        dedupe_prefix=f'takeover_lead:{lead.pk}',
    )


def notify_media_upload_link(upload_link, *, files_added=0):
    """One notification per client media page — message shows total file count."""
    total = upload_link.files.count()
    if total == 0:
        return

    leadtask = upload_link.leadtask
    lead = leadtask.lead
    url = reverse('client_media_upload_detail', kwargs={'token': str(upload_link.token)})
    title = f'New client media: {lead.name}'
    file_word = 'file' if total == 1 else 'files'
    message = f'{total} media {file_word} uploaded'

    from .push import send_push_to_user

    for user in active_users():
        dedupe_key = f'media_upload:{upload_link.pk}:{user.pk}'
        notification, created = UserNotification.objects.get_or_create(
            recipient=user,
            dedupe_key=dedupe_key,
            defaults={
                'kind': NotificationKind.MEDIA_UPLOAD,
                'title': title,
                'message': message,
                'url': url,
                'lead': lead,
                'leadtask': leadtask,
            },
        )
        if not created:
            notification.title = title
            notification.message = message
            notification.url = url
            update_fields = ['title', 'message', 'url']
            if files_added > 0:
                notification.is_read = False
                update_fields.append('is_read')
            notification.save(update_fields=update_fields)

        if created or files_added > 0:
            send_push_to_user(user, title, message, url)


def notify_new_chat_message(message):
    sender_label = message.sender.get_full_name() or message.sender.username
    url = f"{reverse('notifications_chat')}?user={message.sender_id}"
    create_notification(
        recipient=message.recipient,
        kind=NotificationKind.MESSAGE,
        title=f'New message from {sender_label}',
        message=message.body[:500],
        url=url,
        dedupe_key=f'message:{message.pk}:{message.recipient_id}',
    )


def notify_broadcast(*, sender, body):
    import uuid

    title = f'Notice from {sender.get_full_name() or sender.username}'
    notify_all_users(
        kind=NotificationKind.BROADCAST,
        title=title,
        message=body,
        url='',
        dedupe_prefix=f'broadcast:{uuid.uuid4().hex}',
    )


def sync_reminder_notifications():
    """Create due-soon reminders (24h window). Safe to call on every poll."""
    now = timezone.now()
    window_end = now + timedelta(hours=24)

    from tasks.models import LeadTask, Payment, Service

    payments = (
        Payment.objects.filter(
            is_checked=False,
            date__gte=now,
            date__lte=window_end,
        )
        .select_related('leadtask', 'leadtask__lead', 'leadtask__assigned_to')
    )
    for payment in payments:
        leadtask = payment.leadtask
        lead = leadtask.lead
        due = timezone.localtime(payment.date).strftime('%d %b %Y %H:%M')
        url = reverse('client_payments_list')
        for user in recipients_for_assigned_lead(lead, leadtask):
            create_notification(
                recipient=user,
                kind=NotificationKind.CLIENT_PAYMENT_DUE,
                title=f'Client payment due: {lead.name}',
                message=f'${payment.amount} due {due}',
                url=url,
                lead=lead,
                leadtask=leadtask,
                dedupe_key=f'client_payment_due:{payment.pk}:{user.pk}',
            )

    services = (
        Service.objects.filter(
            is_checked=False,
            due_time__gte=now,
            due_time__lte=window_end,
        )
        .select_related('leadtask', 'leadtask__lead', 'leadtask__assigned_to')
    )
    for service in services:
        leadtask = service.leadtask
        lead = leadtask.lead
        due = timezone.localtime(service.due_time).strftime('%d %b %Y %H:%M')
        url = reverse('supplier_payments_list')
        for user in recipients_for_assigned_lead(lead, leadtask):
            create_notification(
                recipient=user,
                kind=NotificationKind.SUPPLIER_PAYMENT_DUE,
                title=f'Supplier payment due: {lead.name}',
                message=f'{service.supplier or service.service_name} — {service.net} due {due}',
                url=url,
                lead=lead,
                leadtask=leadtask,
                dedupe_key=f'supplier_payment_due:{service.pk}:{user.pk}',
            )

    travelling = (
        LeadTask.objects.filter(
            travel_date__gte=now,
            travel_date__lte=window_end,
        )
        .select_related('lead', 'assigned_to')
    )
    for leadtask in travelling:
        lead = leadtask.lead
        when = timezone.localtime(leadtask.travel_date).strftime('%d %b %Y %H:%M')
        url = reverse('edit_lead_tasks', kwargs={'pk': leadtask.pk})
        for user in recipients_for_assigned_lead(lead, leadtask):
            create_notification(
                recipient=user,
                kind=NotificationKind.CLIENT_TRAVELLING,
                title=f'Client travelling soon: {lead.name}',
                message=f'Departure {when}',
                url=url,
                lead=lead,
                leadtask=leadtask,
                dedupe_key=f'client_travelling:{leadtask.pk}:{user.pk}',
            )

    returning = (
        LeadTask.objects.filter(
            return_date__gte=now,
            return_date__lte=window_end,
        )
        .select_related('lead', 'assigned_to')
    )
    for leadtask in returning:
        lead = leadtask.lead
        when = timezone.localtime(leadtask.return_date).strftime('%d %b %Y %H:%M')
        url = reverse('edit_lead_tasks', kwargs={'pk': leadtask.pk})
        for user in recipients_for_assigned_lead(lead, leadtask):
            create_notification(
                recipient=user,
                kind=NotificationKind.CLIENT_RETURN,
                title=f'Client return soon: {lead.name}',
                message=f'Return {when}',
                url=url,
                lead=lead,
                leadtask=leadtask,
                dedupe_key=f'client_return:{leadtask.pk}:{user.pk}',
            )


def unread_count(user):
    return UserNotification.objects.filter(recipient=user, is_read=False).count()


def unread_message_count(user):
    from .models import ChatMessage

    return ChatMessage.objects.filter(recipient=user, is_read=False).count()
