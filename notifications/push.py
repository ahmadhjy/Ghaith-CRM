import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

PUSH_ICON_PATH = '/static/img/favicon.svg'


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
    if not key:
        return ''
    if '\\n' in key:
        key = key.replace('\\n', '\n')
    return key.strip()


def get_site_origin():
    return getattr(settings, 'CRM_SITE_URL', '').rstrip('/')


def absolute_url(path):
    path = path or '/'
    if not path.startswith('/'):
        path = '/' + path
    origin = get_site_origin()
    if origin:
        return origin + path
    return path


def get_push_icon_url():
    icon = getattr(settings, 'CRM_PUSH_ICON_URL', PUSH_ICON_PATH)
    return absolute_url(icon)


def _vapid_claims():
    return {
        'sub': getattr(settings, 'VAPID_ADMIN_EMAIL', 'mailto:admin@ghaithtravel.com'),
    }


def _build_vapid_key():
    private_pem = get_vapid_private_key()
    if not private_pem:
        return None
    try:
        from py_vapid import Vapid

        return Vapid.from_string(private_key=private_pem)
    except Exception as exc:
        logger.error('Invalid VAPID private key: %s', exc)
        return None


def send_push_to_user(user, title, body, url=''):
    if not vapid_configured():
        logger.warning('Push skipped for %s — VAPID keys not configured', user.username)
        return {'sent': 0, 'failed': 0, 'skipped': 'vapid_not_configured'}

    from .models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(user=user))
    if not subscriptions:
        logger.info('Push skipped for %s — no browser subscription saved', user.username)
        return {'sent': 0, 'failed': 0, 'skipped': 'no_subscription'}

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning('pywebpush not installed; browser push disabled')
        return {'sent': 0, 'failed': 0, 'skipped': 'pywebpush_missing'}

    icon_url = get_push_icon_url()
    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url or '/',
        'icon': icon_url,
        'badge': icon_url,
    })

    vapid_key = _build_vapid_key()
    private_pem = get_vapid_private_key()

    sent = 0
    failed = 0
    stale = []

    for sub in subscriptions:
        try:
            kwargs = {
                'subscription_info': {
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                'data': payload,
                'vapid_claims': _vapid_claims(),
                'ttl': 86400,
            }
            if vapid_key is not None:
                kwargs['vapid_private_key'] = vapid_key
            else:
                kwargs['vapid_private_key'] = private_pem

            webpush(**kwargs)
            sent += 1
        except WebPushException as exc:
            failed += 1
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
            failed += 1
            logger.exception('Push error for %s: %s', user.username, exc)

    if stale:
        PushSubscription.objects.filter(pk__in=stale).delete()

    return {'sent': sent, 'failed': failed, 'stale_removed': len(stale)}


def send_test_push(user):
    return send_push_to_user(
        user,
        'Ghaith CRM',
        'Browser notifications are working.',
        '/',
    )
