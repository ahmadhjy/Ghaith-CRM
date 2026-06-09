from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate VAPID keys for browser push notifications'

    def handle(self, *args, **options):
        try:
            from py_vapid import Vapid
        except ImportError:
            self.stderr.write('Install pywebpush first: pip install pywebpush')
            return

        vapid = Vapid()
        vapid.generate_keys()
        private = vapid.private_pem()
        public = vapid.public_key

        self.stdout.write('Add these to your environment / production settings:\n')
        self.stdout.write(f'VAPID_PRIVATE_KEY={private!r}')
        self.stdout.write(f'VAPID_PUBLIC_KEY={public!r}')
        self.stdout.write("VAPID_ADMIN_EMAIL=mailto:admin@ghaithtravel.com")
