"""Reading what a ready-to-publish file says about itself.

Bulk import exists to save typing, not to be believed. Everything in here is a
guess from the first page of a document that was laid out for a human eye, and
every guess lands on a review screen where an editor confirms or corrects it
before anything becomes public. So the rules below are deliberately timid: a
blank field an editor fills in costs a minute, while a plausible-looking wrong
author in the published record is a correction notice.

No new dependencies: PDFs go through pypdf, which the project already has for
its galleys, and a .docx is a zip of XML that the standard library opens.
"""

import logging
import re
import zipfile
from xml.etree import ElementTree as ET

from pypdf import PdfReader

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = ['.pdf', '.docx']

# Only the front matter is worth reading: title, byline, abstract and keywords
# all live there, and the body is noise for this purpose.
PAGES_SCANNED = 2
MAX_CHARS = 12000
MAX_ABSTRACT_CHARS = 3000

DOCX_NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
}

# Where the abstract stops. A paper's abstract is followed by one of these
# almost without exception.
ABSTRACT_ENDS = re.compile(
    r'^\s*(keywords?|key\s*words?|introduction|1\.?\s+introduction|background)\b',
    re.IGNORECASE,
)
KEYWORDS_LINE = re.compile(r'^\s*(keywords?|key\s*words?)\s*[:\-–]\s*(?P<value>.+)$', re.IGNORECASE)
ABSTRACT_HEADING = re.compile(r'^\s*abstract\s*[:\-–]?\s*(?P<rest>.*)$', re.IGNORECASE)

# Lines that are furniture rather than content — running heads, page numbers,
# DOIs, the journal's own name on the front page.
FURNITURE = re.compile(
    r'^\s*(page\s*\d+|\d{1,4}|doi\s*:?.*|https?://\S+|issn.*|vol(ume)?\.?\s*\d+.*|'
    r'received\s*:.*|accepted\s*:.*|published\s*:.*)\s*$',
    re.IGNORECASE,
)

# What PDF and Word producers write into the title property when nobody set
# one. Trusting these puts "untitled" on the front page of the journal.
PLACEHOLDER_TITLE = re.compile(
    r'^\s*(untitled|no title|document\s*\d*|doc\d*|new document|slide\s*\d*|'
    r'presentation\d*|book\d*|paper\d*|article\d*|final|draft|template)\s*$',
    re.IGNORECASE,
)

# A byline is names. Anything with one of these in it is an affiliation, an
# address or a correspondence note, whatever else it may also contain.
NOT_A_NAME = re.compile(
    r'@|\d|\b(university|universite|college|school|department|dept|faculty|institute|'
    r'polytechnic|centre|center|academy|corresponding|author|email|e-mail|abstract|'
    r'nigeria|ghana|kenya|africa|p\.?\s*m\.?\s*b|po box)\b',
    re.IGNORECASE,
)


class ExtractedMetadata:
    """What a file appears to claim about itself. All of it provisional."""

    def __init__(self, title='', abstract='', keywords='', authors=None, error=''):
        self.title = title
        self.abstract = abstract
        self.keywords = keywords
        self.authors = authors or []
        self.error = error

    def __repr__(self):
        return f'<ExtractedMetadata {self.title[:40]!r} authors={len(self.authors)}>'


def extension_of(name):
    return ('.' + name.rsplit('.', 1)[1].lower()) if '.' in (name or '') else ''


def title_from_filename(name):
    """The last resort, and a decent one: people name files after the paper.

    Separators become spaces and a trailing version marker goes, but the words
    are left exactly as they were typed — 'ESL' must not come back as 'Esl'.
    """
    stem = (name or '').rsplit('/', 1)[-1]
    stem = stem.rsplit('.', 1)[0] if '.' in stem else stem
    stem = re.sub(r'[_\-]+', ' ', stem)
    stem = re.sub(r'\s*\(\d+\)\s*$', '', stem)
    stem = re.sub(r'\s*[-–]?\s*(final|revised|v\d+|copy|draft)\s*$', '', stem, flags=re.IGNORECASE)
    return re.sub(r'\s{2,}', ' ', stem).strip()


def extract(uploaded, filename=None):
    """Read a PDF or .docx and report what it seems to say.

    Never raises: a file that cannot be read still has to import, because an
    editor typing the metadata by hand is a worse day than a failed batch.
    """
    name = filename or getattr(uploaded, 'name', '') or ''
    extension = extension_of(name)

    try:
        if extension == '.pdf':
            lines, embedded_title = _read_pdf(uploaded)
        elif extension == '.docx':
            lines, embedded_title = _read_docx(uploaded)
        else:
            return ExtractedMetadata(
                title=title_from_filename(name),
                error=f'{extension or "This file type"} cannot be read for metadata.',
            )
    except Exception as exc:                      # noqa: BLE001 - see docstring
        logger.warning('Could not read %s for metadata: %s', name, exc)
        return ExtractedMetadata(
            title=title_from_filename(name),
            error='The file could not be read — its details need typing in.',
        )
    finally:
        _rewind(uploaded)

    return _interpret(lines, embedded_title, name)


