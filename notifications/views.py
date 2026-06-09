import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .models import ChatMessage, PushSubscription, UserNotification
from .push import get_vapid_public_key, vapid_configured
from .services import (
    notify_broadcast,
    notify_new_chat_message,
    sync_reminder_notifications,
    unread_count,
    unread_message_count,
)


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


@login_required(login_url='/login/')
def chat_page(request):
    users = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by('username')
    selected_id = request.GET.get('user')
    selected_user = None
    if selected_id and selected_id.isdigit():
        selected_user = users.filter(pk=int(selected_id)).first()
    return render(request, 'notifications/chat.html', {
        'users': users,
        'selected_user': selected_user,
    })


@login_required(login_url='/login/')
@require_GET
def api_count(request):
    """Lightweight badge poll — no reminder sync, no list payload."""
    return JsonResponse({
        'unread_count': unread_count(request.user),
        'unread_messages': unread_message_count(request.user),
    })


@login_required(login_url='/login/')
@require_GET
def api_list(request):
    if request.GET.get('count_only'):
        return JsonResponse({
            'unread_count': unread_count(request.user),
            'unread_messages': unread_message_count(request.user),
        })

    sync_reminder_notifications()

    notifications = (
        UserNotification.objects.filter(recipient=request.user)
        .select_related('lead', 'leadtask')[:50]
    )
    items = [{
        'id': n.pk,
        'kind': n.kind,
        'kind_label': n.get_kind_display(),
        'title': n.title,
        'message': n.message,
        'url': n.url,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
    } for n in notifications]

    return JsonResponse({
        'notifications': items,
        'unread_count': unread_count(request.user),
        'unread_messages': unread_message_count(request.user),
    })


@login_required(login_url='/login/')
@require_POST
def api_mark_read(request):
    data = _json_body(request)
    if data.get('all'):
        UserNotification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'ok'})

    notification_id = data.get('id')
    if not notification_id:
        return JsonResponse({'status': 'error', 'message': 'Missing id'}, status=400)

    UserNotification.objects.filter(
        recipient=request.user, pk=notification_id
    ).update(is_read=True)
    return JsonResponse({'status': 'ok'})


@login_required(login_url='/login/')
@require_GET
def api_chat_users(request):
    users = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by('username')
    result = []
    for user in users:
        unread = ChatMessage.objects.filter(
            recipient=request.user, sender=user, is_read=False
        ).count()
        last = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=user) | Q(sender=user, recipient=request.user)
        ).order_by('-created_at').first()
        result.append({
            'id': user.pk,
            'name': user.get_full_name() or user.username,
            'username': user.username,
            'unread': unread,
            'last_message': last.body[:120] if last else '',
            'last_at': last.created_at.isoformat() if last else '',
        })
    return JsonResponse({'users': result})


@login_required(login_url='/login/')
@require_GET
def api_chat_thread(request, user_id):
    other = get_object_or_404(User, pk=user_id, is_active=True)
    if other.pk == request.user.pk:
        return JsonResponse({'status': 'error', 'message': 'Invalid user'}, status=400)

    messages = ChatMessage.objects.filter(
        Q(sender=request.user, recipient=other) | Q(sender=other, recipient=request.user)
    ).select_related('sender', 'recipient').order_by('created_at')[:200]

    ChatMessage.objects.filter(
        sender=other, recipient=request.user, is_read=False
    ).update(is_read=True)

    UserNotification.objects.filter(
        recipient=request.user,
        kind='message',
        is_read=False,
        url__contains=f'user={other.pk}',
    ).update(is_read=True)

    return JsonResponse({
        'messages': [{
            'id': m.pk,
            'body': m.body,
            'is_mine': m.sender_id == request.user.pk,
            'sender': m.sender.get_full_name() or m.sender.username,
            'created_at': m.created_at.isoformat(),
        } for m in messages],
        'user': {
            'id': other.pk,
            'name': other.get_full_name() or other.username,
        },
    })


@login_required(login_url='/login/')
@require_POST
def api_chat_send(request):
    data = _json_body(request)
    recipient_id = data.get('recipient_id')
    body = (data.get('body') or '').strip()
    if not recipient_id or not body:
        return JsonResponse({'status': 'error', 'message': 'Missing fields'}, status=400)

    recipient = get_object_or_404(User, pk=recipient_id, is_active=True)
    if recipient.pk == request.user.pk:
        return JsonResponse({'status': 'error', 'message': 'Invalid recipient'}, status=400)

    message = ChatMessage.objects.create(
        sender=request.user,
        recipient=recipient,
        body=body,
    )
    notify_new_chat_message(message)

    return JsonResponse({
        'status': 'ok',
        'message': {
            'id': message.pk,
            'body': message.body,
            'is_mine': True,
            'sender': request.user.get_full_name() or request.user.username,
            'created_at': message.created_at.isoformat(),
        },
    })


@require_GET
def service_worker(request):
    """Serve SW at site scope so push works on all CRM pages."""
    sw_path = Path(settings.BASE_DIR) / 'static' / 'sw.js'
    response = HttpResponse(
        sw_path.read_text(encoding='utf-8'),
        content_type='application/javascript',
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


@login_required(login_url='/login/')
@require_GET
def api_vapid_public_key(request):
    return JsonResponse({
        'public_key': get_vapid_public_key(),
        'enabled': vapid_configured(),
    })


@login_required(login_url='/login/')
@require_POST
def api_push_subscribe(request):
    if not vapid_configured():
        return JsonResponse({'status': 'error', 'message': 'Push not configured'}, status=503)

    data = _json_body(request)
    endpoint = data.get('endpoint')
    keys = data.get('keys') or {}
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')
    if not endpoint or not p256dh or not auth:
        return JsonResponse({'status': 'error', 'message': 'Invalid subscription'}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
        },
    )
    return JsonResponse({'status': 'ok'})


@login_required(login_url='/login/')
@require_POST
def api_push_unsubscribe(request):
    data = _json_body(request)
    endpoint = data.get('endpoint')
    if endpoint:
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({'status': 'ok'})


@login_required(login_url='/login/')
@require_POST
def api_broadcast(request):
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Admin only'}, status=403)

    data = _json_body(request)
    body = (data.get('body') or '').strip()
    if not body:
        return JsonResponse({'status': 'error', 'message': 'Message required'}, status=400)

    notify_broadcast(sender=request.user, body=body)
    return JsonResponse({'status': 'ok'})
