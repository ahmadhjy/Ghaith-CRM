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
    if not key:
        return ''
    if '\\n' in key:
        key = key.replace('\\n', '\n')
    return key.strip()


def _vapid_claims():
    return {
        'sub': getattr(settings, 'VAPID_ADMIN_EMAIL', 'mailto:admin@ghaithtravel.com'),
    }


def _build_vapid_key():
    """Return a py_vapid Vapid instance for pywebpush 2.x."""
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
        logger.debug('Push skipped — VAPID keys not configured')
        return {'sent': 0, 'failed': 0, 'skipped': 'vapid_not_configured'}

    from .models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(user=user))
    if not subscriptions:
        logger.debug('Push skipped — no subscription for %s', user.username)
        return {'sent': 0, 'failed': 0, 'skipped': 'no_subscription'}

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning('pywebpush not installed; browser push disabled')
        return {'sent': 0, 'failed': 0, 'skipped': 'pywebpush_missing'}

    vapid_key = _build_vapid_key()
    if vapid_key is None:
        return {'sent': 0, 'failed': 0, 'skipped': 'invalid_vapid_key'}

    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url or '/',
    })

    sent = 0
    failed = 0
    stale = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_key,
                vapid_claims=_vapid_claims(),
                ttl=86400,
            )
            sent += 1
        except WebPushException as exc:
            failed += 1
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            logger.warning(
                'Push failed for %s (%s): %s',
                user.username,
                sub.endpoint[:60],
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
        'Browser push is working.',
        '/',
    )