# --- readers ---------------------------------------------------------------

def _rewind(uploaded):
    """Hand the file back unread, so the same upload can still be saved."""
    try:
        uploaded.seek(0)
    except Exception:                             # noqa: BLE001
        pass


def _read_pdf(uploaded):
    _rewind(uploaded)
    reader = PdfReader(uploaded)
    text = []
    for page in reader.pages[:PAGES_SCANNED]:
        text.append(page.extract_text() or '')
        if sum(len(part) for part in text) > MAX_CHARS:
            break

    embedded = ''
    try:
        embedded = (reader.metadata.title or '') if reader.metadata else ''
    except Exception:                             # noqa: BLE001
        embedded = ''
    return _to_lines('\n'.join(text)), embedded


def _read_docx(uploaded):
    _rewind(uploaded)
    with zipfile.ZipFile(uploaded) as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
        embedded = ''
        if 'docProps/core.xml' in archive.namelist():
            try:
                core = ET.fromstring(archive.read('docProps/core.xml'))
                node = core.find('dc:title', DOCX_NS)
                embedded = (node.text or '') if node is not None else ''
            except ET.ParseError:
                embedded = ''

    lines = []
    for paragraph in document.iter(f'{{{DOCX_NS["w"]}}}p'):
        # A run break inside a word is a formatting artefact, not a space, so
        # the runs of one paragraph are joined without one.
        runs = [node.text or '' for node in paragraph.iter(f'{{{DOCX_NS["w"]}}}t')]
        lines.append(''.join(runs))
        if sum(len(line) for line in lines) > MAX_CHARS:
            break
    return _to_lines('\n'.join(lines)), embedded


def _to_lines(text):
    cleaned = []
    for raw in (text or '').splitlines():
        line = re.sub(r'\s+', ' ', raw).strip()
        if line and not FURNITURE.match(line):
            cleaned.append(line)
    return cleaned


# --- interpretation --------------------------------------------------------

def _looks_like_a_title(value):
    value = (value or '').strip()
    if not 8 <= len(value) <= 300:
        return False
    # Word writes "Microsoft Word - thesis draft 3.doc" into the title property
    # of anything printed from it, which is a filename, not a title.
    if re.match(r'^microsoft word\b', value, re.IGNORECASE):
        return False
    if extension_of(value) in ('.doc', '.docx', '.pdf', '.rtf'):
        return False
    if PLACEHOLDER_TITLE.match(value):
        return False
    # A paper's title is a phrase. One word is a placeholder far more often than
    # it is a title, and the filename is a better guess than "untitled".
    if len(value.split()) < 2:
        return False
    return bool(re.search(r'[A-Za-z]{3}', value))


def _interpret(lines, embedded_title, filename):
    title = embedded_title.strip() if _looks_like_a_title(embedded_title) else ''
    title_index = -1

    if not title:
        for index, line in enumerate(lines[:12]):
            if ABSTRACT_HEADING.match(line):
                break
            if _looks_like_a_title(line):
                title, title_index = line, index
                break
    else:
        # The embedded title was used, but the byline still sits after wherever
        # that title appears in the text.
        for index, line in enumerate(lines[:12]):
            if line.lower().startswith(title.lower()[:30]):
                title_index = index
                break

    if not title:
        title = title_from_filename(filename)

    abstract, abstract_index = _find_abstract(lines)
    keywords = _find_keywords(lines)
    authors = _find_authors(lines, title_index, abstract_index)

    return ExtractedMetadata(
        title=title.strip(),
        abstract=abstract,
        keywords=keywords,
        authors=authors,
    )


def _find_abstract(lines):
    for index, line in enumerate(lines):
        heading = ABSTRACT_HEADING.match(line)
        if not heading:
            continue

        collected = []
        rest = heading.group('rest').strip()
        if rest:
            collected.append(rest)
        for following in lines[index + 1:]:
            if ABSTRACT_ENDS.match(following):
                break
            collected.append(following)
            if sum(len(part) for part in collected) > MAX_ABSTRACT_CHARS:
                break

        text = ' '.join(collected).strip()
        if len(text) >= 40:
            return text[:MAX_ABSTRACT_CHARS], index
        return '', index
    return '', -1


