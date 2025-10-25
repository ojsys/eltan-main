"""
Context processors for core app
"""

from datetime import datetime
from django.conf import settings


def site_settings(request):
    """Add site settings to template context"""
    try:
        from .models import SiteSettings
        site_settings_obj = SiteSettings.objects.first()
        if not site_settings_obj:
            # Create default settings if none exist
            site_settings_obj = SiteSettings.objects.create(
                site_name="ELTAN",
                site_tagline="English Language Teachers Association of Nigeria",
                site_description="Empowering English Language Teachers Across Nigeria"
            )
    except:
        # Fallback if model doesn't exist yet
        site_settings_obj = type('SiteSettings', (), {
            'site_name': 'ELTAN',
            'site_tagline': 'English Language Teachers Association of Nigeria',
            'site_description': 'Empowering English Language Teachers Across Nigeria',
            'primary_color': '#1976d2',
            'secondary_color': '#dc004e',
            'accent_color': '#e67918',
            'contact_email': 'info@eltanigeria.org',
            'contact_phone': '',
            'facebook_url': '',
            'twitter_url': '',
            'linkedin_url': '',
            'instagram_url': '',
            'logo': None,
            'favicon': None,
            'default_og_image': None,
        })()
    
    return {'site_settings': site_settings_obj}


def current_date(request):
    """Add current date to template context"""
    return {'current_date': datetime.now()}


def social_links(request):
    """Provide active social links to all templates"""
    try:
        from .models_cms import SocialLink
        links = SocialLink.objects.filter(is_active=True).order_by('order')
    except Exception:
        links = []
    return {'social_links': links}
