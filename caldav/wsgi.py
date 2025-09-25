import os
import sys

# Add the project directory to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")
import django
django.setup()

# Import the WsgiDAVApp and load configuration
from wsgidav.wsgidav_app import WsgiDAVApp

config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "wsgidav.conf")
application = WsgiDAVApp.new_from_config(config_file)