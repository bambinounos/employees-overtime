from .models import SiteConfiguration

def site_configuration(request):
    """
    Makes the site configuration singleton available to all templates.
    """
    return {
        'site_config': SiteConfiguration.load()
    }