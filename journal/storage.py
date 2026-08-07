"""Private storage for manuscripts under review.

Anything uploaded to MEDIA_ROOT is served straight off the filesystem by the web
server, with no view in between to ask who is asking. For a double-blind journal
that is a hole in the process: a title page names the authors, and a reviewer who
can guess a media URL has defeated the anonymity the whole workflow rests on.

Manuscript files therefore live outside MEDIA_ROOT and are only ever handed out
by :func:`journal.views.submission_file` after it has checked the requester.
Published article PDFs are the opposite case and stay in MEDIA_ROOT — they are
meant to be downloadable by anyone.
"""

from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_storage():
    """The storage manuscripts are written to.

    A callable rather than a module-level instance so the absolute path is
    resolved at runtime and never baked into a migration, which would pin the
    project to whatever machine generated it.
    """
    return FileSystemStorage(location=str(settings.JOURNAL_PRIVATE_ROOT))
