"""
Development settings with SQLite database
Use this for local development without MySQL
"""

from eltanweb.settings import *

# Override database to use SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Add core app to installed apps
INSTALLED_APPS += [
    'core',
]

# Template context processors
TEMPLATES[0]['OPTIONS']['context_processors'].extend([
    'core.context_processors.site_settings',
    'core.context_processors.current_date',
])

# Paystack Configuration
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
SITE_URL = config('SITE_URL', default='http://localhost:8000')

# Enhanced logging with file creation
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.utils.autoreload': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ELTAN specific settings
ELTAN_SETTINGS = {
    'MEMBERSHIP_RENEWAL_REMINDER_DAYS': 30,
    'CERTIFICATE_AUTO_GENERATION': True,
    'EMAIL_NOTIFICATIONS': True,
    'PAYMENT_WEBHOOK_VERIFICATION': True,
}