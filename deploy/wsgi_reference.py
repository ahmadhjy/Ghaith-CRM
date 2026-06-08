# Reference WSGI file for PythonAnywhere (already configured on the server).
# Path: /var/www/ghaithtravel_pythonanywhere_com_wsgi.py
#
# Do not replace this file during deploy — the deploy script only touches it
# to reload the app (touch). Content should remain:

import os
import sys

project_home = '/home/ghaithtravel/ghaithleads'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['DJANGO_SETTINGS_MODULE'] = 'ghaithleads.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
