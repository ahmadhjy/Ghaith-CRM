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