def _find_keywords(lines):
    for line in lines:
        found = KEYWORDS_LINE.match(line)
        if found:
            value = found.group('value').strip().rstrip('.')
            # Semicolons are as common as commas in a keyword line.
            parts = [part.strip() for part in re.split(r'[;,]', value) if part.strip()]
            return ', '.join(parts[:8])[:300]
    return ''


def _find_authors(lines, title_index, abstract_index):
    """The byline, if a line between the title and the abstract clearly is one.

    A wrong author is worse than no author, so this gives up easily: one line,
    every part a plausible personal name, nothing that smells of an address.
    """
    if title_index < 0:
        return []
    end = abstract_index if abstract_index > title_index else title_index + 4

    for line in lines[title_index + 1:end]:
        # Superscript affiliation markers survive extraction as digits and stars.
        candidate = re.sub(r'[\d*†‡§¶]', '', line).strip(' ,;')
        if not candidate or NOT_A_NAME.search(candidate):
            continue

        parts = [
            part.strip(' .,')
            for part in re.split(r',| and | & |;', candidate, flags=re.IGNORECASE)
            if part.strip(' .,')
        ]
        names = []
        for part in parts:
            words = part.split()
            if not 2 <= len(words) <= 4:
                names = []
                break
            if not all(word[0].isupper() for word in words if word):
                names = []
                break
            names.append((' '.join(words[:-1]), words[-1]))
        if names:
            return names[:12]
    return []


def names_to_pairs(value):
    """Turn 'Ada Obi, Chidi Eze' into [('Ada', 'Obi'), ('Chidi', 'Eze')].

    The bulk screen takes the byline as one line of text, because a nested form
    per author across twenty articles is unusable. Affiliations and ORCIDs are
    added on an article's own page, where there is room for them.
    """
    pairs = []
    for part in re.split(r',|;| and | & ', value or '', flags=re.IGNORECASE):
        part = part.strip()
        if not part:
            continue
        words = part.split()
        if len(words) == 1:
            pairs.append(('', words[0]))
        else:
            pairs.append((' '.join(words[:-1]), words[-1]))
    return pairs


# --- document structure ----------------------------------------------------

# Word's own heading styles, when the author used them.
HEADING_STYLE = re.compile(r'^(heading|berschrift)([1-6])$', re.IGNORECASE)
TITLE_STYLES = {'title', 'subtitle'}
QUOTE_STYLES = {'quote', 'intensequote', 'blockquote'}

# Most manuscripts do not use heading styles: authors bold a short line and
# move on. A numbered opener is the other giveaway.
NUMBERED_HEADING = re.compile(r'^\s*(\d+(\.\d+)*)[.)]?\s+\S')
REFERENCES_HEADING = re.compile(
    r'^\s*(references|bibliography|works cited)\s*$', re.IGNORECASE,
)

MAX_BODY_BLOCKS = 4000

W = DOCX_NS['w']
RELS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
DRAWING_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
DRAWING_REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'


class Block:
    """One piece of a typeset article: a heading, a paragraph, a list, a table.

    Deliberately not HTML yet. This module's job is to say what the author
    marked up; turning that into a page belongs to the template.
    """

    def __init__(self, kind, **data):
        self.kind = kind
        self.__dict__.update(data)

    def __repr__(self):
        return f'<Block {self.kind}>'


def read_docx_blocks(uploaded):
    """Read a .docx into ordered blocks, with any images it carries.

    Returns ``(blocks, images)``, where images maps a generated filename to its
    bytes for the caller to store.
    """
    _rewind(uploaded)
    with zipfile.ZipFile(uploaded) as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
        relationships = _docx_relationships(archive)
        media = {}
        blocks = []

        body = document.find(f'{{{W}}}body')
        if body is None:
            return [], {}

        for node in body:
            tag = node.tag.split('}')[-1]
            if tag == 'p':
                block = _docx_paragraph(node, archive, relationships, media)
                if block:
                    blocks.append(block)
            elif tag == 'tbl':
                block = _docx_table(node)
                if block:
                    blocks.append(block)
            if len(blocks) >= MAX_BODY_BLOCKS:
                break

    _rewind(uploaded)
    return _group_lists(blocks), media


def _docx_relationships(archive):
    """Relationship id to the file it points at, for images."""
    path = 'word/_rels/document.xml.rels'
    if path not in archive.namelist():
        return {}
    try:
        root = ET.fromstring(archive.read(path))
    except ET.ParseError:
        return {}
    return {
        node.get('Id'): node.get('Target', '')
        for node in root.iter(f'{{{RELS_NS}}}Relationship')
    }


