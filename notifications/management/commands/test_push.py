from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from notifications.push import send_push_to_user, vapid_configured


class Command(BaseCommand):
    help = 'Send a test browser push to a user (checks VAPID + saved subscription)'

    def add_arguments(self, parser):
        parser.add_argument('--user', default='', help='Username (default: first staff user)')
        parser.add_argument('--all', action='store_true', help='Send to every user with a subscription')

    def handle(self, *args, **options):
        if not vapid_configured():
            raise CommandError('VAPID keys missing. Run: python manage.py generate_vapid_keys --write')

        if options['all']:
            from notifications.models import PushSubscription

            user_ids = PushSubscription.objects.values_list('user_id', flat=True).distinct()
            users = User.objects.filter(pk__in=user_ids, is_active=True)
        elif options['user']:
            users = User.objects.filter(username__iexact=options['user'])
            if not users.exists():
                raise CommandError(f'User not found: {options["user"]}')
        else:
            users = User.objects.filter(is_active=True, is_staff=True).order_by('id')[:1]
            if not users.exists():
                raise CommandError('No staff user found; pass --user USERNAME')

        total = 0
        for user in users:
            sent = send_push_to_user(
                user,
                'Ghaith CRM test push',
                f'If you see this, push works for {user.username}.',
                '/',
            )
            total += sent
            self.stdout.write(f'{user.username}: sent={sent}')

        if total == 0:
            self.stdout.write(
                self.style.WARNING(
                    'No push delivered. Ensure the user allowed notifications in the browser '
                    'and has an active subscription (log in and allow push).'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f'Delivered {total} push notification(s).'))
