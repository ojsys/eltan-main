"""
Base settings for ELTAN project.
These settings are common to both development and production environments.
"""

import warnings
from cryptography.utils import CryptographyDeprecationWarning
from pathlib import Path
from decouple import config
import os

# Filter Warnings
warnings.filterwarnings('ignore', category=CryptographyDeprecationWarning)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# Paystack Configuration
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
PAYSTACK_TEST_SECRET_KEY = 'sk_test_1ccdb1ad0a8a19c53492781336ad15390760afd8'
PAYSTACK_TEST_PUBLIC_KEY = 'pk_test_96b9995fbf552beec8da11acbb821aa5c1d06341'
PAYSTACK_INITIALIZE_PAYMENT_URL = 'https://api.paystack.co/transaction/initialize'

# Custom User Model
AUTH_USER_MODEL = 'account.CustomUser'

# Application definition
INSTALLED_APPS = [
    # Jazzmin Admin (must be before django.contrib.admin)
    'jazzmin',

    # Forms and UI
    'crispy_forms',
    'crispy_bootstrap5',

    # Django Core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'ckeditor',
    'ordered_model',

    # Project Apps
    'account',
    'mainapp',
    'membership',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'eltanweb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site_settings',
            ],
        },
    },
]

# CKEditor configuration
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'full',
        'height': 300,
        'width': '100%',
    },
}

CKEDITOR_UPLOAD_PATH = "uploads/"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

WSGI_APPLICATION = 'eltanweb.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dash'
LOGOUT_REDIRECT_URL = 'login'

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = config('USER_EMAIL', default='')
EMAIL_HOST_PASSWORD = config('USER_PASSWORD', default='')
DEFAULT_FROM_EMAIL = 'ELTAN <noreply@eltanigeria.org>'

# =============================================================================
# JAZZMIN SETTINGS
# =============================================================================

JAZZMIN_SETTINGS = {
    # title of the window (Will default to current_admin_site.site_title if absent or None)
    "site_title": "ELTAN Admin",

    # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_header": "ELTAN",

    # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_brand": "ELTAN Admin",

    # Logo to use for your site, must be present in static files, used for brand on top left
    # "site_logo": "images/logo-eltan.jpeg",

    # Logo to use for your site, must be present in static files, used for login form logo (defaults to site_logo)
    "login_logo": None,

    # Logo to use for login form in dark themes (defaults to login_logo)
    "login_logo_dark": None,

    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",

    # Relative path to a favicon for your site, will default to site_logo if absent (ideally 32x32 px)
    "site_icon": None,

    # Welcome text on the login screen
    "welcome_sign": "Welcome to ELTAN Admin Portal",

    # Copyright on the footer
    "copyright": "ELTAN - English Language Teachers Association of Nigeria",

    # List of model admins to search from the search bar, search bar omitted if excluded
    "search_model": ["account.CustomUser", "membership.Subscription", "membership.EltanConference"],

    # Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
    "user_avatar": None,

    ############
    # Top Menu #
    ############

    # Links to put along the top menu
    "topmenu_links": [
        # Url that gets reversed (Permissions can be added)
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        # external url that opens in a new window (Permissions can be added)
        {"name": "View Site", "url": "/", "new_window": True},
        # model admin to link to (Permissions checked against model)
        {"model": "account.CustomUser"},
        # App with dropdown menu to all its models pages (Permissions checked against models)
        {"app": "membership"},
    ],

    #############
    # User Menu #
    #############

    # Additional links to include in the user menu on the top right ("app" url type is not allowed)
    "usermenu_links": [
        {"name": "View Site", "url": "/", "new_window": True},
        {"model": "account.customuser"}
    ],

    #############
    # Side Menu #
    #############

    # Whether to display the side menu
    "show_sidebar": True,

    # Whether to aut expand the menu
    "navigation_expanded": True,

    # Hide these apps when generating side menu e.g (auth)
    "hide_apps": [],

    # Hide these models when generating side menu (e.g auth.user)
    "hide_models": [],

    # List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
    "order_with_respect_to": ["account", "membership", "core", "auth"],

    # Custom links to append to app groups, keyed on app name
    "custom_links": {
        "membership": [{
            "name": "View Conferences",
            "url": "/conferences/",
            "icon": "fas fa-calendar",
            "permissions": ["membership.view_eltanconference"]
        }]
    },

    # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
    # for the full list of 5.13.0 free icon classes
    "icons": {
        "auth": "fas fa-users-cog",
        "account.CustomUser": "fas fa-user",
        "account.Group": "fas fa-users",
        "membership.Subscription": "fas fa-credit-card",
        "membership.MemberProfile": "fas fa-id-card",
        "membership.EltanConference": "fas fa-calendar-alt",
        "membership.EltanConferenceRegistration": "fas fa-ticket-alt",
        "membership.ConferenceSpeaker": "fas fa-microphone",
        "membership.ConferenceSchedule": "fas fa-clock",
        "membership.ConferenceSponsor": "fas fa-handshake",
        "membership.ConferenceLocMember": "fas fa-user-tie",
        "membership.Sigs": "fas fa-users",
        "membership.SigsRegistration": "fas fa-user-check",
        "membership.Events": "fas fa-calendar",
        "membership.News": "fas fa-newspaper",
        "membership.Resource": "fas fa-book",
        "membership.Newsletter": "fas fa-envelope",
        "membership.Certificate": "fas fa-certificate",
        "membership.MembershipType": "fas fa-tags",
        "core.HeroSlide": "fas fa-images",
        "core.Feature": "fas fa-star",
        "core.Statistic": "fas fa-chart-line",
        "core.Partner": "fas fa-building",
        "core.FAQ": "fas fa-question-circle",
    },
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    #################
    # Related Modal #
    #################
    # Use modals instead of popups
    "related_modal_active": False,

    #############
    # UI Tweaks #
    #############
    # Relative paths to custom CSS/JS scripts (must be present in static files)
    "custom_css": None,
    "custom_js": None,
    # Whether to link font from fonts.googleapis.com (use custom_css to supply font otherwise)
    "use_google_fonts_cdn": True,
    # Whether to show the UI customizer on the sidebar
    "show_ui_builder": False,

    ###############
    # Change view #
    ###############
    # Render out the change view as a single form, or in tabs, current options are
    # - single
    # - horizontal_tabs (default)
    # - vertical_tabs
    # - collapsible
    # - carousel
    "changeform_format": "horizontal_tabs",
    # override change forms on a per modeladmin basis
    "changeform_format_overrides": {"account.customuser": "collapsible", "auth.group": "vertical_tabs"},
    # Add a language dropdown into the admin
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-orange",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-orange",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },
    "actions_sticky_top": False
}
