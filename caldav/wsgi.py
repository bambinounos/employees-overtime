"""WSGI entry point for Radicale CalDAV server with Django backend."""
import os
import sys

# Add the project directory to the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django before Radicale loads plugins
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")
import django
django.setup()

from django.conf import settings
from radicale import config
from radicale.app import Application

configuration = config.load()
configuration.update({
    "auth": {"type": "caldav.radicale_auth"},
    "storage": {"type": "caldav.storage"},
    "rights": {"type": "owner_only"},
    "web": {"type": "none"},
    "server": {"hosts": "0.0.0.0:8080"},
    "logging": {"level": "info"},
}, "custom")

# Mount prefix where the reverse proxy exposes CalDAV (e.g. /caldav-server/).
# The proxy strips it from PATH_INFO (proxy_pass http://127.0.0.1:8080/), so
# Radicale would otherwise run with an empty base prefix and (a) emit hrefs
# without the prefix and (b) reject calendar-multiget hrefs that DO carry it,
# logging "Skipping invalid path ... doesn't start with ...". Telling Radicale
# its prefix via X-Script-Name keeps generated and validated hrefs consistent.
# Overridable in local_settings.py via CALDAV_SCRIPT_NAME (set "" to disable).
CALDAV_SCRIPT_NAME = getattr(settings, 'CALDAV_SCRIPT_NAME', '/caldav-server')


def with_script_name(app, script_name):
    """WSGI middleware that advertises the proxy mount prefix to Radicale."""
    if not script_name:
        return app

    def wrapper(environ, start_response):
        # Don't override an explicit header already set by the proxy.
        if 'HTTP_X_SCRIPT_NAME' not in environ:
            environ['HTTP_X_SCRIPT_NAME'] = script_name
        return app(environ, start_response)

    return wrapper


application = with_script_name(Application(configuration), CALDAV_SCRIPT_NAME)
