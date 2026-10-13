"""Event certificates: the PDF, and the link that adds one to LinkedIn.

Two ways to make the PDF, the same split conference certificates use:

* **Uploaded artwork.** A designer's single-page PDF with the name left blank;
  the name and certificate id are printed onto it. The result is exactly what
  the committee approved.
* **No artwork.** Most webinars will never get a bespoke design, so there is a
  house certificate drawn here: ELTAN's mark, the title, the name, the event,
  the CPD hours, and the officers' signatures from CertificateSignatory — the
  same people and images the membership certificate prints.

Names are set in Charis SIL, the journal's typeface. The PDF base fonts stop at
Latin-1, and a certificate that prints "Ng■z■" for Ngọzị is worse than none.
"""

import io
import logging
import os
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils import dateformat
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from membership.models import CertificateSignatory

logger = logging.getLogger(__name__)

ORGANISATION = 'English Language Teachers Association of Nigeria'
LOGO_STATIC_PATH = 'images/logo-eltan.jpeg'
FONT_DIRECTORY = os.path.join(settings.BASE_DIR, 'journal', 'static', 'journal', 'fonts')
FONTS = {
    'EvtSerif': 'Charis-Regular.ttf',
    'EvtSerifBold': 'Charis-Bold.ttf',
    'EvtSerifItalic': 'Charis-Italic.ttf',
    'EvtSerifBoldItalic': 'Charis-BoldItalic.ttf',
    'EvtSans': 'NotoSans-Regular.ttf',
    'EvtSansBold': 'NotoSans-Bold.ttf',
}

NAVY = (0x10 / 255, 0x20 / 255, 0x2f / 255)
ORANGE = (0xE6 / 255, 0x79 / 255, 0x18 / 255)
INK = (0x35 / 255, 0x48 / 255, 0x5c / 255)
GREY = (0x8c / 255, 0x9c / 255, 0xab / 255)
MIN_NAME_SIZE = 14


def _fonts():
    registered = pdfmetrics.getRegisteredFontNames()
    for name, filename in FONTS.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIRECTORY, filename)))


def _fit(text, font, size, width):
    while size > MIN_NAME_SIZE and pdfmetrics.stringWidth(text, font, size) > width:
        size -= 0.5
    return size


def _logo():
    path = finders.find(LOGO_STATIC_PATH) or os.path.join(settings.STATIC_ROOT, LOGO_STATIC_PATH)
    return ImageReader(path) if path and os.path.exists(path) else None


def _file_path_or_reader(field):
    try:
        return field.path
    except (NotImplementedError, ValueError):
        field.open('rb')
        try:
            return io.BytesIO(field.read())
        finally:
            field.close()


def render(certificate, verify_url=''):
    """The finished certificate as PDF bytes."""
    _fonts()
    setup = getattr(certificate.event, 'setup', None)
    if setup and setup.certificate_template:
        try:
            return _onto_artwork(certificate, setup, verify_url)
        except Exception:                                # noqa: BLE001
            # Broken artwork should not stop someone receiving what they earned.
            logger.exception('Uploaded certificate artwork failed for event %s', certificate.event.pk)
    return _house_certificate(certificate, verify_url)


