#!/usr/bin/env python3
"""
Patch ghaithleads/settings.py on PythonAnywhere after deploy.
- Adds 'notifications' to INSTALLED_APPS if missing
- Adds VAPID env loader block if missing

Safe to run multiple times (idempotent).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


VAPID_BLOCK = '''

# Browser push (patched by deploy/patch_production_settings.py)
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
'''


ACCOUNTING_APPS = [
    'rest_framework',
    'accounts_core.apps.AccountsCoreConfig',
    'catalog',
    'sales',
    'purchases',
    'treasury',
    'expenses',
    'reporting',
    'auditlog',
    'api',
    'accounting_bridge.apps.AccountingBridgeConfig',
]

ACCOUNTING_SETTINGS_BLOCK = '''

# Embedded accounting module (patched by deploy/patch_production_settings.py)
ACCOUNTING_TEMPLATE_DIR = BASE_DIR / 'ghaith_accounting' / 'templates'
if str(ACCOUNTING_TEMPLATE_DIR) not in [str(p) for p in TEMPLATES[0].get('DIRS', [])]:
    TEMPLATES[0]['DIRS'] = list(TEMPLATES[0].get('DIRS', [])) + [ACCOUNTING_TEMPLATE_DIR]

if 'accounting_bridge.middleware.AccountingAccessMiddleware' not in MIDDLEWARE:
    MIDDLEWARE.append('accounting_bridge.middleware.AccountingAccessMiddleware')
if 'reporting.middleware.ReportDateDefaultsMiddleware' not in MIDDLEWARE:
    MIDDLEWARE.append('reporting.middleware.ReportDateDefaultsMiddleware')

for _cp in (
    'accounts_core.context_processors.pdf_branding',
    'accounting_bridge.context_processors.app_shell',
):
    if _cp not in TEMPLATES[0]['OPTIONS']['context_processors']:
        TEMPLATES[0]['OPTIONS']['context_processors'].append(_cp)

COMPANY_LEGAL_NAME = os.environ.get('COMPANY_LEGAL_NAME', 'Ghaith Travel')
COMPANY_ADDRESS = os.environ.get('COMPANY_ADDRESS', 'Bechara El Khoury Highway, Beirut, Lebanon')
COMPANY_PHONE = os.environ.get('COMPANY_PHONE', '+961-81456406')
COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL', 'info@ghaithtravel.com')
COMPANY_FOOTER_TEXT = os.environ.get('COMPANY_FOOTER_TEXT', '© Ghaith Travel. All rights reserved.')
COMPANY_TAGLINE = os.environ.get('COMPANY_TAGLINE', 'Ghaith Travel & Tourism')
COMPANY_DEFAULT_CURRENCY = os.environ.get('COMPANY_DEFAULT_CURRENCY', 'USD')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
'''


def patch_settings(path: Path) -> list[str]:
    changes: list[str] = []
    text = path.read_text(encoding='utf-8')

    if "'notifications'" not in text and '"notifications"' not in text:
        match = re.search(
            r"(INSTALLED_APPS\s*=\s*\[[\s\S]*?)(\n\])",
            text,
        )
        if not match:
            raise SystemExit('Could not find INSTALLED_APPS in settings.py')
        insert_at = match.start(2)
        text = text[:insert_at] + "\n    'notifications'," + text[insert_at:]
        changes.append("added 'notifications' to INSTALLED_APPS")

    # Remove legacy ckeditor entry if a previous deploy added it without working templates.
    if "'ckeditor'" in text or '"ckeditor"' in text:
        text = re.sub(r"\n\s*['\"]ckeditor['\"],?", '', text)
        changes.append("removed 'ckeditor' from INSTALLED_APPS (using TinyMCE in admin)")

    if 'VAPID_PUBLIC_KEY' not in text or 'CRM_SITE_URL' not in text:
        if 'import os' not in text:
            text = 'import os\n' + text
            changes.append('added import os')
        if 'VAPID_PUBLIC_KEY' not in text:
            text = text.rstrip() + VAPID_BLOCK + '\n'
            changes.append('added VAPID settings block')
        elif 'CRM_SITE_URL' not in text:
            text = text.rstrip() + (
                "\nCRM_SITE_URL = os.environ.get('CRM_SITE_URL', "
                "'https://ghaithtravel.pythonanywhere.com')\n"
                "CRM_PUSH_ICON_URL = '/static/img/favicon.svg'\n"
            )
            changes.append('added CRM_SITE_URL for push notifications')

    for app in ACCOUNTING_APPS:
        if f"'{app}'" not in text and f'"{app}"' not in text:
            match = re.search(r"(INSTALLED_APPS\s*=\s*\[[\s\S]*?)(\n\])", text)
            if match:
                insert_at = match.start(2)
                text = text[:insert_at] + f"\n    '{app}'," + text[insert_at:]
                changes.append(f"added '{app}' to INSTALLED_APPS")

    if 'accounting_bridge.middleware.AccountingAccessMiddleware' not in text:
        text = text.rstrip() + ACCOUNTING_SETTINGS_BLOCK + '\n'
        changes.append('added accounting module settings block')

    if changes:
        path.write_text(text, encoding='utf-8')

    return changes


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: patch_production_settings.py /path/to/ghaithleads/settings.py')
        return 1

    settings_path = Path(sys.argv[1])
    if not settings_path.is_file():
        print(f'Not found: {settings_path}')
        return 1

    changes = patch_settings(settings_path)
    if changes:
        print('Patched settings.py:')
        for item in changes:
            print(f'  - {item}')
    else:
        print('settings.py already up to date')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
