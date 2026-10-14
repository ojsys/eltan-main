"""The issue booklet: one PDF holding a whole issue, as a printed journal would.

In order: a front cover, the preliminary pages (title page, imprint, aims and
scope, editorial board), the table of contents, the editorial if the issue has
one, and then every published article in the issue, one after another.

The articles are not re-typeset for the booklet. Each one's own galley goes in
as it is, which is only possible because galleys are numbered from the
article's first page in the issue (see typeset.stamp_page_numbers). So
building a booklet starts by paginating the issue: page numbers run on from one
article to the next, in the order the editor set, and any galley printed with
the wrong numbers is rendered again. A reader who downloads one article gets
exactly the pages they would find in the booklet.

Front matter is numbered i, ii, iii…; the articles start again at 1. The PDF's
page labels say the same, so a reader's "go to page 15" lands on page 15.
"""

import io
import logging

from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from pypdf.constants import PageLabelStyle

from . import typeset

logger = logging.getLogger(__name__)

# A re-numbered galley can come back a page longer or shorter than before — the
# page range printed on its first page is longer, and a line wraps. Rendering
# it again with the range it really has settles it, in one more pass at most.
MAX_PAGINATION_PASSES = 3


class BookletError(Exception):
    """The booklet could not be built, for a reason an editor can act on."""


def booklet_articles(issue):
    """The articles that go into an issue's booklet, in the order they appear.

    Published ones only. The booklet is public once the issue is, and an
    article still being corrected must not reach readers inside it.
    """
    return list(
        issue.public_articles
        .select_related('section', 'issue')
        .prefetch_related('authors')
        .order_by('issue_order', 'first_page', 'title')
    )


def _galley_bytes(article):
    return typeset._read(article.pdf)


def _has_pdf_galley(article):
    return bool(article.pdf) and article.galley_extension == '.pdf'


def prepare_galleys(articles):
    """Typeset any article that has no PDF galley yet, if there is anything to set.

    An article published with only a Word file — uploaded as the galley, or left
    there when typesetting fell back to the source — would otherwise stop the
    whole booklet. Its Word file is kept as the source before it is set, so the
    original is never lost to the new galley.
    """
    for article in articles:
        if _has_pdf_galley(article):
            continue
        if not article.source_file and article.pdf:
            article.source_file.name = article.pdf.name
            article.save(update_fields=['source_file', 'updated_at'])
        if article.body_html or article.source_file:
            typeset.refresh_galley(article)
            article.refresh_from_db()


def check_galleys(articles):
    """Every article must have a PDF galley — a Word file cannot be bound in."""
    prepare_galleys(articles)
    missing = []
    for article in articles:
        if _has_pdf_galley(article):
            continue
        if not article.pdf and not article.source_file:
            reason = 'no file uploaded'
        else:
            reason = article.typeset_note or 'its file could not be typeset'
        missing.append(f'"{article.title}" ({reason})')
    if missing:
        raise BookletError(
            'These articles have no PDF to include, so the booklet cannot be built. '
            'Upload a PDF or a readable Word file for each, then build again: '
            + '; '.join(missing)
        )


# --- pagination ------------------------------------------------------------

def paginate(issue, articles=None):
    """Number the pages through the issue, in article order.

    The first article starts on page 1 and each one after starts on the page
    after the last ended. An article whose page range changes, or whose galley
    was printed from a different first page, has its galley rendered again.

    Returns how many galleys were re-rendered.
    """
    articles = articles if articles is not None else booklet_articles(issue)
    check_galleys(articles)
    refreshed = 0
    cursor = 1

    for article in articles:
        first = cursor
        count = typeset.page_count(_galley_bytes(article))
        if (article.first_page, article.last_page) != (first, first + count - 1) \
                or article.galley_numbered_from != first:
            refreshed += 1
            for _ in range(MAX_PAGINATION_PASSES):
                article.first_page, article.last_page = first, first + count - 1
                article.save(update_fields=['first_page', 'last_page', 'updated_at'])
                rendered = typeset.refresh_galley(article) or count
                if rendered == count:
                    break
                # It came back a different length, so the range printed in it
                # is wrong. Set it again with the range it actually has.
                count = rendered
        cursor = first + count
    return refreshed


