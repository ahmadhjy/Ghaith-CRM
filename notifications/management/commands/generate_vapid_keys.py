import base64
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from cryptography.hazmat.primitives import serialization

from notifications.push import load_vapid_credentials, normalize_vapid_private_pem


class Command(BaseCommand):
    help = 'Generate VAPID keys for browser push notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--write',
            action='store_true',
            help='Write keys to deploy/vapid.env and deploy/vapid_private.pem',
        )
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify existing VAPID keys load correctly (no new keys generated)',
        )

    def handle(self, *args, **options):
        if options['verify']:
            try:
                load_vapid_credentials()
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            pub = getattr(settings, 'VAPID_PUBLIC_KEY', '')
            self.stdout.write(self.style.SUCCESS('VAPID keys are valid.'))
            if pub:
                self.stdout.write(f'Public key: {pub[:32]}…')
            return

        try:
            from py_vapid import Vapid
        except ImportError:
            raise CommandError('Install pywebpush first: pip install pywebpush')

        vapid = Vapid()
        vapid.generate_keys()

        public_raw = vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        public_key = base64.urlsafe_b64encode(public_raw).decode().rstrip('=')

        private_pem = vapid.private_pem()
        if isinstance(private_pem, bytes):
            private_pem = private_pem.decode()
        private_pem = normalize_vapid_private_pem(private_pem)
        private_one_line = private_pem.replace('\n', '\\n')

        self.stdout.write('Keys generated. After --write, reload the web app.\n')
        self.stdout.write(f'VAPID_PUBLIC_KEY={public_key[:32]}…')

        if options['write']:
            deploy_dir = Path(settings.BASE_DIR) / 'deploy'
            deploy_dir.mkdir(parents=True, exist_ok=True)

            pem_path = deploy_dir / 'vapid_private.pem'
            pem_path.write_text(private_pem, encoding='utf-8')

            env_path = deploy_dir / 'vapid.env'
            env_path.write_text(
                '# Browser push keys — never commit to GitHub\n'
                f'VAPID_PUBLIC_KEY="{public_key}"\n'
                f'VAPID_PRIVATE_KEY="{private_one_line}"\n'
                'VAPID_ADMIN_EMAIL="mailto:admin@ghaithtravel.com"\n',
                encoding='utf-8',
            )

            # Verify round-trip
            try:
                load_vapid_credentials()
            except ValueError as exc:
                raise CommandError(f'Generated keys failed verification: {exc}') from exc

            self.stdout.write(self.style.SUCCESS(f'Wrote {env_path}'))
            self.stdout.write(self.style.SUCCESS(f'Wrote {pem_path}'))
            self.stdout.write(
                'Reload the PythonAnywhere web app, then run: '
                'python manage.py generate_vapid_keys --verify'
            )
