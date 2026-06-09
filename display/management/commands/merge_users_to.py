"""
Reassign all CRM data from one or more users to a target user, then remove sources.

Usage (dry run — shows counts only):
  python manage.py merge_users_to --to Sara --from Willy OLD Reine Batoul Mohammad MohammadHaidar Hassan tia aya

Apply changes:
  python manage.py merge_users_to --to Sara --from Willy OLD ... --execute

Also delete source user accounts after reassignment:
  python manage.py merge_users_to --to Sara --from Willy OLD ... --execute --delete-sources
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from dashboard.models import Event
from display.models import DailyReport, Lead, Offer, UserMonthlyTarget
from notifications.models import ChatMessage, PushSubscription, UserNotification
from tasks.models import ClientMediaUploadLink, LeadTask, Task


DEFAULT_SOURCE_USERNAMES = [
    'Willy',
    'OLD',
    'Reine',
    'Batoul',
    'Mohammad',
    'MohammadHaidar',
    'Hassan',
    'tia',
    'aya',
]


def resolve_user(identifier: str) -> User | None:
    ident = identifier.strip()
    if not ident:
        return None
    qs = User.objects.filter(is_active=True) | User.objects.filter(is_active=False)
    user = qs.filter(username__iexact=ident).first()
    if user:
        return user
    return qs.filter(first_name__iexact=ident).first()


class Command(BaseCommand):
    help = 'Move all data from source users to a target user and optionally delete sources.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            required=True,
            help='Target username (e.g. Sara)',
        )
        parser.add_argument(
            '--from',
            dest='from_users',
            nargs='+',
            default=DEFAULT_SOURCE_USERNAMES,
            help='Source usernames to merge (default: Willy, OLD, Reine, ...)',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Apply changes (default is dry run)',
        )
        parser.add_argument(
            '--delete-sources',
            action='store_true',
            help='Delete source user accounts after reassignment (requires --execute)',
        )

    def handle(self, *args, **options):
        target = resolve_user(options['to'])
        if not target:
            raise CommandError(f'Target user not found: {options["to"]!r}')

        sources: list[User] = []
        missing: list[str] = []
        for name in options['from_users']:
            user = resolve_user(name)
            if user:
                if user.pk == target.pk:
                    raise CommandError(f'Source and target are the same user: {name}')
                sources.append(user)
            else:
                missing.append(name)

        if not sources:
            raise CommandError('No source users found.')

        source_ids = [u.pk for u in sources]
        execute = options['execute']
        delete_sources = options['delete_sources']

        if delete_sources and not execute:
            raise CommandError('--delete-sources requires --execute')

        self.stdout.write(f'Target: {target.username} (id={target.pk})')
        self.stdout.write('Sources:')
        for user in sources:
            self.stdout.write(f'  - {user.username} (id={user.pk})')
        if missing:
            self.stdout.write(self.style.WARNING(f'Not found (skipped): {", ".join(missing)}'))

        counts = self._count_reassignments(source_ids)
        self.stdout.write('\nRecords to reassign:')
        for label, count in counts.items():
            self.stdout.write(f'  {label}: {count}')

        chat_count = ChatMessage.objects.filter(
            Q(sender_id__in=source_ids) | Q(recipient_id__in=source_ids)
        ).count()
        push_count = PushSubscription.objects.filter(user_id__in=source_ids).count()
        self.stdout.write(f'  chat messages (will be deleted): {chat_count}')
        self.stdout.write(f'  push subscriptions (will be deleted): {push_count}')

        if not execute:
            self.stdout.write(self.style.WARNING('\nDry run only. Re-run with --execute to apply.'))
            return

        with transaction.atomic():
            updated = self._reassign_all(target, source_ids)
            self.stdout.write(self.style.SUCCESS('\nReassigned:'))
            for label, count in updated.items():
                self.stdout.write(f'  {label}: {count}')

            deleted_chat, _ = ChatMessage.objects.filter(
                Q(sender_id__in=source_ids) | Q(recipient_id__in=source_ids)
            ).delete()
            deleted_push, _ = PushSubscription.objects.filter(user_id__in=source_ids).delete()
            self.stdout.write(f'  deleted chat messages: {deleted_chat}')
            self.stdout.write(f'  deleted push subscriptions: {deleted_push}')

            if delete_sources:
                for user in sources:
                    username = user.username
                    user.delete()
                    self.stdout.write(self.style.SUCCESS(f'Deleted user: {username}'))
            else:
                deactivated = User.objects.filter(pk__in=source_ids).update(is_active=False)
                self.stdout.write(
                    self.style.SUCCESS(f'Deactivated {deactivated} source user(s) (use --delete-sources to remove accounts)')
                )

        self.stdout.write(self.style.SUCCESS('\nDone.'))

    def _count_reassignments(self, source_ids: list[int]) -> dict[str, int]:
        return {
            'leads (assigned_to)': Lead.objects.filter(assigned_to_id__in=source_ids).count(),
            'lead tasks (assigned_to)': LeadTask.objects.filter(assigned_to_id__in=source_ids).count(),
            'tasks (assigned_to)': Task.objects.filter(assigned_to_id__in=source_ids).count(),
            'offers (assigned_to)': Offer.objects.filter(assigned_to_id__in=source_ids).count(),
            'offers (created_by)': Offer.objects.filter(created_by_id__in=source_ids).count(),
            'daily reports': DailyReport.objects.filter(user_id__in=source_ids).count(),
            'monthly targets': UserMonthlyTarget.objects.filter(user_id__in=source_ids).count(),
            'calendar events': Event.objects.filter(user_id__in=source_ids).count(),
            'media upload links (created_by)': ClientMediaUploadLink.objects.filter(
                created_by_id__in=source_ids
            ).count(),
            'notifications (recipient)': UserNotification.objects.filter(
                recipient_id__in=source_ids
            ).count(),
        }

    def _reassign_all(self, target: User, source_ids: list[int]) -> dict[str, int]:
        result: dict[str, int] = {}

        result['leads (assigned_to)'] = Lead.objects.filter(
            assigned_to_id__in=source_ids
        ).update(assigned_to=target)

        result['lead tasks (assigned_to)'] = LeadTask.objects.filter(
            assigned_to_id__in=source_ids
        ).update(assigned_to=target)

        result['tasks (assigned_to)'] = Task.objects.filter(
            assigned_to_id__in=source_ids
        ).update(assigned_to=target)

        result['offers (assigned_to)'] = Offer.objects.filter(
            assigned_to_id__in=source_ids
        ).update(assigned_to=target)

        result['offers (created_by)'] = Offer.objects.filter(
            created_by_id__in=source_ids
        ).update(created_by=target)

        result['daily reports'] = DailyReport.objects.filter(
            user_id__in=source_ids
        ).update(user=target)

        result['calendar events'] = Event.objects.filter(
            user_id__in=source_ids
        ).update(user=target)

        result['media upload links (created_by)'] = ClientMediaUploadLink.objects.filter(
            created_by_id__in=source_ids
        ).update(created_by=target)

        result['notifications (recipient)'] = self._reassign_notifications(target, source_ids)
        result['monthly targets'] = self._merge_monthly_targets(target, source_ids)

        return result

    def _reassign_notifications(self, target: User, source_ids: list[int]) -> int:
        moved = 0
        skipped = 0
        existing_keys = set(
            UserNotification.objects.filter(recipient=target)
            .exclude(dedupe_key='')
            .values_list('dedupe_key', flat=True)
        )

        for notification in UserNotification.objects.filter(recipient_id__in=source_ids):
            if notification.dedupe_key and notification.dedupe_key in existing_keys:
                notification.delete()
                skipped += 1
                continue
            notification.recipient = target
            notification.save(update_fields=['recipient'])
            if notification.dedupe_key:
                existing_keys.add(notification.dedupe_key)
            moved += 1

        if skipped:
            self.stdout.write(
                self.style.WARNING(f'  skipped duplicate notifications: {skipped}')
            )
        return moved

    def _merge_monthly_targets(self, target: User, source_ids: list[int]) -> int:
        moved = 0
        for row in UserMonthlyTarget.objects.filter(user_id__in=source_ids):
            existing = UserMonthlyTarget.objects.filter(user=target, month=row.month).first()
            if existing:
                existing.target_profit += row.target_profit
                existing.save(update_fields=['target_profit'])
                row.delete()
            else:
                row.user = target
                row.save(update_fields=['user'])
                moved += 1
        return moved