def _onto_artwork(certificate, setup, verify_url):
    setup.certificate_template.open('rb')
    try:
        reader = PdfReader(io.BytesIO(setup.certificate_template.read()))
    finally:
        setup.certificate_template.close()
    page = reader.pages[0]
    width, height = float(page.mediabox.width), float(page.mediabox.height)

    overlay = io.BytesIO()
    sheet = canvas.Canvas(overlay, pagesize=(width, height))
    size = _fit(
        certificate.participant_name, 'EvtSerifBoldItalic',
        setup.certificate_name_font_size * (height / 595.3), width * setup.certificate_name_max_width,
    )
    sheet.setFont('EvtSerifBoldItalic', size)
    sheet.setFillColorRGB(*NAVY)
    sheet.drawCentredString(
        width * setup.certificate_name_x, height * (1 - setup.certificate_name_baseline),
        certificate.participant_name,
    )
    _print_reference(sheet, certificate, verify_url, width * 0.057, height * 0.078)
    sheet.save()

    page.merge_page(PdfReader(io.BytesIO(overlay.getvalue())).pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    _metadata(writer, certificate)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _print_reference(sheet, certificate, verify_url, x, y):
    sheet.setFont('EvtSans', 7)
    sheet.setFillColorRGB(*GREY)
    sheet.drawString(x, y, f'Certificate ID: {certificate.certificate_id}')
    if verify_url:
        sheet.drawString(x, y - 9, f'Verify at {verify_url}')


def _metadata(writer, certificate):
    writer.add_metadata({
        '/Title': f'{certificate.certificate_title} — {certificate.participant_name}',
        '/Author': f'{ORGANISATION} (ELTAN)',
        '/Subject': certificate.event_title,
    })


def _house_certificate(certificate, verify_url):
    width, height = landscape(A4)
    out = io.BytesIO()
    sheet = canvas.Canvas(out, pagesize=(width, height))
    sheet.setTitle(f'{certificate.certificate_title} — {certificate.participant_name}')
    sheet.setAuthor(f'{ORGANISATION} (ELTAN)')
    sheet.setSubject(certificate.event_title)
    centre = width / 2

    # Frame: an orange band, a fine navy rule inside it.
    sheet.setStrokeColorRGB(*ORANGE)
    sheet.setLineWidth(9)
    sheet.rect(18, 18, width - 36, height - 36)
    sheet.setStrokeColorRGB(*NAVY)
    sheet.setLineWidth(0.6)
    sheet.rect(32, 32, width - 64, height - 64)

    y = height - 70
    logo = _logo()
    if logo:
        sheet.drawImage(logo, centre - 28, y - 56, 56, 56, preserveAspectRatio=True, mask='auto')
        y -= 72
    sheet.setFillColorRGB(*INK)
    sheet.setFont('EvtSansBold', 9.5)
    sheet.drawCentredString(centre, y, ORGANISATION.upper())

    y -= 52
    sheet.setFillColorRGB(*NAVY)
    sheet.setFont('EvtSerifBold', 32)
    sheet.drawCentredString(centre, y, certificate.certificate_title)
    sheet.setFillColorRGB(*ORANGE)
    sheet.rect(centre - 40, y - 16, 80, 2.5, stroke=0, fill=1)

    y -= 46
    sheet.setFillColorRGB(*INK)
    sheet.setFont('EvtSerifItalic', 13)
    sheet.drawCentredString(centre, y, 'This is to certify that')

    y -= 46
    size = _fit(certificate.participant_name, 'EvtSerifBoldItalic', 34, width - 220)
    sheet.setFillColorRGB(*NAVY)
    sheet.setFont('EvtSerifBoldItalic', size)
    sheet.drawCentredString(centre, y, certificate.participant_name)

    y -= 34
    sheet.setFillColorRGB(*INK)
    sheet.setFont('EvtSerif', 12.5)
    sheet.drawCentredString(centre, y, 'took part in and completed the post-event activity for')
    y -= 24
    sheet.setFillColorRGB(*NAVY)
    sheet.setFont('EvtSerifBold', 15)
    for line in simpleSplit(certificate.event_title, 'EvtSerifBold', 15, width - 240)[:2]:
        sheet.drawCentredString(centre, y, line)
        y -= 20

    event = certificate.event
    details = [dateformat.format(event.event_date, 'j F Y')]
    if event.event_end_date and event.event_end_date != event.event_date:
        details[0] = (
            f"{dateformat.format(event.event_date, 'j F')} – "
            f"{dateformat.format(event.event_end_date, 'j F Y')}"
        )
    if event.event_location:
        details.append(event.event_location)
    if certificate.cpd_hours:
        hours = format(certificate.cpd_hours.normalize(), 'f')
        details.append(f'{hours} CPD hour{"" if hours == "1" else "s"}')
    sheet.setFillColorRGB(*INK)
    sheet.setFont('EvtSans', 10)
    sheet.drawCentredString(centre, y - 2, '   ·   '.join(details))

    _signatures(sheet, width)
    _print_reference(sheet, certificate, verify_url, 48, 50)

    sheet.showPage()
    sheet.save()
    return out.getvalue()


def _signatures(sheet, width):
    """The officers' signatures, spread evenly across the foot of the page."""
    signatories = CertificateSignatory.for_certificate()[:3]
    if not signatories:
        return
    slot = (width - 160) / len(signatories)
    for index, person in enumerate(signatories):
        centre = 80 + slot * index + slot / 2
        source = person.signature_source
        if source:
            try:
                sheet.drawImage(
                    ImageReader(source), centre - 70, 100, 140, 40,
                    preserveAspectRatio=True, mask='auto',
                )
            except Exception:                            # noqa: BLE001
                logger.warning('Could not draw the signature of %s', person.name)
        sheet.setStrokeColorRGB(*INK)
        sheet.setLineWidth(0.5)
        sheet.line(centre - 80, 96, centre + 80, 96)
        sheet.setFillColorRGB(*NAVY)
        sheet.setFont('EvtSansBold', 9)
        sheet.drawCentredString(centre, 84, person.name)
        sheet.setFillColorRGB(*INK)
        sheet.setFont('EvtSans', 8)
        sheet.drawCentredString(centre, 73, person.title)


def filename(certificate):
    safe = ''.join(ch if ch.isalnum() else '_' for ch in certificate.participant_name)
    safe = '_'.join(part for part in safe.split('_') if part) or 'Participant'
    return f'ELTAN_Certificate_{certificate.certificate_id}_{safe}.pdf'


def linkedin_url(certificate, verify_url):
    """LinkedIn's 'Add licence or certification' form, filled in.

    No API or app review is needed: this is the public add-to-profile link, and
    the member confirms it on LinkedIn. With ELTAN's LinkedIn page id set, the
    certification shows the association's logo instead of plain text.
    """
    issued = certificate.issued_at
    params = {
        'startTask': 'CERTIFICATION_NAME',
        'name': f'{certificate.certificate_title}: {certificate.event_title}',
        'issueYear': issued.year,
        'issueMonth': issued.month,
        'certUrl': verify_url,
        'certId': certificate.certificate_id,
    }
    organisation_id = getattr(settings, 'ELTAN_LINKEDIN_ORGANIZATION_ID', '')
    if organisation_id:
        params['organizationId'] = organisation_id
    else:
        params['organizationName'] = f'{ORGANISATION} (ELTAN)'
    return 'https://www.linkedin.com/profile/add?' + urlencode(params)
