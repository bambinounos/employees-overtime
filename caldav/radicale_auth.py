"""Radicale auth plugin that validates against Django's auth system."""
import os
import sys

# Ensure Django is set up before importing auth
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")

import django
try:
    django.setup()
except RuntimeError:
    pass  # Already set up

from radicale.auth import BaseAuth


class Auth(BaseAuth):
    def _login(self, login, password):
        from django.contrib.auth import authenticate
        user = authenticate(username=login, password=password)
        if user is not None and user.is_active:
            return login
        return ""
