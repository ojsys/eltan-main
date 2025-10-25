"""
WSGI config for eltanweb project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Use production settings for WSGI deployment
env = os.environ.get('ELTAN_ENV', 'production')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'eltanweb.settings.{env}')

application = get_wsgi_application()
