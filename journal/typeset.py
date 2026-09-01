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


def strip_repeated_front_matter(blocks, article):
    """Drop the title page the manuscript carries at the top of its own text.

    Almost every manuscript opens with its title, byline, abstract and keywords,
    and the galley template sets all four itself. Left alone they appear twice
    on the first page. Only a contiguous run at the very start is removed, so a
    phrase that happens to match further down is safe.
    """
    known = {_normalise(article.title), 'abstract', 'keywords', 'key words'}
    known |= {_normalise(author.full_name) for author in article.authors.all()}
    known |= {_normalise(article.abstract)} if article.abstract else set()
    known.discard('')

    index = 0
    for index, block in enumerate(blocks):
        text = getattr(block, 'text', '') or ''.join(
            part for part, _, _ in getattr(block, 'runs', [])
        )
        value = _normalise(text)
        if not value:
            continue
        if value in known:
            continue
        if value.startswith('keywords') or value.startswith('key words'):
            continue
        # The author's affiliation line sits in the same block, and is printed
        # from the author records rather than from the manuscript.
        if any(value in name or name in value for name in known if len(name) > 8):
            continue
        break
    else:
        index = len(blocks)
    return blocks[index:]


def blocks_to_html(blocks, figure_urls=None):
    """The article body as HTML, from the blocks read out of the manuscript."""
    figure_urls = figure_urls or {}
    html = []
    in_references = False

    for block in blocks:
        if block.kind == 'heading':
            level = min(max(block.level, 1), 3) + 1     # h1 is the article title
            text = escape(block.text)
            html.append(f'<h{level}>{text}</h{level}>')
            in_references = bool(ingest.REFERENCES_HEADING.match(block.text))

        elif block.kind == 'paragraph':
            body = runs_to_html(block.runs)
            if body:
                # A reference list is a hanging indent, not prose, and reads as
                # a wall of text without it.
                css = ' class="reference"' if in_references else ''
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


HEADING_TAG = re.compile(r'<h([234])>(.*?)</h\1>', re.DOTALL)


def outline_of(body_html):
    """The article's sections, as read out of the manuscript.

    Shown back to whoever uploaded the file: an outline that reads Introduction,
    Method, Results, Discussion says the document was understood, and one that
    reads like stray sentences says it was not. That judgement is quicker to
    make from a list of headings than by reading the whole body.
    """
    outline = []
    for match in HEADING_TAG.finditer(body_html or ''):
        text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        if text:
            outline.append({'level': int(match.group(1)) - 1, 'text': text})
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
                'pdf', 'typeset_at', 'typeset_note', 'updated_at',
            ])
        return False

    article.typeset_at = timezone.now()
    article.typeset_note = note
    if save:
        return _save_result(article)
    return True


RESULT_FIELDS = ['pdf', 'body_html', 'typeset_at', 'typeset_note', 'updated_at']


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
    """A cover page in the journal's design, in front of the author's own pages."""
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
    return 'A JELTAN cover page was added to the supplied PDF; its pages are unchanged.'


def _store_galley(article, content):
    name = f'{article.slug or "article"}-jeltan.pdf'
    article.pdf.save(name, ContentFile(content), save=False)


def _fall_back_to_source(article, source):
    """Publish what we were given rather than nothing at all."""
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
