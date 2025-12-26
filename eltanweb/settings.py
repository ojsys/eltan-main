import warnings
from cryptography.utils import CryptographyDeprecationWarning
from pathlib import Path
from decouple import config
import os

# Filter Warnings
warnings.filterwarnings('ignore', category=CryptographyDeprecationWarning)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY')  # sk_test_... or sk_live_...
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY')  # pk_test_... or pk_live_...
PAYSTACK_TEST_SECRET_KEY = 'sk_test_1ccdb1ad0a8a19c53492781336ad15390760afd8'
PAYSTACK_TEST_PUBLIC_KEY = 'pk_test_96b9995fbf552beec8da11acbb821aa5c1d06341'
PAYSTACK_INITIALIZE_PAYMENT_URL = 'https://api.paystack.co/transaction/initialize'


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['www.eltanigeria.org', 'eltanigeria.org', '*']

AUTH_USER_MODEL = 'account.CustomUser'
# Application definition

INSTALLED_APPS = [
    'livereload',
    'crispy_forms',
    'crispy_bootstrap5',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ckeditor',
    'account',
    'mainapp',
    'membership',
    
    #'django_summernote',
]

MIDDLEWARE = [
    'livereload.middleware.LiveReloadScript',
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
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site_settings',
                'core.context_processors.current_date',
                'core.context_processors.social_links',
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


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# Use SQLite for local development when MySQL is not available
try:
    config('DB_NAME')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST'),
            'PORT': config('DB_PORT'),
            'OPTIONS':{
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
            }
        }
    }
except:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'eltanige_eltandb',
#         'USER': 'eltanige_eltan_user',
#         'PASSWORD': 'saA~JEd2%QX4',
#         'HOST': 'localhost',
#         'PORT': '3306',
#         'OPTIONS':{
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
#         }
#     }
# }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dash'
LOGOUT_REDIRECT_URL = 'login'

#SUMMERNOTE_THEME = 'bs5'

#Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = config('USER_EMAIL')
EMAIL_HOST_PASSWORD = config('USER_PASSWORD')
DEFAULT_FROM_EMAIL = 'ELTAN <noreply@eltanigeria.org>'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
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
