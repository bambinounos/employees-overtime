from pathlib import Path

from django.conf import settings

from .models import SiteConfiguration


_VERSION_CACHE = None


def _read_version():
    global _VERSION_CACHE
    if _VERSION_CACHE is None:
        try:
            path = Path(settings.BASE_DIR) / 'VERSION'
            _VERSION_CACHE = path.read_text(encoding='utf-8').strip()
        except (OSError, AttributeError):
            _VERSION_CACHE = ''
    return _VERSION_CACHE


def site_configuration(request):
    """
    Makes the site configuration singleton and app version available to all templates.
    """
    return {
        'site_config': SiteConfiguration.load(),
        'app_version': _read_version(),
    }