def number_as_entered(articles):
    """Keep the page numbers typed in by hand, and print them on the galleys.

    For a back issue whose numbering is already in print and in citations.
    Every article needs a first page; one whose galley does not match the range
    it was given is reported, not silently renumbered.
    """
    check_galleys(articles)
    unnumbered = [article.title for article in articles if not article.first_page]
    if unnumbered:
        raise BookletError(
            'Automatic pagination is off for this issue, so every article needs a first '
            'page. Missing: ' + '; '.join(unnumbered)
        )

    mismatched = []
    for article in articles:
        if article.galley_numbered_from != article.first_page:
            typeset.refresh_galley(article)
        count = typeset.page_count(_galley_bytes(article))
        if article.last_page and article.last_page - article.first_page + 1 != count:
            mismatched.append(
                f'"{article.title}" is entered as pp. {article.page_range} '
                f'but its PDF has {count} page{"s" if count != 1 else ""}'
            )
    return mismatched


# --- the cover -------------------------------------------------------------

A4 = (595.2756, 841.8898)
NAVY = (0x10 / 255, 0x20 / 255, 0x2f / 255)
ORANGE = (0xE6 / 255, 0x79 / 255, 0x18 / 255)
MIST = (0xc9 / 255, 0xd4 / 255, 0xde / 255)

COVER_FONTS = {
    'JeltanCoverSerif': 'Charis-Regular.ttf',
    'JeltanCoverSerifBold': 'Charis-Bold.ttf',
    'JeltanCoverSerifItalic': 'Charis-Italic.ttf',
    'JeltanCoverSans': 'NotoSans-Regular.ttf',
    'JeltanCoverSansBold': 'NotoSans-Bold.ttf',
}


def _cover_fonts():
    """Register the galley's own typefaces with the canvas the cover is drawn on."""
    import os

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    registered = pdfmetrics.getRegisteredFontNames()
    for name, filename in COVER_FONTS.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, os.path.join(typeset.FONT_DIRECTORY, filename)))


def render_cover(issue, journal, articles):
    """The front cover: the editor's own artwork if there is some, ours if not."""
    from reportlab.pdfgen import canvas as pdf_canvas

    buffer = io.BytesIO()
    sheet = pdf_canvas.Canvas(buffer, pagesize=A4)
    sheet.setTitle(f'{journal.name} — {issue.label}')

    drawn = False
    if issue.cover_image:
        try:
            _draw_uploaded_cover(sheet, issue)
            drawn = True
        except Exception:                                # noqa: BLE001
            # A cover that will not open is not a reason to have no booklet.
            logger.exception('Could not use the uploaded cover for issue %s', issue.pk)
    if not drawn:
        _draw_generated_cover(sheet, issue, journal, articles)

    sheet.showPage()
    sheet.save()
    return buffer.getvalue()


def _draw_uploaded_cover(sheet, issue):
    """Fill the page with the uploaded image, cropping rather than letterboxing.

    A cover with white bars down the sides looks like a mistake. Scaling to fill
    and centring loses a sliver of an image that is not quite A4, which a
    designer working to A4 will never notice.
    """
    from reportlab.lib.utils import ImageReader

    issue.cover_image.open('rb')
    try:
        image = ImageReader(io.BytesIO(issue.cover_image.read()))
    finally:
        issue.cover_image.close()

    width, height = A4
    image_width, image_height = image.getSize()
    scale = max(width / image_width, height / image_height)
    drawn_width, drawn_height = image_width * scale, image_height * scale
    sheet.drawImage(
        image, (width - drawn_width) / 2, (height - drawn_height) / 2,
        drawn_width, drawn_height,
    )


def _wrap(text, font, size, width):
    from reportlab.lib.utils import simpleSplit
    return simpleSplit(text or '', font, size, width)


