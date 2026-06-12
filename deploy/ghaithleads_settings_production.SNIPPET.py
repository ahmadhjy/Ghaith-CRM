# Copy relevant lines into /home/ghaithtravel/ghaithleads/ghaithleads/settings.py
# (production only — do not commit this file with real secrets to GitHub)

import os
from pathlib import Path

DEBUG = False

ALLOWED_HOSTS = [
    'ghaithtravel.pythonanywhere.com',
    'www.ghaithtravel.pythonanywhere.com',
]

# Generate a new key for production: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY = 'REPLACE_WITH_PRODUCTION_SECRET_KEY'

# Database stays SQLite at project root (never delete this file on deploy)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Static: PythonAnywhere Web tab maps /static/ → BASE_DIR/static/
# Do NOT run collectstatic --clear — it wipes theme CSS from this folder.
STATIC_ROOT = BASE_DIR / 'static'
STATIC_URL = '/static/'
# Do not set STATICFILES_STORAGE to ManifestStaticFilesStorage on production.

# Add to INSTALLED_APPS:
# 'notifications',

# Browser push — run once on server: python manage.py generate_vapid_keys --write
# That creates deploy/vapid.env (gitignored). Loader:
def _load_vapid_env():
    vapid_file = BASE_DIR / 'deploy' / 'vapid.env'
    if not vapid_file.exists():
        return
    for line in vapid_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_vapid_env()
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_ADMIN_EMAIL = os.environ.get('VAPID_ADMIN_EMAIL', 'mailto:admin@ghaithtravel.com')

CRM_SITE_URL = os.environ.get('CRM_SITE_URL', 'https://ghaithtravel.pythonanywhere.com')
CRM_PUSH_ICON_URL = '/static/img/favicon.svg'

# Optional: import local overrides
# try:
#     from .local_settings import *  # noqa: F403
# except ImportError:
#     pass
