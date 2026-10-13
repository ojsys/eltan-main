"""Turning what an author supplied into the article the journal publishes.

Every JELTAN article should look like a JELTAN article. What that takes depends
on what arrived, and the two cases are genuinely different:

A **Word manuscript** is unformatted content. Its structure — headings, lists,
tables, figures — can be read out of the file and set in the journal's own
template, so the whole galley is generated here and the full text can also be
shown on the article page.

**Somebody else's PDF** is already typeset, by a person, in a layout this code
cannot see. Re-flowing text scraped out of it would replace a designed page
with a worse one. So the original pages are kept exactly as they are and a
JELTAN cover page is put in front of them: uniform presentation of the journal's
front matter, without destroying anyone's typesetting.

Either way the reader downloads something that opens with the journal's own
first page, which is what "uniform" has to mean when the sources differ.
"""

import io
import logging
import os
import re

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import escape
from django.utils.text import slugify
from pypdf import PdfReader, PdfWriter
from xhtml2pdf import pisa

from . import ingest

logger = logging.getLogger(__name__)

FIGURE_DIRECTORY = 'journal/figures'

# The galley's fonts, shipped with the project rather than taken from whatever
# the server happens to have installed.
#
# PDF's built-in fonts — Times, Helvetica — carry WinAnsiEncoding, which stops
# at Latin-1. Every character past it comes out as a black box, and this is a
# Nigerian journal: Igbo and Yoruba are written with dot-below vowels (ụ ị ọ ẹ
# ṣ ṅ) that live in Latin Extended Additional, and a reference list will reach
# further still. A galley that prints "Igboan■s■" for Igboanụsị is not a galley.
#
# Charis SIL is drawn by SIL for exactly these languages and reads as a
# scholarly serif; Noto Sans covers the same ground for the interface type.
# Both are under the SIL Open Font License, and the licences ship beside them.
FONT_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'journal', 'fonts')

BODY_FONT = 'CharisSIL'
UI_FONT = 'NotoSans'

FONT_FACES = [
    (BODY_FONT, 'Charis-Regular.ttf', 'normal', 'normal'),
    (BODY_FONT, 'Charis-Bold.ttf', 'bold', 'normal'),
    (BODY_FONT, 'Charis-Italic.ttf', 'normal', 'italic'),
    (BODY_FONT, 'Charis-BoldItalic.ttf', 'bold', 'italic'),
    (UI_FONT, 'NotoSans-Regular.ttf', 'normal', 'normal'),
    (UI_FONT, 'NotoSans-Bold.ttf', 'bold', 'normal'),
]


def font_faces():
    """The @font-face rules for the galley stylesheet.

    Built here rather than written into the template so the paths are absolute
    and correct wherever the project is checked out, and so a missing file is
    noticed once, here, instead of silently falling back to a font that cannot
    spell half the journal's authors.
    """
    faces = []
    for family, filename, weight, style in FONT_FACES:
        path = os.path.join(FONT_DIRECTORY, filename)
        if not os.path.isfile(path):
            logger.error('Galley font missing: %s', path)
            continue
        faces.append({
            'family': family, 'path': path, 'weight': weight, 'style': style,
        })
    return faces


class TypesetError(Exception):
    """Raised when a galley could not be produced from the source."""


# --- blocks to HTML --------------------------------------------------------

def runs_to_html(runs):
    """Inline HTML for a paragraph's runs.

    Text is escaped first and marked up second, so nothing an author typed —
    or pasted in from a web page — can introduce a tag of its own.
    """
    parts = []
    for text, bold, italic in runs:
        piece = escape(text)
        if italic:
            piece = f'<em>{piece}</em>'
        if bold:
            piece = f'<strong>{piece}</strong>'
        parts.append(piece)
    return ''.join(parts).strip()


def _normalise(text):
    return re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip()


def _block_text(block):
    return getattr(block, 'text', '') or ''.join(
        part for part, _, _ in getattr(block, 'runs', [])
    )


