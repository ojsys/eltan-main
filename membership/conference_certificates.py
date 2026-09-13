"""Conference participation certificates.

The certificate artwork is a finished PDF produced by the design team — the
photo backdrop, the affiliate logos, the officers' signatures, the conference
theme and dates are all baked into it. Rebuilding that in HTML would mean
chasing the design every year and never quite matching the fonts, so instead we
treat the artwork as a *template*: a single-page PDF with everything on it
except the participant's name, which we stamp on at download time.

That keeps the output pixel-identical to what the committee approved, and it
means next year's certificate is an admin upload rather than a deploy.

Only two things are drawn on top of the template:

* the participant's name, centred on the rule and shrunk to fit if it is long;
* the certificate id in small grey type in the bottom-left margin, so a
  certificate presented on paper can be checked against the verification page.

Positions are stored on the conference as *fractions* of the page, not
points, so an uploaded template of a different size still lands the name in
roughly the right place.
"""

import io
import logging
import os

from django.conf import settings
from django.contrib.staticfiles import finders

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# The artwork shipped with the site, used when a conference has no uploaded
# template of its own. Resolved through the staticfiles finders so it works
# both from STATICFILES_DIRS in development and from STATIC_ROOT after
# collectstatic in production.
DEFAULT_TEMPLATE_STATIC_PATH = 'certificates/eltan_conference_certificate_template.pdf'

# The name is set in a bold italic serif to match the Cambria Bold Italic of the
# original artwork. Times-BoldItalic is one of the 14 fonts every PDF reader has
# built in, so nothing needs to be installed on the server.
NAME_FONT = 'Times-BoldItalic'
ID_FONT = 'Helvetica'

# Deep navy, sampled from the certificate's own headings.
NAME_COLOR = Color(0.10, 0.18, 0.42)
ID_COLOR = Color(0.45, 0.45, 0.45)

# Smallest the name is allowed to shrink to before we let it run wide. Below
# this it stops looking like a certificate.
MIN_NAME_FONT_SIZE = 13.0


class CertificateTemplateError(Exception):
    """The certificate artwork is missing or unreadable."""


def _default_template_path():
    path = finders.find(DEFAULT_TEMPLATE_STATIC_PATH)
    if path and os.path.exists(path):
        return path
    # finders only searches STATICFILES_DIRS; after collectstatic in production
    # the file may only exist under STATIC_ROOT.
    fallback = os.path.join(settings.STATIC_ROOT, DEFAULT_TEMPLATE_STATIC_PATH)
    if os.path.exists(fallback):
        return fallback
    return None


def resolve_template(conference):
    """Return an open binary file-like object for the conference's artwork.

    Prefers the template uploaded against the conference, and falls back to the
    artwork shipped in static. Raises :class:`CertificateTemplateError` when
    neither can be read, so the caller can show a real message instead of
    handing the user a broken download.
    """
    uploaded = getattr(conference, 'certificate_template', None)
    if uploaded:
        try:
            uploaded.open('rb')
            return uploaded
        except Exception as exc:  # missing file on disk, bad storage, etc.
            logger.error(
                "Conference %s has a certificate template that could not be opened (%s); "
                "falling back to the default artwork.", conference.pk, exc,
            )

    path = _default_template_path()
    if not path:
        raise CertificateTemplateError(
            "No certificate artwork is available. Upload a certificate template "
            "for this conference, or run collectstatic so the default template "
            "is present."
        )
    return open(path, 'rb')


def _fit_font_size(name, base_size, max_width):
    """Largest size at or below ``base_size`` that keeps ``name`` inside the rule."""
    size = base_size
    while size > MIN_NAME_FONT_SIZE and stringWidth(name, NAME_FONT, size) > max_width:
        size -= 0.5
    return size


def render_certificate(conference, participant_name, certificate_id=None, verify_url=None):
    """Return the finished certificate PDF as bytes.

    ``participant_name`` is printed as given — it is the attendee's own record of
    how their name should appear, so it is not re-cased or otherwise tidied.
    """
    name = (participant_name or '').strip()
    if not name:
        raise ValueError("A certificate needs a participant name.")

    template_file = resolve_template(conference)
    try:
        reader = PdfReader(template_file)
        if not reader.pages:
            raise CertificateTemplateError("The certificate template PDF has no pages.")
        page = reader.pages[0]

        box = page.mediabox
        page_width = float(box.width)
        page_height = float(box.height)

        # Layout knobs live on the conference so next year's artwork can be
        # positioned from the admin instead of from a deploy.
        x_ratio = float(getattr(conference, 'certificate_name_x', 0.5005) or 0.5005)
        baseline_ratio = float(getattr(conference, 'certificate_name_baseline', 0.4690) or 0.4690)
        width_ratio = float(getattr(conference, 'certificate_name_max_width', 0.5225) or 0.5225)
        base_size = float(getattr(conference, 'certificate_name_font_size', 30) or 30)

        centre_x = page_width * x_ratio
        # Stored top-down (how a designer measures); PDF draws bottom-up.
        baseline_y = page_height * (1 - baseline_ratio)
        max_width = page_width * width_ratio

        # A template of a different size should keep the same visual weight.
        A4_LANDSCAPE_HEIGHT = 595.5
        size = _fit_font_size(name, base_size * (page_height / A4_LANDSCAPE_HEIGHT), max_width)

        overlay_buffer = io.BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

        c.setFont(NAME_FONT, size)
        c.setFillColor(NAME_COLOR)
        c.drawCentredString(centre_x, baseline_y, name)

        if certificate_id:
            # Bottom-left margin: the printed footer is centred and never reaches
            # this far left, so the id sits in genuinely empty space.
            c.setFont(ID_FONT, 6.5)
            c.setFillColor(ID_COLOR)
            label = f"Certificate ID: {certificate_id}"
            c.drawString(page_width * 0.057, page_height * 0.078, label)
            if verify_url:
                c.drawString(page_width * 0.057, page_height * 0.078 - 8, f"Verify: {verify_url}")

        c.showPage()
        c.save()
        overlay_buffer.seek(0)

        overlay_page = PdfReader(overlay_buffer).pages[0]
        page.merge_page(overlay_page)

        writer = PdfWriter()
        writer.add_page(page)
        writer.add_metadata({
            '/Title': f"Certificate of Participation — {name}",
            '/Author': 'English Language Teachers Association of Nigeria (ELTAN)',
            '/Subject': conference.title,
        })

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    finally:
        try:
            template_file.close()
        except Exception:
            pass


def certificate_filename(conference, participant_name):
    """A download filename that reads well in a downloads folder."""
    safe_name = ''.join(ch if ch.isalnum() else '_' for ch in (participant_name or 'Participant'))
    safe_name = '_'.join(part for part in safe_name.split('_') if part)
    year = conference.start_date.year if conference.start_date else ''
    return f"ELTAN_{year}_Certificate_{safe_name}.pdf".replace('__', '_')