def _draw_generated_cover(sheet, issue, journal, articles):
    """JELTAN's house cover, laid out on a canvas rather than through HTML.

    A cover is a fixed composition — colour to the edges, type placed by
    measure — which is exactly what the HTML renderer cannot do and a canvas
    does without effort.
    """
    _cover_fonts()
    width, height = A4
    margin = 54
    measure = width - 2 * margin

    sheet.setFillColorRGB(*NAVY)
    sheet.rect(0, 0, width, height, stroke=0, fill=1)
    sheet.setFillColorRGB(*ORANGE)
    sheet.rect(0, height - 14, width, 14, stroke=0, fill=1)

    # Masthead.
    y = height - 120
    sheet.setFillColorRGB(1, 1, 1)
    sheet.setFont('JeltanCoverSansBold', 64)
    sheet.drawString(margin - 3, y, journal.short_name or 'JELTAN')
    y -= 34
    sheet.setFont('JeltanCoverSerif', 15)
    for line in _wrap(journal.name, 'JeltanCoverSerif', 15, measure):
        sheet.drawString(margin, y, line)
        y -= 20
    if journal.tagline:
        sheet.setFillColorRGB(*MIST)
        sheet.setFont('JeltanCoverSerifItalic', 10.5)
        for line in _wrap(journal.tagline, 'JeltanCoverSerifItalic', 10.5, measure):
            sheet.drawString(margin, y, line)
            y -= 14

    # The issue's own line, on an orange band that runs off the left edge.
    y -= 30
    band = 34
    sheet.setFillColorRGB(*ORANGE)
    sheet.rect(0, y - band + 10, margin + measure * 0.72, band, stroke=0, fill=1)
    sheet.setFillColorRGB(1, 1, 1)
    sheet.setFont('JeltanCoverSansBold', 12.5)
    sheet.drawString(
        margin, y - 7,
        f'VOLUME {issue.volume}   ·   NUMBER {issue.number}   ·   {issue.year}',
    )
    y -= band + 34

    if issue.title:
        sheet.setFont('JeltanCoverSerifBold', 25)
        for line in _wrap(issue.title, 'JeltanCoverSerifBold', 25, measure)[:4]:
            sheet.drawString(margin, y, line)
            y -= 31
        y -= 14

    # In this issue: as many titles as fit above the imprint, never cut mid-entry.
    floor = 150
    entries = [(a.title, a.author_list) for a in articles]
    if entries and y - 60 > floor:
        sheet.setFillColorRGB(*ORANGE)
        sheet.setFont('JeltanCoverSansBold', 8.5)
        sheet.drawString(margin, y, 'IN THIS ISSUE')
        y -= 22
        shown = 0
        for title, authors in entries:
            title_lines = _wrap(title, 'JeltanCoverSerif', 11, measure)
            author_lines = _wrap(authors, 'JeltanCoverSans', 8, measure)[:1]
            needed = 14 * len(title_lines) + 11 * len(author_lines) + 10
            if y - needed < floor:
                break
            sheet.setFillColorRGB(1, 1, 1)
            sheet.setFont('JeltanCoverSerif', 11)
            for line in title_lines:
                sheet.drawString(margin, y, line)
                y -= 14
            sheet.setFillColorRGB(*MIST)
            sheet.setFont('JeltanCoverSans', 8)
            for line in author_lines:
                sheet.drawString(margin, y, line)
                y -= 11
            y -= 10
            shown += 1
        if shown < len(entries):
            sheet.setFillColorRGB(*MIST)
            sheet.setFont('JeltanCoverSans', 8)
            more = len(entries) - shown
            sheet.drawString(margin, y, f'and {more} more article{"s" if more != 1 else ""}')

    # Imprint.
    sheet.setFillColorRGB(*ORANGE)
    sheet.rect(margin, 112, 36, 2.5, stroke=0, fill=1)
    sheet.setFillColorRGB(1, 1, 1)
    sheet.setFont('JeltanCoverSansBold', 9.5)
    publisher = journal.publisher or 'English Language Teachers Association of Nigeria'
    for offset, line in enumerate(_wrap(publisher, 'JeltanCoverSansBold', 9.5, measure)[:2]):
        sheet.drawString(margin, 92 - offset * 13, line)
    issns = ' · '.join(
        f'ISSN {value} ({kind})'
        for value, kind in ((journal.issn_print, 'print'), (journal.issn_online, 'online'))
        if value
    )
    if issns:
        sheet.setFillColorRGB(*MIST)
        sheet.setFont('JeltanCoverSans', 8)
        sheet.drawString(margin, 62, issns)


# --- front matter ----------------------------------------------------------

def _render_part(part, context):
    html = render_to_string('journal/pdf/front_matter.html', {**context, 'part': part})
    return typeset.html_to_pdf(html)