# How far into the document the manuscript's own title page can reach. Names,
# affiliations, emails and a funding note all sit in there; twenty-five blocks
# is generous for that and nowhere near the body of any real paper.
FRONT_MATTER_BLOCKS = 25

FRONT_MATTER_LABEL = re.compile(r'^\s*(abstract|keywords?|key\s*words?)\b', re.IGNORECASE)


def strip_repeated_front_matter(blocks, article):
    """Drop what the galley sets itself, and only that.

    A manuscript opens with its own title page — title, byline, affiliations,
    abstract, keywords — and the galley prints the title, the abstract and the
    keywords. Left alone, a reader gets the abstract twice: once in the box and
    once again in the body, running onto the next page.

    The byline is the deliberate exception. The galley prints none of its own:
    the authors as the manuscript gives them — their order, their affiliations,
    their emails, their titles — are better than anything reconstructed from the
    article record, and matching the two closely enough to de-duplicate is
    guesswork. So names stay where the author put them, and the article record
    supplies the byline on the web page instead.

    Which rules out cutting a prefix. Real manuscripts put the byline after the
    keywords, before them, or between the abstract and the title, and any scan
    that stops at the first line it does not recognise stops on a name. So this
    looks at the whole opening instead and removes only the three things the
    galley is about to print again.
    """
    title = _normalise(article.title)
    abstract = _normalise(article.abstract)
    names = {_normalise(author.full_name) for author in article.authors.all()}
    names.discard('')

    kept = []
    in_byline = False
    for index, block in enumerate(blocks):
        opening = index < FRONT_MATTER_BLOCKS
        if opening:
            # A PDF has no paragraph marks, so its title and byline usually
            # arrive as one run-together block: dropping it whole would take the
            # authors with it, and keeping it whole prints the title twice.
            # Trimming the title off the front leaves exactly the byline.
            _trim_reprinted_title(block, title)
        if opening and _is_reprinted(block, title, abstract):
            continue

        # Mark the manuscript's own byline — the names, and the affiliations and
        # addresses that run on from them — rather than dropping it. The galley
        # prints it, because it is the authors' own; the web article hides it,
        # because the same names are already set properly at the top of the page
        # from the article record. One pass, two presentations.
        if opening:
            value = _normalise(_block_text(block))
            if value and any(name in value or value in name for name in names):
                in_byline = True
            elif in_byline and block.kind == 'heading':
                in_byline = False
            if in_byline and block.kind != 'heading':
                block.is_byline = True

        kept.append(block)
    return kept


def _trim_reprinted_title(block, title):
    """Strip a repeated title from the front of a block that also carries more.

    Only touches single-run blocks, which is what text read out of a PDF looks
    like. A Word manuscript keeps its runs — and its bold and italic — intact,
    because there the title is its own paragraph and never needs this.
    """
    if not title or block.kind != 'paragraph':
        return
    runs = getattr(block, 'runs', None)
    if not runs or len(runs) != 1:
        return

    text = runs[0][0]
    value = _normalise(text)
    if value == title or not value.startswith(title):
        return

    # Cut by words rather than characters: the normalised title and the raw text
    # have the same words in the same order, whatever the punctuation and
    # spacing between them, so dropping as many words as the title has lands
    # exactly at its end.
    words = text.split()
    remainder = ' '.join(words[len(title.split()):]).lstrip(' \t.,:;-–—')
    if remainder:
        block.runs = [(remainder, runs[0][1], runs[0][2])]
        block.text = remainder


