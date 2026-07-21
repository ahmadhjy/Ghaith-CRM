"""
Reassign all CRM data from one or more users to a target user, then remove sources.

Usage (dry run — shows counts only):
  python manage.py merge_users_to --to Sara --from Willy OLD Reine Batoul Mohammad MohammadHaidar Hassan tia aya

Apply changes:
  python manage.py merge_users_to --to Sara --from Willy OLD ... --execute

Also delete source user accounts after reassignment:
  python manage.py merge_users_to --to Sara --from Willy OLD ... --execute --delete-sources
"""
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts_core.models import UserProfile
from display.models import CrmUserProfile, UserMonthlyTarget
from notifications.models import UserNotification


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

        if not execute:
            self.stdout.write(self.style.WARNING('\nDry run only. Re-run with --execute to apply.'))
            return

        with transaction.atomic():
            updated = self._reassign_all(target, source_ids)
            self.stdout.write(self.style.SUCCESS('\nReassigned:'))
            for label, count in updated.items():
                self.stdout.write(f'  {label}: {count}')

            self._merge_profile_flags(target, sources)
            self._merge_accounting_employees(target, sources, deactivate_only=not delete_sources)

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
        counts = {}
        for relation in User._meta.related_objects:
            if not (relation.one_to_many or relation.one_to_one):
                continue
            model = relation.related_model
            field = relation.field
            label = f'{model._meta.label} ({field.name})'
            counts[label] = model.objects.filter(
                **{f'{field.name}_id__in': source_ids}
            ).count()
        return counts

    def _reassign_all(self, target: User, source_ids: list[int]) -> dict[str, int]:
        result: dict[str, int] = {}

        special_models = {
            UserNotification,
            UserMonthlyTarget,
        }
        for relation in User._meta.related_objects:
            model = relation.related_model
            field = relation.field
            if model in special_models:
                continue
            label = f'{model._meta.label} ({field.name})'
            if relation.one_to_many:
                result[label] = model.objects.filter(
                    **{f'{field.name}_id__in': source_ids}
                ).update(**{f'{field.name}_id': target.pk})
            elif relation.one_to_one:
                result[label] = self._move_one_to_one(
                    model, field.name, target, source_ids
                )

        result['notifications.UserNotification (recipient)'] = (
            self._reassign_notifications(target, source_ids)
        )
        result['display.UserMonthlyTarget (user)'] = (
            self._merge_monthly_targets(target, source_ids)
        )

        return result

    def _move_one_to_one(self, model, field_name, target, source_ids) -> int:
        """Move a one-to-one row when possible without replacing Sara's row."""
        source_rows = model.objects.filter(
            **{f'{field_name}_id__in': source_ids}
        )
        moved = 0
        for row in source_rows:
            if model.objects.filter(**{f'{field_name}_id': target.pk}).exists():
                if model._meta.label == 'accounts_core.Employee':
                    # Keep Mona's employee/payroll history, detached and inactive.
                    row.user = None
                    row.is_active = False
                    row.save(update_fields=['user', 'is_active'])
                else:
                    # Sara's own profile/link remains authoritative.
                    row.delete()
                continue
            setattr(row, f'{field_name}_id', target.pk)
            row.save(update_fields=[field_name])
            moved += 1
        return moved

    def _merge_profile_flags(self, target: User, sources: list[User]) -> None:
        """Copy useful CRM/accounting flags onto Sara without moving 1:1 rows."""
        target_crm, _ = CrmUserProfile.objects.get_or_create(user=target)
        target_profile, _ = UserProfile.objects.get_or_create(user=target)
        changed_crm = []
        changed_profile = []

        for source in sources:
            source_crm = getattr(source, 'crm_profile', None)
            if source_crm:
                if not target_crm.department_id and source_crm.department_id:
                    target_crm.department = source_crm.department
                    changed_crm.append('department')
                if source_crm.receives_lead_assignments and not target_crm.receives_lead_assignments:
                    target_crm.receives_lead_assignments = True
                    changed_crm.append('receives_lead_assignments')

            source_profile = getattr(source, 'profile', None)
            if source_profile:
                if source_profile.is_main_accountant and not target_profile.is_main_accountant:
                    target_profile.is_main_accountant = True
                    changed_profile.append('is_main_accountant')
                if source_profile.is_accountant and not target_profile.is_accountant:
                    target_profile.is_accountant = True
                    changed_profile.append('is_accountant')

            if source.is_sales and not target.is_sales:
                target.is_sales = True
                target.save(update_fields=['is_sales'])
            if getattr(source, 'administration', False) and not getattr(target, 'administration', False):
                target.administration = True
                target.save(update_fields=['administration'])

        if changed_crm:
            target_crm.save(update_fields=list(dict.fromkeys(changed_crm)))
        if changed_profile:
            target_profile.save(update_fields=list(dict.fromkeys(changed_profile)))

    def _merge_accounting_employees(
        self, target: User, sources: list[User], *, deactivate_only: bool
    ) -> None:
        """Move invoice/payroll employee ownership after user FK reassignment."""
        for source in sources:
            args = [
                'merge_employees',
                '--to',
                target.username,
                '--from',
                source.username,
            ]
            if deactivate_only:
                args.append('--deactivate-only')
            try:
                call_command(*args, stdout=StringIO())
            except CommandError as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f'  skipped employee merge for {source.username}: {exc}'
                    )
                )

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
                # Sara's own target remains authoritative; combining targets
                # would incorrectly double the dashboard target.
                row.delete()
            else:
                row.user = target
                row.save(update_fields=['user'])
                moved += 1
        return moved
