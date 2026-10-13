"""Private storage for portfolio evidence.

A member's uploaded certificates carry their name, sometimes their date of birth
or a registration number, and nobody else has any business opening them. So
they are kept outside MEDIA_ROOT, where the web server would serve them to
anyone with the URL, and handed out only by the owner-checked evidence view.
"""

from django.conf import settings
from django.core.files.storage import FileSystemStorage


def evidence_storage():
    """A callable, so the absolute path never ends up baked into a migration."""
    root = getattr(settings, 'PORTFOLIO_PRIVATE_ROOT', settings.BASE_DIR / 'private_media' / 'portfolio')
    return FileSystemStorage(location=str(root))