def _is_reprinted(block, title, abstract):
    """Whether the galley is going to print this block's content anyway."""
    text = _block_text(block)
    value = _normalise(text)
    if not value:
        return False

    if title and value == title:
        return True
    # "Abstract" on its own, and the "Keywords: a; b; c" line whole.
    if FRONT_MATTER_LABEL.match(text):
        return True
    # The abstract itself, whether the manuscript sets it as one paragraph or
    # several. A block has to account for a real share of the abstract to count
    # as part of it: papers do sometimes repeat one sentence of the abstract in
    # the introduction, and that sentence is the author's to keep.
    if abstract and (value in abstract or abstract in value):
        if len(value) >= max(40, len(abstract) // 4):
            return True
    return False


def blocks_to_html(blocks, figure_urls=None):
    """The article body as HTML, from the blocks read out of the manuscript."""
    figure_urls = figure_urls or {}
    html = []
    used_anchors = set()
    in_references = False

    for block in blocks:
        if block.kind == 'heading':
            level = min(max(block.level, 1), 3) + 1     # h1 is the article title
            text = escape(block.text)
            # An id per heading, so the web article can offer a contents list
            # that jumps to a section — the reason for reading a paper online
            # rather than downloading it is usually to find one part of it.
            anchor = _anchor(block.text, used_anchors)
            html.append(f'<h{level} id="{anchor}">{text}</h{level}>')
            in_references = bool(ingest.REFERENCES_HEADING.match(block.text))

        elif block.kind == 'paragraph':
            body = runs_to_html(block.runs)
            if body:
                # A reference list is a hanging indent, not prose, and reads as
                # a wall of text without it.
                classes = []
                if in_references:
                    classes.append('reference')
                if getattr(block, 'is_byline', False):
                    classes.append('manuscript-byline')
                css = f' class="{" ".join(classes)}"' if classes else ''
                html.append(f'<p{css}>{body}</p>')
            for name in getattr(block, 'images', []) or []:
                html.append(_figure_html(name, figure_urls))

        elif block.kind == 'figure':
            for name in block.images:
                html.append(_figure_html(name, figure_urls))

        elif block.kind == 'quote':
            body = runs_to_html(block.runs)
            if body:
                html.append(f'<blockquote>{body}</blockquote>')

        elif block.kind == 'list':
            items = ''.join(f'<li>{runs_to_html(runs)}</li>' for runs in block.items)
            html.append(f'<ul>{items}</ul>')

        elif block.kind == 'table':
            html.append(_table_html(block.rows))

    return '\n'.join(html)


HEADING_TAG = re.compile(
    r'<h([234])(?:\s+id="([^"]*)")?>(.*?)</h\1>', re.DOTALL,
)


def _anchor(text, used):
    """A stable, unique id for a heading, readable in a URL bar."""
    base = slugify(text)[:60] or 'section'
    anchor = base
    suffix = 2
    while anchor in used:
        anchor = f'{base}-{suffix}'
        suffix += 1
    used.add(anchor)
    return anchor


def outline_of(body_html):
    """The article's sections, as read out of the manuscript.

    Shown back to whoever uploaded the file: an outline that reads Introduction,
    Method, Results, Discussion says the document was understood, and one that
    reads like stray sentences says it was not. That judgement is quicker to
    make from a list of headings than by reading the whole body.
    """
    outline = []
    for match in HEADING_TAG.finditer(body_html or ''):
        text = re.sub(r'<[^>]+>', '', match.group(3)).strip()
        if text:
            outline.append({
                'level': int(match.group(1)) - 1,
                'text': text,
                # Articles typeset before headings carried ids have none; the
                # contents list shows those as plain text rather than as links
                # that would go nowhere.
                'anchor': match.group(2) or '',
            })
    return outline


def _figure_html(name, figure_urls):
    url = figure_urls.get(name)
    if not url:
        return ''
    return f'<figure><img src="{escape(url)}" alt=""></figure>'


def _table_html(rows):
    if not rows:
        return ''
    head, *body = rows
    header = ''.join(f'<th>{escape(cell)}</th>' for cell in head)
    lines = [f'<table><thead><tr>{header}</tr></thead><tbody>']
    for row in body:
        cells = ''.join(f'<td>{escape(cell)}</td>' for cell in row)
        lines.append(f'<tr>{cells}</tr>')
    lines.append('</tbody></table>')
    return ''.join(lines)


# --- storing the figures ---------------------------------------------------

def store_figures(article, media):
    """Save a manuscript's images and return {name: url} for the body HTML."""
    urls = {}
    for name, content in media.items():
        path = f'{FIGURE_DIRECTORY}/{article.pk}/{name}'
        if default_storage.exists(path):
            default_storage.delete(path)
        saved = default_storage.save(path, ContentFile(content))
        urls[name] = default_storage.url(saved)
    return urls


def clear_figures(article):
    """Drop the figures of a previous run, so re-typesetting does not stack up."""
    directory = f'{FIGURE_DIRECTORY}/{article.pk}'
    try:
        _, files = default_storage.listdir(directory)
    except (FileNotFoundError, NotImplementedError, OSError):
        return
    for name in files:
        default_storage.delete(f'{directory}/{name}')


# --- HTML to PDF -----------------------------------------------------------

def link_callback(uri, rel):
    """Point the PDF renderer at files on disk rather than over the network.

    xhtml2pdf fetches by URI; a media URL would mean the server making an HTTP
    request to itself, which fails behind auth, on a different media domain, and
    whenever the site is not reachable from its own machine.
    """
    for url, root in (
        (getattr(settings, 'MEDIA_URL', None), getattr(settings, 'MEDIA_ROOT', None)),
        (getattr(settings, 'STATIC_URL', None), getattr(settings, 'STATIC_ROOT', None)),
    ):
        if url and root and uri.startswith(url):
            path = os.path.join(root, uri.replace(url, '', 1))
            if os.path.isfile(path):
                return path

    if uri.startswith('/') and os.path.isfile(uri):
        return uri
    return uri


def html_to_pdf(html):
    """Render HTML to PDF bytes, or raise with what went wrong."""
    buffer = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html), dest=buffer, link_callback=link_callback)
    if result.err:
        raise TypesetError(f'The page could not be rendered ({result.err} errors).')
    return buffer.getvalue()


