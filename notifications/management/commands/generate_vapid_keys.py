import base64
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from cryptography.hazmat.primitives import serialization


class Command(BaseCommand):
    help = 'Generate VAPID keys for browser push notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--write',
            action='store_true',
            help='Write keys to deploy/vapid.env (gitignored on server)',
        )

    def handle(self, *args, **options):
        try:
            from py_vapid import Vapid
        except ImportError:
            self.stderr.write('Install pywebpush first: pip install pywebpush')
            return

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
        private_one_line = private_pem.replace('\n', '\\n')

        self.stdout.write('Add these to ghaithleads/settings.py on production:\n')
        self.stdout.write('')
        self.stdout.write(f"VAPID_PUBLIC_KEY = '{public_key}'")
        self.stdout.write(f"VAPID_PRIVATE_KEY = '{private_one_line}'")
        self.stdout.write("VAPID_ADMIN_EMAIL = 'mailto:admin@ghaithtravel.com'")
        self.stdout.write('')

        if options['write']:
            out = Path(settings.BASE_DIR) / 'deploy' / 'vapid.env'
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                '# Browser push keys — never commit to GitHub\n'
                f'VAPID_PUBLIC_KEY="{public_key}"\n'
                f'VAPID_PRIVATE_KEY="{private_one_line}"\n'
                'VAPID_ADMIN_EMAIL="mailto:admin@ghaithtravel.com"\n',
                encoding='utf-8',
            )
            self.stdout.write(self.style.SUCCESS(f'Wrote {out}'))
