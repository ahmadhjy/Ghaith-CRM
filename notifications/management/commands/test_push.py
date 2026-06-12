from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from notifications.models import PushSubscription
from notifications.push import (
    get_site_origin,
    get_vapid_public_key,
    send_test_push,
    vapid_configured,
)


class Command(BaseCommand):
    help = 'Send a test browser push (checks VAPID + subscriptions).'

    def add_arguments(self, parser):
        parser.add_argument('username', nargs='?', default='', help='Target username')
        parser.add_argument('--list-subs', action='store_true', help='List users with push subscriptions')
        parser.add_argument('--diagnose', action='store_true', help='Show VAPID config and test all subscribers')
        parser.add_argument('--all', action='store_true', help='Send test push to every subscribed user')

    def handle(self, *args, **options):
        if options['list_subs'] or options['diagnose']:
            self._list_subscriptions()
            if options['list_subs'] and not options['diagnose']:
                return

        if options['diagnose']:
            self._print_config()
            self._test_all(verbose=True)
            return

        if not vapid_configured():
            raise CommandError(
                'VAPID keys are not configured.\n'
                'Run: python manage.py generate_vapid_keys --write\n'
                'Then reload the web app.'
            )

        if options['all']:
            self._test_all(verbose=True)
            return

        username = options['username']
        if not username:
            self.stdout.write('Users with push enabled:')
            self._list_subscriptions()
            raise CommandError('Provide a username, or use --diagnose / --all')

        self._test_user(username, verbose=True)

    def _print_config(self):
        self.stdout.write('--- Push configuration ---')
        self.stdout.write(f'VAPID configured: {vapid_configured()}')
        pub = get_vapid_public_key()
        self.stdout.write(f'VAPID public key: {pub[:24]}…' if pub else 'VAPID public key: (missing)')
        self.stdout.write(f'CRM_SITE_URL: {get_site_origin() or "(not set)"}')
        self.stdout.write('')

    def _list_subscriptions(self):
        subs = PushSubscription.objects.select_related('user').order_by('user__username', 'pk')
        if not subs.exists():
            self.stdout.write('No push subscriptions saved yet.')
            self.stdout.write('Log in on phone/desktop, allow notifications, wait a few seconds.')
            return

        current_user = None
        count = 0
        for sub in subs:
            if sub.user.username != current_user:
                if current_user is not None:
                    self.stdout.write(f'  ({count} device{"s" if count != 1 else ""})')
                current_user = sub.user.username
                count = 0
                self.stdout.write(f'{sub.user.username}:')
            count += 1
            self.stdout.write(f'  - {sub.endpoint[:90]}…')
        if current_user is not None:
            self.stdout.write(f'  ({count} device{"s" if count != 1 else ""})')

    def _test_user(self, username, *, verbose=False):
        user = User.objects.filter(username__iexact=username).first()
        if not user:
            known = list(
                User.objects.filter(push_subscriptions__isnull=False)
                .distinct()
                .values_list('username', flat=True)
            )
            hint = f' Known subscribers: {", ".join(known)}' if known else ''
            raise CommandError(f'User not found: {username}.{hint}')

        subs = PushSubscription.objects.filter(user=user).count()
        if subs == 0:
            raise CommandError(
                f'No push subscription for {user.username}. '
                'Log in on that account and allow notifications in the browser.'
            )

        result = send_test_push(user, verbose=verbose)
        self.stdout.write(str(result))
        for err in result.get('errors', []):
            self.stdout.write(self.style.WARNING(err))

        if result.get('sent', 0) < 1:
            raise CommandError(
                f'Push not delivered to {user.username}. '
                'If HTTP 401/403: run generate_vapid_keys --write, reload web app, '
                'then log in again on phone and re-allow notifications.'
            )
        self.stdout.write(self.style.SUCCESS(f'Test push sent to {user.username}'))

    def _test_all(self, *, verbose=False):
        usernames = (
            PushSubscription.objects.values_list('user__username', flat=True).distinct()
        )
        if not usernames:
            self.stdout.write('No subscribers to test.')
            return

        for name in usernames:
            self.stdout.write(f'--- Testing {name} ---')
            try:
                self._test_user(name, verbose=verbose)
            except CommandError as exc:
                self.stdout.write(self.style.ERROR(str(exc)))