def render_context(article, body_html='', full_text=True):
    from .models import JournalSettings

    return {
        'journal': JournalSettings.load(),
        'article': article,
        'authors': list(article.authors.all()),
        'body_html': body_html,
        'full_text': full_text,
        'generated_at': timezone.now(),
        'font_faces': font_faces(),
        'body_font': BODY_FONT,
        'ui_font': UI_FONT,
    }


# --- page numbers ----------------------------------------------------------

# Where the folio sits: the bottom right corner, inside the right margin and on
# the footer's baseline. Offsets are from the page's own edges, so the number
# lands in the same place on an author's US Letter page as on a JELTAN A4 one.
FOLIO_RIGHT = 2.1 * 28.3465        # pt — the galley's right margin
FOLIO_BASELINE = 1.73 * 28.3465    # pt above the bottom edge — the footer line
FOLIO_SIZE = 7.5
FOLIO_COLOUR = (0x8c / 255, 0x9c / 255, 0xab / 255)
FOLIO_FONT = 'JeltanFolio'

ROMAN = [
    (1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'), (100, 'c'), (90, 'xc'),
    (50, 'l'), (40, 'xl'), (10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i'),
]


def roman(number):
    """Lower-case roman numerals — the front matter's page numbers."""
    out = []
    for value, letters in ROMAN:
        while number >= value:
            out.append(letters)
            number -= value
    return ''.join(out)


def _folio_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if FOLIO_FONT not in pdfmetrics.getRegisteredFontNames():
        path = os.path.join(FONT_DIRECTORY, 'NotoSans-Regular.ttf')
        if not os.path.isfile(path):
            return 'Helvetica'
        pdfmetrics.registerFont(TTFont(FOLIO_FONT, path))
    return FOLIO_FONT


def stamp_page_numbers(pdf_bytes, start=1, numbering='arabic', unnumbered=()):
    """Print page numbers onto a finished PDF, counting from `start`.

    xhtml2pdf's own page counter always begins at 1, and an issue needs its
    second article to begin where the first one ended. Numbering after the fact
    is also the only way to number pages this code did not lay out — an
    author's own PDF kept behind a JELTAN cover — so every galley is numbered
    the same way, whatever produced it.

    Each number sits on a small white ground. On a JELTAN page that is
    invisible; on an author's page it keeps the number legible over whatever
    they had there, and when a galley is numbered again after its articles are
    reordered, it covers the number it carried before.

    `unnumbered` holds 0-based page indexes that are counted but left blank,
    as a book leaves its title page.
    """
    from reportlab.pdfgen import canvas as pdf_canvas

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    font = _folio_font()

    for index, page in enumerate(reader.pages):
        if index not in unnumbered:
            number = start + index
            label = roman(number) if numbering == 'roman' else str(number)
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            overlay = io.BytesIO()
            sheet = pdf_canvas.Canvas(overlay, pagesize=(width, height))
            text_width = sheet.stringWidth(label, font, FOLIO_SIZE)
            right = float(page.mediabox.left) + width - FOLIO_RIGHT
            baseline = float(page.mediabox.bottom) + FOLIO_BASELINE
            sheet.setFillColorRGB(1, 1, 1)
            sheet.rect(right - text_width - 3, baseline - 3, text_width + 5, FOLIO_SIZE + 5,
                       stroke=0, fill=1)
            sheet.setFillColorRGB(*FOLIO_COLOUR)
            sheet.setFont(font, FOLIO_SIZE)
            sheet.drawRightString(right, baseline, label)
            sheet.save()
            page.merge_page(PdfReader(io.BytesIO(overlay.getvalue())).pages[0])
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def page_count(pdf_bytes):
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


# --- putting a cover on somebody else's PDF --------------------------------

def prepend_cover(cover_pdf, source_pdf):
    """Put the journal's first page in front of the pages the author supplied."""
    writer = PdfWriter()
    for source in (cover_pdf, source_pdf):
        reader = PdfReader(io.BytesIO(source))
        if getattr(reader, 'is_encrypted', False):
            try:
                reader.decrypt('')
            except Exception as exc:                     # noqa: BLE001
                raise TypesetError('The supplied PDF is password protected.') from exc
        for page in reader.pages:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# --- the whole job ---------------------------------------------------------

def typeset(article, save=True):
    """Produce the galley readers download, and the full text if there is one.

    Never raises, and that has to hold for the database too, not only for the
    parsing: a manuscript that cannot be typeset must still be publishable, so
    the source file is used as the galley and the reason is recorded on the
    article for an editor to read. Returns whether a JELTAN galley was produced.
    """
    source = article.source_file or article.pdf
    if not source:
        article.typeset_note = 'There is no file to typeset.'
        if save:
            article.save(update_fields=['typeset_note', 'updated_at'])
        return False

    extension = article.source_extension or article.galley_extension
    try:
        if extension == '.docx':
            note = _typeset_from_manuscript(article, source)
        else:
            note = _typeset_from_pdf(article, source)
    except Exception as exc:                             # noqa: BLE001 - see docstring
        logger.exception('Typesetting failed for article %s', article.pk)
        _fall_back_to_source(article, source)
        article.typeset_at = None
        article.typeset_note = f'Could not typeset: {exc}'[:300]
        if save:
            article.save(update_fields=[
                'pdf', 'typeset_at', 'typeset_note', 'galley_numbered_from', 'updated_at',
            ])
        return False

    article.typeset_at = timezone.now()
    article.typeset_note = note
    if save:
        return _save_result(article)
    return True


RESULT_FIELDS = [
    'pdf', 'body_html', 'typeset_at', 'typeset_note', 'galley_numbered_from', 'updated_at',
]


def _save_result(article):
    """Write the result, giving up the body text rather than the whole galley.

    The galley is already on disk by this point; the body text is the one part
    that still has to survive a round trip to the database. When it cannot —
    a column that will not store the characters in it, a value too long — then
    keeping the PDF and recording why the full text is missing beats losing
    both to an exception halfway through.
    """
    try:
        article.save(update_fields=RESULT_FIELDS)
        return True
    except Exception as exc:                             # noqa: BLE001
        logger.exception('Could not store the typeset body for article %s', article.pk)
        article.body_html = ''
        article.typeset_at = None
        article.typeset_note = (
            f'The galley was generated, but the full text could not be stored: {exc}'
        )[:300]

    try:
        article.save(update_fields=RESULT_FIELDS)
    except Exception:                                    # noqa: BLE001
        # Nothing more to try. The caller is told it failed and the article keeps
        # whatever it had, rather than the request dying on the way out.
        logger.exception('Could not record the typesetting result for %s', article.pk)
    return False


def _typeset_from_manuscript(article, source):
    blocks, media = ingest.read_docx_blocks(source)
    blocks = strip_repeated_front_matter(blocks, article)
    clear_figures(article)
    figure_urls = store_figures(article, media) if media else {}

    body_html = blocks_to_html(blocks, figure_urls)
    html = render_to_string(
        'journal/pdf/article.html', render_context(article, body_html, full_text=True),
    )
    _store_galley(article, html_to_pdf(html))
    article.body_html = body_html

    figures = f', {len(media)} figure{"s" if len(media) != 1 else ""}' if media else ''
    return f'Typeset from the Word manuscript: {len(blocks)} blocks{figures}.'


def _typeset_from_pdf(article, source):
    """Re-set a supplied PDF in the journal's own type, or cover it if we cannot.

    Every JELTAN article is meant to read as one journal: the same body face, the
    same size, the same title block, whatever the author's own file looked like.
    A PDF carries none of that structure, so the text is read back out and put
    through the very same template a Word manuscript uses — that, and only that,
    is what makes two articles from two different authors match.

    The text does not always come back. A scan has none, and a paper built out of
    equations or wide tables loses more by being re-flowed than it gains by
    matching. Those fall back to the author's pages behind a JELTAN cover, and
    the note says so, so an editor can see which articles did not convert.
    """
    mode = getattr(article, 'typeset_mode', None) or article.TYPESET_AUTO

    if mode == article.TYPESET_ORIGINAL:
        return _cover_supplied_pdf(
            article, source,
            "set to keep the author's own pages",
        )

    try:
        source.open('rb')
        try:
            data = source.read()
        finally:
            source.close()
        blocks, _ = ingest.read_pdf_blocks(io.BytesIO(data))
        page_count = len(PdfReader(io.BytesIO(data)).pages)
    except Exception as exc:                             # noqa: BLE001
        logger.warning('Could not read text from the PDF for article %s: %s', article.pk, exc)
        return _cover_supplied_pdf(article, source, f'its text could not be read ({exc})')

    readable, reason = ingest.pdf_text_quality(blocks, page_count)
    if not readable and mode != article.TYPESET_JELTAN:
        return _cover_supplied_pdf(article, source, reason)

    blocks = strip_repeated_front_matter(blocks, article)
    body_html = blocks_to_html(blocks, {})
    html = render_to_string(
        'journal/pdf/article.html', render_context(article, body_html, full_text=True),
    )
    _store_galley(article, html_to_pdf(html))
    article.body_html = body_html

    forced = ' (forced)' if not readable else ''
    return (
        f'Re-set from the supplied PDF in JELTAN type{forced}: '
        f'{len(blocks)} blocks from {page_count} page{"s" if page_count != 1 else ""}.'
    )


def _cover_supplied_pdf(article, source, reason):
    """Keep the author's pages exactly as they are, behind a JELTAN cover page."""
    html = render_to_string(
        'journal/pdf/article.html', render_context(article, '', full_text=False),
    )
    source.open('rb')
    try:
        merged = prepend_cover(html_to_pdf(html), source.read())
    finally:
        source.close()

    _store_galley(article, merged)
    # The body was not re-set, so there is no trustworthy full text to show.
    article.body_html = ''
    return f"A JELTAN cover page was added and the author's pages kept: {reason}."[:300]


def _store_galley(article, content):
    # Numbered from the article's first page in its issue, so the galley a
    # reader downloads on its own carries the same page numbers as the issue
    # booklet and the citation printed inside it.
    article.galley_numbered_from = article.first_page or 1
    content = stamp_page_numbers(content, start=article.galley_numbered_from)
    old = article.pdf.name if article.pdf else ''
    name = f'{article.slug or "article"}-jeltan.pdf'
    article.pdf.save(name, ContentFile(content), save=False)
    _discard_previous_galley(article, old)


def _discard_previous_galley(article, old):
    """Delete the galley the new one replaced, when it was ours to delete.

    Paginating an issue re-renders its galleys, and every render would otherwise
    leave the last one on disk. Only a file this code generated goes, and only
    while the source is kept separately — a PDF that *is* the author's original
    is never removed here. Called after the new file is saved, so a failed save
    never leaves the article pointing at nothing.
    """
    if not old or old == article.pdf.name or not article.source_file:
        return
    if old == article.source_file.name or '-jeltan' not in old.rsplit('/', 1)[-1]:
        return
    try:
        article.pdf.storage.delete(old)
    except Exception:                                    # noqa: BLE001
        logger.warning('Could not delete the previous galley %s', old)


def refresh_galley(article):
    """Bring a galley up to date with its page numbers, as cheaply as possible.

    Called when an issue is paginated. The page range is printed in two places
    on a galley — the locator line and the citation — and on every page's folio,
    so all three have to follow when an article moves. In order of preference:

    1. Full text already extracted: render it again from `body_html`. No parsing.
    2. The supplied file is still on record: typeset it again from that.
    3. Neither (a back-issue PDF loaded before sources were kept): number the
       pages it has. Its front page may still show the old range; the note says
       so, and re-uploading the source is the fix.

    Saves the article. Returns the galley's page count, or None if it has no PDF.
    """
    if article.body_html:
        html = render_to_string(
            'journal/pdf/article.html',
            render_context(article, article.body_html, full_text=True),
        )
        _store_galley(article, html_to_pdf(html))
        article.save(update_fields=['pdf', 'galley_numbered_from', 'updated_at'])
    elif article.source_file:
        typeset(article)
        article.refresh_from_db()
    elif article.pdf and article.galley_extension == '.pdf':
        old = article.pdf.name
        article.galley_numbered_from = article.first_page or 1
        content = stamp_page_numbers(_read(article.pdf), start=article.galley_numbered_from)
        article.pdf.save(old.rsplit('/', 1)[-1], ContentFile(content), save=False)
        if article.pdf.name != old and '-jeltan' in old.rsplit('/', 1)[-1]:
            article.pdf.storage.delete(old)
        article.typeset_note = (
            'Page numbers were printed on the existing PDF. Its first page may still show '
            'the old page range: upload the source file again to re-set it.'
        )
        article.save(update_fields=['pdf', 'typeset_note', 'galley_numbered_from', 'updated_at'])

    if not article.pdf or article.galley_extension != '.pdf':
        return None
    return page_count(_read(article.pdf))


def _read(field):
    field.open('rb')
    try:
        return field.read()
    finally:
        field.close()


def _fall_back_to_source(article, source):
    """Publish what we were given rather than nothing at all."""
    article.galley_numbered_from = None
    try:
        source.open('rb')
        try:
            article.pdf.save(
                f'{article.slug or "article"}{article.source_extension or ".pdf"}',
                ContentFile(source.read()), save=False,
            )
        finally:
            source.close()
    except Exception:                                    # noqa: BLE001
        logger.exception('Could not fall back to the source file for %s', article.pk)
