"""
Context processors for making data available to all templates
"""
from .models import SiteSettings


def site_settings(request):
    """
    Make site settings available to all templates
    """
    try:
        settings = SiteSettings.objects.first()
    except:
        settings = None

    return {
        'site_settings': settings,
    }
