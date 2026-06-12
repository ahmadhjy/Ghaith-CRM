import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

PUSH_ICON_PATH = '/static/img/favicon.svg'
STALE_PUSH_HTTP_CODES = {401, 403, 404, 410}


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


def _response_detail(exc):
    response = getattr(exc, 'response', None)
    if response is None:
        return ''
    try:
        return (response.text or '')[:500]
    except Exception:
        return ''


def send_push_to_user(user, title, body, url='', *, verbose=False):
    if not vapid_configured():
        msg = 'VAPID keys not configured'
        logger.warning('Push skipped for %s — %s', user.username, msg)
        return {'sent': 0, 'failed': 0, 'skipped': 'vapid_not_configured', 'errors': [msg]}

    from .models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(user=user))
    if not subscriptions:
        msg = 'no browser subscription saved'
        logger.info('Push skipped for %s — %s', user.username, msg)
        return {'sent': 0, 'failed': 0, 'skipped': 'no_subscription', 'errors': [msg]}

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        msg = 'pywebpush not installed'
        logger.warning('%s; browser push disabled', msg)
        return {'sent': 0, 'failed': 0, 'skipped': 'pywebpush_missing', 'errors': [msg]}

    private_pem = get_vapid_private_key()
    if not private_pem:
        return {'sent': 0, 'failed': 0, 'skipped': 'invalid_vapid_key', 'errors': ['empty private key']}

    icon_url = get_push_icon_url()
    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url or '/',
        'icon': icon_url,
        'badge': icon_url,
    })

    sent = 0
    failed = 0
    stale = []
    errors = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=private_pem,
                vapid_claims=_vapid_claims(),
                ttl=86400,
            )
            sent += 1
        except WebPushException as exc:
            failed += 1
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            detail = _response_detail(exc)
            err = f'HTTP {status}: {exc}'
            if detail:
                err += f' — {detail}'
            errors.append(err)
            logger.warning('Push failed for %s: %s', user.username, err)
            if status in STALE_PUSH_HTTP_CODES:
                stale.append(sub.pk)
        except Exception as exc:
            failed += 1
            err = str(exc)
            errors.append(err)
            logger.exception('Push error for %s: %s', user.username, exc)

    if stale:
        PushSubscription.objects.filter(pk__in=stale).delete()
        errors.append(f'removed {len(stale)} stale subscription(s) — revisit site to re-enable push')

    result = {
        'sent': sent,
        'failed': failed,
        'stale_removed': len(stale),
        'site_url': get_site_origin(),
        'icon_url': icon_url,
    }
    if verbose or failed:
        result['errors'] = errors
    return result


def send_test_push(user, *, verbose=False):
    return send_push_to_user(
        user,
        'Ghaith CRM',
        'Browser notifications are working.',
        '/',
        verbose=verbose,
    )
