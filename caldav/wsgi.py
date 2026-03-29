import os
import sys

# Add the project directory to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")
import django
django.setup()

from wsgidav.wsgidav_app import WsgiDAVApp
from caldav.dav_provider import CalDAVProvider
from caldav.auth import DjangoDomainController

config = {
    "host": "0.0.0.0",
    "port": 8080,
    "provider_mapping": {
        "/": CalDAVProvider(),
    },
    "verbose": 1,
    "enable_loggers": [],
    "property_manager": True,
    "lock_storage": True,
    "http_authenticator": {
        "domain_controller": DjangoDomainController,
        "accept_basic": True,
        "accept_digest": False,
        "default_to_digest": False,
    },
}

application = WsgiDAVApp(config)
