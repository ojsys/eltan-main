"""
Context processors for making data available to all templates
"""
from datetime import datetime


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


def current_date(request):
    """
    Make current date/time available to all templates
    """
    return {
        'current_date': datetime.now(),
        'current_year': datetime.now().year,
    }


def social_links(request):
    """
    Make social links available to all templates
    """
    try:
        from .models_cms import SocialLink
        links = SocialLink.objects.filter(is_active=True).order_by('order')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Could not load social links: {e}")
        links = []

    return {
        'social_links': links,
    }
