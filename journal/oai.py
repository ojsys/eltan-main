"""An OAI-PMH 2.0 endpoint for JELTAN.

This is the protocol DOAJ, BASE, CORE and most aggregators use to harvest a
journal's metadata. Without it JELTAN can be published and still be invisible to
everyone who is not already looking at it — which, for a journal with no DOIs
yet, is the whole discovery story.

Implemented against the OAI-PMH 2.0 specification: the six verbs, oai_dc
metadata, sets by journal section, selective harvesting by date, and
resumption tokens. Only published articles are ever exposed.

Deliberate simplification: ``deletedRecord`` is declared ``no``. An article that
is unpublished simply stops appearing rather than being tombstoned, which the
specification permits and which matches how a journal actually behaves — papers
are corrected or retracted in public, not silently withdrawn from the record.
"""

import base64
import binascii
from datetime import datetime, timezone as dt_timezone
from xml.etree import ElementTree as ET

from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from .models import Article, JournalSettings, Section

OAI_NS = 'http://www.openarchives.org/OAI/2.0/'
OAI_SCHEMA = 'http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
OAI_DC_NS = 'http://www.openarchives.org/OAI/2.0/oai_dc/'
OAI_DC_SCHEMA = 'http://www.openarchives.org/OAI/2.0/oai_dc.xsd'
DC_NS = 'http://purl.org/dc/elements/1.1/'

METADATA_PREFIX = 'oai_dc'
# Harvesters expect to be paged rather than handed the whole archive at once.
PAGE_SIZE = 100

VERBS = {
    'Identify', 'ListMetadataFormats', 'ListSets',
    'ListIdentifiers', 'ListRecords', 'GetRecord',
}

# Which arguments each verb accepts, so that a malformed request is answered with
# badArgument rather than being quietly misinterpreted.
ALLOWED_ARGS = {
    'Identify': set(),
    'ListMetadataFormats': {'identifier'},
    'ListSets': {'resumptionToken'},
    'ListIdentifiers': {'from', 'until', 'metadataPrefix', 'set', 'resumptionToken'},
    'ListRecords': {'from', 'until', 'metadataPrefix', 'set', 'resumptionToken'},
    'GetRecord': {'identifier', 'metadataPrefix'},
}


class OAIError(Exception):
    """An OAI-PMH error condition, returned as an <error> element."""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _utc(value):
    """Format a datetime as OAI-PMH requires: UTC, second granularity."""
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse_date(value, name):
    """Parse a `from`/`until` argument in either granularity the spec allows."""
    for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d'):
        try:
            parsed = datetime.strptime(value, fmt)
            return timezone.make_aware(parsed, dt_timezone.utc)
        except ValueError:
            continue
    raise OAIError('badArgument', f"'{name}' is not a valid UTCdatetime: {value}")


def _base_url(request):
    return request.build_absolute_uri(reverse('journal:oai'))


def _identifier_for(request, article):
    return f'oai:{request.get_host().split(":")[0]}:jeltan/{article.slug}'


def _slug_from_identifier(identifier):
    if not identifier or '/' not in identifier:
        raise OAIError('idDoesNotExist', f'Unknown identifier: {identifier}')
    return identifier.rsplit('/', 1)[1]


def _encode_token(offset, params):
    """Pack the harvest position into an opaque resumption token."""
    raw = '|'.join([
        str(offset),
        params.get('metadataPrefix', METADATA_PREFIX),
        params.get('from', ''),
        params.get('until', ''),
        params.get('set', ''),
    ])
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_token(token):
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        offset, prefix, date_from, date_until, set_spec = raw.split('|')
        params = {'metadataPrefix': prefix}
        if date_from:
            params['from'] = date_from
        if date_until:
            params['until'] = date_until
        if set_spec:
            params['set'] = set_spec
        return int(offset), params
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise OAIError('badResumptionToken', 'That resumption token is not valid or has expired.')


def _records(params):
    """The published articles matching a harvest request, oldest first.

    Ordered by publication date so that a harvest paged over several requests
    stays stable: a new article appears at the end rather than shifting
    everything the harvester has already seen.
    """
    queryset = (
        Article.objects.filter(is_published=True, published_at__isnull=False)
        .select_related('issue', 'section')
        .prefetch_related('authors')
        .order_by('published_at', 'pk')
    )

    if params.get('from'):
        queryset = queryset.filter(published_at__gte=_parse_date(params['from'], 'from'))
    if params.get('until'):
        queryset = queryset.filter(published_at__lte=_parse_date(params['until'], 'until'))

    set_spec = params.get('set')
    if set_spec:
        if not Section.objects.filter(slug=set_spec).exists():
            raise OAIError('badArgument', f'Unknown set: {set_spec}')
        queryset = queryset.filter(section__slug=set_spec)

    return queryset


