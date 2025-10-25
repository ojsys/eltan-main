#!/usr/bin/env python3
import sys
import os

# Add your project directory to the sys.path
sys.path.insert(0, '/home/eltanige/eltan2')
sys.path.insert(0, '/home/eltanige/eltan2/eltanweb')

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eltanweb.settings')

try:
    # Import Django's WSGI application
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except ImportError as e:
    # Fallback for debugging
    def application(environ, start_response):
        status = '500 Internal Server Error'
        output = f'Django Import Error: {str(e)}\nPython path: {sys.path}'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return [output.encode('utf-8')]