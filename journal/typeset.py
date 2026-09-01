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

    Never raises: a manuscript that cannot be typeset must still be publishable,
    so the source file is used as the galley and the reason is recorded on the
    article for an editor to read.
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
        article.save(update_fields=[
            'pdf', 'body_html', 'typeset_at', 'typeset_note', 'updated_at',
        ])
    return True


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
