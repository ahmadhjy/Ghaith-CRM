import json
import logging
from urllib.parse import urljoin, urlparse

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


def public_origin():
    origin = getattr(settings, 'CRM_PUBLIC_ORIGIN', '').strip().rstrip('/')
    if origin:
        return origin
    hosts = getattr(settings, 'ALLOWED_HOSTS', []) or []
    for host in hosts:
        if host and host not in ('*', 'localhost', '127.0.0.1'):
            return f'https://{host}'
    return ''


def absolute_url(url=''):
    if not url:
        return public_origin() or '/'
    if url.startswith('http://') or url.startswith('https://'):
        return url
    origin = public_origin()
    if origin:
        return urljoin(origin + '/', url.lstrip('/'))
    return url


def _vapid_claims_for_endpoint(endpoint):
    claims = {
        'sub': getattr(settings, 'VAPID_ADMIN_EMAIL', 'mailto:admin@ghaithtravel.com'),
    }
    parsed = urlparse(endpoint or '')
    if parsed.scheme and parsed.netloc:
        claims['aud'] = f'{parsed.scheme}://{parsed.netloc}'
    return claims


def send_push_to_user(user, title, body, url=''):
    if not vapid_configured():
        logger.info('Push skipped for %s: VAPID keys not configured', user.username)
        return 0

    from .models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(user=user))
    if not subscriptions:
        logger.info('Push skipped for %s: no browser subscription saved', user.username)
        return 0

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning('pywebpush not installed; browser push disabled')
        return 0

    payload = json.dumps({
        'title': title,
        'body': body,
        'url': absolute_url(url),
        'icon': absolute_url(getattr(settings, 'CRM_PUSH_ICON', '/static/css/favicon.ico')),
    })

    private_key = get_vapid_private_key()
    sent = 0
    stale = []

    for sub in subscriptions:
        claims = _vapid_claims_for_endpoint(sub.endpoint)
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=claims,
                content_encoding='aes128gcm',
                timeout=30,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            logger.warning(
                'Push failed for %s (HTTP %s): %s',
                user.username,
                status,
                exc,
            )
            if status in (404, 410):
                stale.append(sub.pk)
        except Exception as exc:
            logger.exception('Push error for %s: %s', user.username, exc)

    if stale:
        PushSubscription.objects.filter(pk__in=stale).delete()
        logger.info('Removed %s stale push subscription(s) for %s', len(stale), user.username)

    if sent:
        logger.info('Sent %s push notification(s) to %s', sent, user.username)

    return sent