def _check_arguments(verb, request_args):
    """Reject arguments the verb does not take, per the specification."""
    supplied = {key for key in request_args if key != 'verb'}

    if 'resumptionToken' in supplied and supplied != {'resumptionToken'}:
        raise OAIError(
            'badArgument',
            'resumptionToken is exclusive — it cannot be combined with other arguments.',
        )

    unknown = supplied - ALLOWED_ARGS[verb]
    if unknown:
        raise OAIError('badArgument', f"{verb} does not take: {', '.join(sorted(unknown))}")

    if verb in {'ListIdentifiers', 'ListRecords'} and 'resumptionToken' not in supplied:
        if 'metadataPrefix' not in supplied:
            raise OAIError('badArgument', 'metadataPrefix is required.')
    if verb == 'GetRecord':
        for required in ('identifier', 'metadataPrefix'):
            if required not in supplied:
                raise OAIError('badArgument', f'{required} is required.')


def _check_prefix(prefix):
    if prefix and prefix != METADATA_PREFIX:
        raise OAIError(
            'cannotDisseminateFormat',
            f"'{prefix}' is not supported. This repository provides '{METADATA_PREFIX}'.",
        )


# --------------------------------------------------------------- XML building

def _envelope(request, verb=None, request_args=None):
    root = ET.Element('OAI-PMH', {
        'xmlns': OAI_NS,
        'xmlns:xsi': XSI_NS,
        'xsi:schemaLocation': f'{OAI_NS} {OAI_SCHEMA}',
    })
    ET.SubElement(root, 'responseDate').text = _utc(timezone.now())

    # On an error of verb or argument the spec requires the request element to
    # carry no attributes, so a broken request is echoed back plainly.
    attributes = {}
    if verb:
        attributes['verb'] = verb
        for key, value in (request_args or {}).items():
            if key != 'verb':
                attributes[key] = value
    ET.SubElement(root, 'request', attributes).text = _base_url(request)
    return root


def _text(parent, tag, value):
    if value:
        ET.SubElement(parent, tag).text = str(value)


def _identify(root, request):
    journal = JournalSettings.load()
    node = ET.SubElement(root, 'Identify')
    _text(node, 'repositoryName', journal.name)
    _text(node, 'baseURL', _base_url(request))
    _text(node, 'protocolVersion', '2.0')

    admin_email = journal.contact_email or 'editor@eltanigeria.org'
    _text(node, 'adminEmail', admin_email)

    earliest = (
        Article.objects.filter(is_published=True, published_at__isnull=False)
        .order_by('published_at').values_list('published_at', flat=True).first()
    )
    _text(node, 'earliestDatestamp', _utc(earliest) if earliest else '1970-01-01T00:00:00Z')
    _text(node, 'deletedRecord', 'no')
    _text(node, 'granularity', 'YYYY-MM-DDThh:mm:ssZ')


def _list_metadata_formats(root, request, params):
    # An identifier may be supplied; if it is, it has to exist.
    if params.get('identifier'):
        slug = _slug_from_identifier(params['identifier'])
        if not Article.objects.filter(slug=slug, is_published=True).exists():
            raise OAIError('idDoesNotExist', f"Unknown identifier: {params['identifier']}")

    node = ET.SubElement(root, 'ListMetadataFormats')
    fmt = ET.SubElement(node, 'metadataFormat')
    _text(fmt, 'metadataPrefix', METADATA_PREFIX)
    _text(fmt, 'schema', OAI_DC_SCHEMA)
    _text(fmt, 'metadataNamespace', OAI_DC_NS)


def _list_sets(root):
    sections = Section.objects.all()
    if not sections.exists():
        raise OAIError('noSetHierarchy', 'This repository does not define sets.')
    node = ET.SubElement(root, 'ListSets')
    for section in sections:
        set_node = ET.SubElement(node, 'set')
        _text(set_node, 'setSpec', section.slug)
        _text(set_node, 'setName', section.name)
        if section.description:
            pass  # setDescription requires a schema-qualified container; omitted.


def _header(parent, request, article):
    header = ET.SubElement(parent, 'header')
    _text(header, 'identifier', _identifier_for(request, article))
    _text(header, 'datestamp', _utc(article.published_at))
    if article.section:
        _text(header, 'setSpec', article.section.slug)
    return header