def render_front_matter(issue, journal, articles):
    """The preliminary pages and contents, as PDF bytes, with where each part starts.

    Each part is rendered on its own so its length is known — the contents page
    has to say which page the editorial is on, and the only way to know that is
    to have laid out everything in front of it.

    Returns (pdf_bytes, [(heading, first page index), ...]).
    """
    from .models import EditorialBoardMember

    board = list(EditorialBoardMember.objects.filter(is_active=True))
    context = {
        'journal': journal,
        'issue': issue,
        'articles': articles,
        'board': board,
        'font_faces': typeset.font_faces(),
        'body_font': typeset.BODY_FONT,
        'ui_font': typeset.UI_FONT,
    }

    before = [('title', 'Title page'), ('imprint', 'Imprint')]
    if journal.aims_and_scope:
        before.append(('aims', 'Aims and scope'))
    if board:
        before.append(('board', 'Editorial board'))

    parts = [(heading, _render_part(part, context)) for part, heading in before]
    contents_start = sum(typeset.page_count(pdf) for _, pdf in parts)

    contents_context = dict(context, editorial_page=None)
    if issue.editorial:
        # Lay the contents out once to learn its length, then again with the
        # editorial's page number in it. A roman numeral more or less in one
        # line does not change how many pages the contents run to.
        draft = _render_part('contents', dict(contents_context, editorial_page='i'))
        contents_context['editorial_page'] = typeset.roman(
            contents_start + typeset.page_count(draft) + 1
        )
    parts.append(('Contents', _render_part('contents', contents_context)))
    if issue.editorial:
        parts.append(('Editorial', _render_part('editorial', context)))

    writer = PdfWriter()
    starts = []
    for heading, pdf in parts:
        starts.append((heading, len(writer.pages)))
        for page in PdfReader(io.BytesIO(pdf)).pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)

    # Counted from the title page, which carries no number of its own.
    numbered = typeset.stamp_page_numbers(out.getvalue(), start=1, numbering='roman', unnumbered={0})
    return numbered, starts


# --- the whole booklet -----------------------------------------------------

def build(issue):
    """Paginate the issue, bind the booklet, and store it on the issue.

    Raises BookletError with a reason an editor can act on. Returns a short
    note describing what was done, which is also kept on the issue.
    """
    from .models import JournalSettings

    journal = JournalSettings.load()
    articles = booklet_articles(issue)
    if not articles:
        raise BookletError('This issue has no published articles to put in a booklet.')

    warnings = []
    if issue.paginate_automatically:
        refreshed = paginate(issue, articles)
    else:
        refreshed = 0
        warnings = number_as_entered(articles)

    # Pagination saved through other instances' fields; read them back fresh.
    articles = booklet_articles(issue)

    cover = render_cover(issue, journal, articles)
    front, front_parts = render_front_matter(issue, journal, articles)

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(cover)).pages:
        writer.add_page(page)
    writer.add_outline_item('Cover', 0)

    front_start = len(writer.pages)
    for page in PdfReader(io.BytesIO(front)).pages:
        writer.add_page(page)
    for heading, index in front_parts:
        writer.add_outline_item(heading, front_start + index)

    article_starts = []
    for article in articles:
        start = len(writer.pages)
        for page in PdfReader(io.BytesIO(_galley_bytes(article))).pages:
            writer.add_page(page)
        article_starts.append((article, start, len(writer.pages) - 1))
        writer.add_outline_item(article.title, start)

    # What a PDF reader shows in its page box, matching what is printed.
    writer.set_page_label(0, 0, prefix='Cover')
    writer.set_page_label(front_start, front_start + typeset.page_count(front) - 1,
                          style=PageLabelStyle.LOWERCASE_ROMAN, start=1)
    for article, start, end in article_starts:
        writer.set_page_label(start, end, style=PageLabelStyle.DECIMAL,
                              start=article.galley_numbered_from or article.first_page or 1)

    writer.add_metadata({
        '/Title': f'{journal.name} — {issue.label}' + (f': {issue.title}' if issue.title else ''),
        '/Author': journal.publisher or '',
        '/Subject': issue.label,
    })
    out = io.BytesIO()
    writer.write(out)

    if issue.booklet:
        issue.booklet.delete(save=False)
    issue.booklet.save(issue.booklet_filename, ContentFile(out.getvalue()), save=False)

    note = (
        f'{len(articles)} article{"s" if len(articles) != 1 else ""}, '
        f'{len(writer.pages)} pages.'
    )
    if refreshed:
        note += f' Re-paginated {refreshed} article{"s" if refreshed != 1 else ""}.'
    if warnings:
        note += ' Check: ' + '; '.join(warnings) + '.'
    issue.booklet_note = note[:500]
    issue.booklet_built_at = timezone.now()
    issue.save(update_fields=['booklet', 'booklet_built_at', 'booklet_note'])
    return issue.booklet_note
