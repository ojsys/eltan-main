"""Citation exports.

A reader who wants to cite an article should not have to retype it into their
reference manager. BibTeX and RIS are what Zotero, Mendeley and EndNote read, and
neither depends on the journal having DOIs.
"""

import re

from .models import JournalSettings


def _citation_key(article):
    """A BibTeX key: firstauthorYEARfirstword, e.g. obi2026reading."""
    author = article.authors.first()
    surname = re.sub(r'[^a-z]', '', (author.last_name if author else 'jeltan').lower()) or 'jeltan'
    year = article.published_at.year if article.published_at else ''
    first_word = re.sub(r'[^a-z]', '', article.title.split(' ')[0].lower()) if article.title else ''
    return f'{surname}{year}{first_word}'


def _escape_bibtex(value):
    """Protect the characters BibTeX treats as markup."""
    if not value:
        return ''
    for character in ('\\', '{', '}', '$', '&', '%', '#', '_'):
        value = value.replace(character, '\\' + character)
    return value.replace('\n', ' ').strip()


def to_bibtex(article):
    journal = JournalSettings.load()
    fields = [
        ('title', _escape_bibtex(article.title)),
        ('author', ' and '.join(
            f'{a.last_name}, {a.first_name}' for a in article.authors.all()
        )),
        ('journal', _escape_bibtex(journal.name)),
        ('year', article.published_at.year if article.published_at else ''),
    ]
    if article.issue:
        fields += [('volume', article.issue.volume), ('number', article.issue.number)]
    if article.page_range:
        fields.append(('pages', article.page_range.replace('–', '--')))
    if journal.issn_online:
        fields.append(('issn', journal.issn_online))
    if article.doi:
        fields.append(('doi', article.doi))
    fields += [
        ('abstract', _escape_bibtex(article.abstract)),
        ('keywords', _escape_bibtex(article.keywords)),
        ('publisher', _escape_bibtex(journal.publisher)),
    ]

    body = ',\n'.join(
        f'  {name} = {{{value}}}' for name, value in fields if value not in ('', None)
    )
    return f'@article{{{_citation_key(article)},\n{body}\n}}\n'


def to_ris(article):
    journal = JournalSettings.load()
    lines = ['TY  - JOUR']
    lines += [f'AU  - {a.last_name}, {a.first_name}' for a in article.authors.all()]
    lines.append(f'TI  - {article.title}')
    lines.append(f'JO  - {journal.name}')
    if article.published_at:
        lines.append(f'PY  - {article.published_at.year}')
        lines.append(f'DA  - {article.published_at.strftime("%Y/%m/%d")}')
    if article.issue:
        lines.append(f'VL  - {article.issue.volume}')
        lines.append(f'IS  - {article.issue.number}')
    if article.first_page:
        lines.append(f'SP  - {article.first_page}')
    if article.last_page:
        lines.append(f'EP  - {article.last_page}')
    if article.abstract:
        lines.append(f'AB  - {article.abstract}')
    for keyword in (article.keywords or '').split(','):
        if keyword.strip():
            lines.append(f'KW  - {keyword.strip()}')
    if journal.issn_online:
        lines.append(f'SN  - {journal.issn_online}')
    if article.doi:
        lines.append(f'DO  - {article.doi}')
    lines.append(f'PB  - {journal.publisher}')
    lines.append('ER  - ')
    return '\r\n'.join(lines) + '\r\n'
