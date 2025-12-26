"""
Context processors for making data available to all templates
"""


def site_settings(request):
    """
    Make site settings available to all templates
    Uses lazy import to avoid circular import issues
    """
    try:
        # Import here to avoid circular imports during Django initialization
        from .models import SiteSettings
        settings = SiteSettings.objects.first()
    except Exception as e:
        # Log the error but don't crash
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Could not load site settings: {e}")
        settings = None

    return {
        'site_settings': settings,
    }