def _style_of(paragraph):
    properties = paragraph.find(f'{{{W}}}pPr')
    if properties is None:
        return '', False
    style = properties.find(f'{{{W}}}pStyle')
    name = (style.get(f'{{{W}}}val') if style is not None else '') or ''
    is_list = properties.find(f'{{{W}}}numPr') is not None
    return name, is_list


def _runs_of(paragraph):
    """The paragraph's runs as (text, bold, italic), merged where alike."""
    runs = []
    for run in paragraph.iter(f'{{{W}}}r'):
        properties = run.find(f'{{{W}}}rPr')
        bold = properties is not None and properties.find(f'{{{W}}}b') is not None
        italic = properties is not None and properties.find(f'{{{W}}}i') is not None
        text = ''.join(node.text or '' for node in run.iter(f'{{{W}}}t'))
        if not text:
            continue
        if runs and runs[-1][1] == bold and runs[-1][2] == italic:
            runs[-1] = (runs[-1][0] + text, bold, italic)
        else:
            runs.append((text, bold, italic))
    return runs


def _docx_images(paragraph, archive, relationships, media):
    """Pull any images in this paragraph out of the zip, keyed by new filename."""
    found = []
    for blip in paragraph.iter(f'{{{DRAWING_NS}}}blip'):
        target = relationships.get(blip.get(DRAWING_REL), '')
        if not target:
            continue
        path = target if target.startswith('word/') else 'word/' + target.lstrip('/')
        if path not in archive.namelist():
            continue
        extension = extension_of(path) or '.png'
        name = f'figure-{len(media) + 1}{extension}'
        media[name] = archive.read(path)
        found.append(name)
    return found


def _heading_level(text, runs):
    """The level of a manual heading, or None if this is not one.

    Most manuscripts never use Word's heading styles: authors bold a short line,
    or number it, and move on. Wrong either way costs something — a missed
    heading reads as a stray short paragraph, a false one puts 'The results were
    striking.' in bold display type — so this asks for several signals at once
    rather than any one of them.

    Depth comes from the numbering when there is any, so that '2.1 Procedure'
    sits under '2. Method' as the author intended. An unnumbered bold line is a
    top-level section heading, which is what 'Introduction' and 'Method' are in
    nearly every paper that writes them this way.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > 120 or len(stripped.split()) > 14:
        return None

    numbered = NUMBERED_HEADING.match(stripped)
    if stripped.endswith(('.', ',', ';', ':')) and not numbered:
        return None

    if numbered:
        return min(numbered.group(1).count('.') + 1, 3)
    if runs and all(bold for _, bold, _ in runs):
        return 1
    return None


def _docx_paragraph(paragraph, archive, relationships, media):
    style, is_list = _style_of(paragraph)
    runs = _runs_of(paragraph)
    text = ''.join(part for part, _, _ in runs).strip()
    images = _docx_images(paragraph, archive, relationships, media)

    if images and not text:
        return Block('figure', images=images)
    if not text:
        return None

    normalised = style.replace(' ', '').lower()
    heading = HEADING_STYLE.match(normalised)
    if heading:
        return Block('heading', level=min(int(heading.group(2)), 3), text=text, runs=runs)
    if normalised in TITLE_STYLES:
        return Block('heading', level=1, text=text, runs=runs)
    if normalised in QUOTE_STYLES:
        return Block('quote', runs=runs)
    if is_list:
        return Block('list_item', runs=runs)
    if REFERENCES_HEADING.match(text):
        return Block('heading', level=1, text=text, runs=runs)
    level = _heading_level(text, runs)
    if level:
        return Block('heading', level=level, text=text, runs=runs)
    return Block('paragraph', runs=runs, images=images)


def _docx_table(table):
    rows = []
    for row in table.iter(f'{{{W}}}tr'):
        cells = []
        for cell in row.iter(f'{{{W}}}tc'):
            cells.append(' '.join(
                ''.join(node.text or '' for node in paragraph.iter(f'{{{W}}}t')).strip()
                for paragraph in cell.iter(f'{{{W}}}p')
            ).strip())
        if any(cells):
            rows.append(cells)
    return Block('table', rows=rows) if rows else None


def _group_lists(blocks):
    """Run consecutive list items together, so they render as one list."""
    grouped = []
    for block in blocks:
        if block.kind == 'list_item':
            if grouped and grouped[-1].kind == 'list':
                grouped[-1].items.append(block.runs)
                continue
            grouped.append(Block('list', items=[block.runs]))
        else:
            grouped.append(block)
    return grouped
