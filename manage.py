#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _default_settings_module():
    """Use production settings on PythonAnywhere; dev settings locally."""
    if os.environ.get('DJANGO_SETTINGS_MODULE'):
        return os.environ['DJANGO_SETTINGS_MODULE']
    root = Path(__file__).resolve().parent
    if (root / 'ghaithleads' / 'settings.py').is_file():
        return 'ghaithleads.settings'
    return 'system.settings'


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', _default_settings_module())
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
