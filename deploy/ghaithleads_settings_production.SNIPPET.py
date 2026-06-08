# Copy relevant lines into /home/ghaithtravel/ghaithleads/ghaithleads/settings.py
# (production only — do not commit this file with real secrets to GitHub)

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

# Optional: import local overrides
# try:
#     from .local_settings import *  # noqa: F403
# except ImportError:
#     pass
