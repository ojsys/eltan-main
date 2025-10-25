"""
Modern ELTAN settings - gradual implementation
This extends your existing settings with new features
"""

from .settings import *  # Import existing settings

# Add new apps to existing INSTALLED_APPS
INSTALLED_APPS += [
    # New core apps
    'core',
    'payments',
    
    # Third-party packages (install as needed)
    # 'taggit',
    # 'import_export',
    # 'reversion',
]

# Override database to use SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Enhanced middleware
MIDDLEWARE_NEW = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware', 
    'whitenoise.middleware.WhiteNoiseMiddleware',
] + MIDDLEWARE[1:]  # Keep existing middleware but add new ones

# Only use new middleware if packages are available
try:
    import corsheaders  # noqa: F401
    import whitenoise   # noqa: F401
    MIDDLEWARE = MIDDLEWARE_NEW
except ImportError:
    pass

# Template context processors
TEMPLATES[0]['OPTIONS']['context_processors'].extend([
    'core.context_processors.site_settings',
    'core.context_processors.current_date',
])

# Email configuration (enhanced)
EMAIL_TIMEOUT = 60
EMAIL_USE_LOCALTIME = True

# Paystack Configuration
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
SITE_URL = config('SITE_URL', default='http://localhost:8000')

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 5  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 10  # 10MB

# Session configuration
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True

# Enhanced logging
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
        'payment_file': {
            'level': 'INFO', 
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'payments.log',
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
        'payments': {
            'handlers': ['payment_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.utils.autoreload': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# ELTAN specific settings
ELTAN_SETTINGS = {
    'MEMBERSHIP_RENEWAL_REMINDER_DAYS': 30,
    'CERTIFICATE_AUTO_GENERATION': True,
    'EMAIL_NOTIFICATIONS': True,
    'PAYMENT_WEBHOOK_VERIFICATION': True,
}

# REST Framework (if available)
try:
    import rest_framework  # noqa: F401
    INSTALLED_APPS += ['rest_framework']
    
    REST_FRAMEWORK = {
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
        'PAGE_SIZE': 20,
    }
except ImportError:
    pass