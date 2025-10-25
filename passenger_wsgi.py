import sys
import os
from pathlib import Path

# Add your project directory to the Python path
# Adjust this path to match your actual project location on the server
sys.path.insert(0, os.path.dirname(__file__))

# Set the Django settings module to use cPanel settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eltanweb.settings')

# Import Django's WSGI application
from django.core.wsgi import get_wsgi_application

# Create the WSGI application
application = get_wsgi_application()