"""WSGI entry point for Radicale CalDAV server with Django backend."""
import os
import sys

# Add the project directory to the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django before Radicale loads plugins
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")
import django
django.setup()

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

application = Application(configuration)
