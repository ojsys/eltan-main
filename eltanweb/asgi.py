"""
ASGI config for eltanweb project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Use production settings for ASGI deployment
env = os.environ.get('ELTAN_ENV', 'production')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'eltanweb.settings.{env}')

application = get_asgi_application()
