import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def vapid_configured():
    return bool(
        getattr(settings, 'VAPID_PUBLIC_KEY', '')
        and getattr(settings, 'VAPID_PRIVATE_KEY', '')
    )


def get_vapid_public_key():
    return getattr(settings, 'VAPID_PUBLIC_KEY', '')


def get_vapid_private_key():
    key = getattr(settings, 'VAPID_PRIVATE_KEY', '')
    if isinstance(key, bytes):
        key = key.decode()
    if '\\n' in key:
        key = key.replace('\\n', '\n')
    return key


def send_push_to_user(user, title, body, url=''):
    if not vapid_configured():
        return

    from .models import PushSubscription

    subscriptions = PushSubscription.objects.filter(user=user)
    if not subscriptions.exists():
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning('pywebpush not installed; browser push disabled')
        return

    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url,
    })

    vapid_claims = {
        'sub': getattr(settings, 'VAPID_ADMIN_EMAIL', 'mailto:admin@ghaithtravel.com'),
    }

    stale = []
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=get_vapid_private_key(),
                vapid_claims=vapid_claims,
            )
        except WebPushException as exc:
            logger.warning('Push failed for %s: %s', sub.endpoint, exc)
            if getattr(exc, 'response', None) and exc.response.status_code in (404, 410):
                stale.append(sub.pk)

    if stale:
        PushSubscription.objects.filter(pk__in=stale).delete()
