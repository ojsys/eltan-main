"""
Core admin configuration
Imports all admin configurations including CMS admin
"""

from django.contrib import admin

# Import CMS admin configurations
from .admin_cms import *

# Note: All admin classes are registered in admin_cms.py
# This includes:
# - SiteSettings
# - ContactMessage
# - HomePage
# - Feature
# - Statistic
# - Partner
# - FAQ
# - Testimonial
# - Page
# - Announcement
# - SocialLink