def _metadata(parent, request, article):
    journal = JournalSettings.load()
    metadata = ET.SubElement(parent, 'metadata')
    dc = ET.SubElement(metadata, 'oai_dc:dc', {
        'xmlns:oai_dc': OAI_DC_NS,
        'xmlns:dc': DC_NS,
        'xmlns:xsi': XSI_NS,
        'xsi:schemaLocation': f'{OAI_DC_NS} {OAI_DC_SCHEMA}',
    })

    _text(dc, 'dc:title', article.title)
    for author in article.authors.all():
        _text(dc, 'dc:creator', f'{author.last_name}, {author.first_name}')
    for keyword in (article.keywords or '').split(','):
        _text(dc, 'dc:subject', keyword.strip())
    _text(dc, 'dc:description', article.abstract)
    _text(dc, 'dc:publisher', journal.publisher)
    _text(dc, 'dc:date', article.published_at.strftime('%Y-%m-%d') if article.published_at else '')
    _text(dc, 'dc:type', 'text')
    _text(dc, 'dc:type', 'article')
    _text(dc, 'dc:format', 'application/pdf' if article.pdf else 'text/html')

    # The landing page first: it is the citable location, and the one that keeps
    # working if the file is ever re-typeset.
    _text(dc, 'dc:identifier', request.build_absolute_uri(article.get_absolute_url()))
    if article.doi:
        _text(dc, 'dc:identifier', f'https://doi.org/{article.doi}')

    source = journal.name
    if article.issue:
        source += f'; Vol. {article.issue.volume} No. {article.issue.number} ({article.issue.year})'
        if article.page_range:
            source += f'; {article.page_range}'
    _text(dc, 'dc:source', source)
    if journal.issn_online:
        _text(dc, 'dc:source', journal.issn_online)

    _text(dc, 'dc:language', 'en')
    _text(dc, 'dc:rights', article.licence)


def _list_records(root, request, params, with_metadata):
    offset = 0
    if params.get('resumptionToken'):
        offset, params = _decode_token(params['resumptionToken'])

    _check_prefix(params.get('metadataPrefix'))

    queryset = _records(params)
    total = queryset.count()
    if not total:
        raise OAIError('noRecordsMatch', 'No published articles match that request.')

    page = list(queryset[offset:offset + PAGE_SIZE])
    node = ET.SubElement(root, 'ListRecords' if with_metadata else 'ListIdentifiers')

    for article in page:
        if with_metadata:
            record = ET.SubElement(node, 'record')
            _header(record, request, article)
            _metadata(record, request, article)
        else:
            _header(node, request, article)

    next_offset = offset + len(page)
    if next_offset < total:
        token = ET.SubElement(node, 'resumptionToken', {
            'completeListSize': str(total),
            'cursor': str(offset),
        })
        token.text = _encode_token(next_offset, params)
    elif offset:
        # An empty token closes a harvest that was paged.
        ET.SubElement(node, 'resumptionToken', {
            'completeListSize': str(total), 'cursor': str(offset),
        })


def _get_record(root, request, params):
    _check_prefix(params.get('metadataPrefix'))
    slug = _slug_from_identifier(params.get('identifier'))
    article = (
        Article.objects.filter(slug=slug, is_published=True, published_at__isnull=False)
        .prefetch_related('authors').select_related('issue', 'section').first()
    )
    if not article:
        raise OAIError('idDoesNotExist', f"Unknown identifier: {params.get('identifier')}")

    node = ET.SubElement(root, 'GetRecord')
    record = ET.SubElement(node, 'record')
    _header(record, request, article)
    _metadata(record, request, article)


def oai(request):
    """The OAI-PMH endpoint. Both GET and POST, as the specification requires."""
    params = {key: value for key, value in (
        request.POST if request.method == 'POST' else request.GET
    ).items()}
    verb = params.get('verb')

    try:
        if verb not in VERBS:
            raise OAIError('badVerb', f"'{verb}' is not a legal OAI-PMH verb." if verb
                           else 'No verb was supplied.')

        _check_arguments(verb, params)
        root = _envelope(request, verb, params)

        if verb == 'Identify':
            _identify(root, request)
        elif verb == 'ListMetadataFormats':
            _list_metadata_formats(root, request, params)
        elif verb == 'ListSets':
            _list_sets(root)
        elif verb == 'ListIdentifiers':
            _list_records(root, request, params, with_metadata=False)
        elif verb == 'ListRecords':
            _list_records(root, request, params, with_metadata=True)
        elif verb == 'GetRecord':
            _get_record(root, request, params)

    except OAIError as error:
        # badVerb and badArgument must be echoed without request attributes.
        bare = error.code in {'badVerb', 'badArgument'}
        root = _envelope(request, None if bare else verb, None if bare else params)
        ET.SubElement(root, 'error', {'code': error.code}).text = error.message

    xml = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    return HttpResponse(xml, content_type='text/xml; charset=utf-8')
