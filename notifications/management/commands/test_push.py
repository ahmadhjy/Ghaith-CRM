from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from notifications.push import send_test_push, vapid_configured


class Command(BaseCommand):
    help = 'Send a test browser push to a user (checks VAPID + subscriptions).'

    def add_arguments(self, parser):
        parser.add_argument('username', nargs='?', default='', help='Target username')
        parser.add_argument('--list-subs', action='store_true', help='List push subscriptions')

    def handle(self, *args, **options):
        if not vapid_configured():
            raise CommandError('VAPID keys are not configured. Run: python manage.py generate_vapid_keys --write')

        from notifications.models import PushSubscription

        if options['list_subs']:
            for sub in PushSubscription.objects.select_related('user').order_by('user__username'):
                self.stdout.write(f'{sub.user.username}: {sub.endpoint[:80]}…')
            return

        username = options['username']
        if not username:
            raise CommandError('Provide a username or use --list-subs')

        user = User.objects.filter(username__iexact=username).first()
        if not user:
            raise CommandError(f'User not found: {username}')

        subs = PushSubscription.objects.filter(user=user).count()
        if subs == 0:
            raise CommandError(
                f'No push subscription for {user.username}. '
                'Log in on the site and allow notifications in the browser first.'
            )

        result = send_test_push(user)
        self.stdout.write(str(result))
        if result.get('sent', 0) < 1:
            raise CommandError('Push was not delivered — check server logs for WebPush errors.')
        self.stdout.write(self.style.SUCCESS(f'Test push sent to {user.username}'))
