"""Gathering a member's record, and summarising a period of it.

ELTAN-issued entries are read from where they live — event certificates,
conference registrations, subscriptions, JELTAN articles — every time, rather
than copied into the portfolio. A copy would drift: a revoked certificate would
stay in the portfolio, a corrected title would not follow. Reading live keeps
the portfolio exactly as true as the records behind it.

Each source is read on its own and a failure in one is logged and skipped, so a
problem in, say, the conference tables never takes the whole portfolio down.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .models import Achievement

logger = logging.getLogger(__name__)

ELTAN = 'ELTAN'
CATEGORY_LABELS = dict(Achievement.CATEGORY_CHOICES)


@dataclass
class Entry:
    title: str
    category: str
    when: date
    provider: str = ''
    cpd_hours: Decimal = None
    verified: bool = False
    description: str = ''
    link: str = ''               # a verification page or the published record
    achievement: Achievement = None   # set for self-reported entries
    is_public: bool = True
    source: str = ''

    @property
    def category_label(self):
        return CATEGORY_LABELS.get(self.category, self.category.title())

    @property
    def hours(self):
        return self.cpd_hours or Decimal('0')


def _events(user):
    from events.models import EventCertificate

    certificates = (
        EventCertificate.objects
        .filter(Q(registration__user=user) | Q(registration__email=(user.email or '').lower()),
                is_revoked=False)
        .select_related('registration__event')
    )
    return [
        Entry(
            title=certificate.event_title, category=Achievement.WORKSHOP,
            when=certificate.registration.event.event_date, provider=ELTAN,
            cpd_hours=certificate.cpd_hours, verified=True,
            description=certificate.certificate_title, link=certificate.get_verify_url(),
            source='event',
        )
        for certificate in certificates
    ]


def _conferences(user):
    from django.urls import reverse
    from membership.models import EltanConferenceRegistration

    today = timezone.localdate()
    registrations = (
        EltanConferenceRegistration.objects
        .filter(user=user, payment_status='completed', conference__start_date__lte=today)
        .select_related('conference')
    )
    entries = []
    for registration in registrations:
        certificate = getattr(registration, 'certificate', None)
        if certificate and certificate.is_revoked:
            continue
        conference = registration.conference
        entries.append(Entry(
            title=conference.title, category=Achievement.CONFERENCE,
            when=conference.start_date, provider=ELTAN, verified=True,
            description=getattr(conference, 'theme', '') or '',
            link=(reverse('verify_conference_certificate', args=[certificate.certificate_id])
                  if certificate and certificate.certificate_id else ''),
            source='conference',
        ))
    return entries


def _memberships(user):
    from membership.models import Subscription

    return [
        Entry(
            title=f'ELTAN membership {subscription.eltan_year}', category=Achievement.MEMBERSHIP,
            when=subscription.start_date, provider=ELTAN, verified=True, source='membership',
        )
        for subscription in Subscription.objects.filter(user=user, payment_status='paid')
        if subscription.start_date
    ]


def _articles(user):
    from journal.models import Article, JournalSettings

    if not user.email:
        return []
    journal = JournalSettings.load()
    articles = (
        Article.objects.filter(is_published=True, authors__email__iexact=user.email)
        .select_related('issue').distinct()
    )
    return [
        Entry(
            title=article.title, category=Achievement.PUBLICATION,
            when=(article.published_at or article.created_at).date(),
            provider=journal.name, verified=True,
            description=article.issue.label if article.issue else 'Online first',
            link=article.get_absolute_url(), source='article',
        )
        for article in articles
    ]


def _self_reported(user):
    return [
        Entry(
            title=item.title, category=item.category, when=item.completed_on,
            provider=item.provider, cpd_hours=item.cpd_hours, verified=False,
            description=item.description, link=item.credential_url, achievement=item,
            is_public=item.is_public, source='self',
        )
        for item in user.achievements.all()
    ]


SOURCES = [_events, _conferences, _memberships, _articles, _self_reported]


def entries_for(user, start=None, end=None, public_only=False):
    """Everything in a member's record, newest first, optionally within a date range."""
    entries = []
    for source in SOURCES:
        try:
            entries.extend(source(user))
        except Exception:                                # noqa: BLE001 - see module docstring
            logger.exception('Portfolio source %s failed for user %s', source.__name__, user.pk)
    if start:
        entries = [entry for entry in entries if entry.when >= start]
    if end:
        entries = [entry for entry in entries if entry.when <= end]
    if public_only:
        entries = [entry for entry in entries if entry.is_public]
    return sorted(entries, key=lambda entry: entry.when, reverse=True)


@dataclass
class Summary:
    start: date
    end: date
    entries: list
    total_hours: Decimal = Decimal('0')
    verified_hours: Decimal = Decimal('0')
    self_reported_hours: Decimal = Decimal('0')
    by_category: list = field(default_factory=list)
    goal_hours: Decimal = None

    @property
    def goal_percent(self):
        if not self.goal_hours:
            return None
        return min(100, int(self.total_hours / self.goal_hours * 100))


def summarise(entries, start, end, goal_hours=None):
    summary = Summary(start=start, end=end, entries=entries, goal_hours=goal_hours)
    for entry in entries:
        summary.total_hours += entry.hours
        if entry.verified:
            summary.verified_hours += entry.hours
        else:
            summary.self_reported_hours += entry.hours
    counts = Counter(entry.category for entry in entries)
    summary.by_category = [
        (CATEGORY_LABELS.get(category, category), count) for category, count in counts.most_common()
    ]
    return summary


# --- periods -------------------------------------------------------------------

def eltan_year_bounds(offset=0):
    """(label, start, end) for the current ELTAN year, or one `offset` years from it."""
    from membership.models import ELTANYearSetting

    label = ELTANYearSetting.current_label()
    first = int(label.split('-')[0]) + offset
    label = f'{first}-{first + 1}'
    start, end = ELTANYearSetting.dates_for(label)
    return label, start, end


def resolve_period(params):
    """Turn the period picker's query string into (key, label, start, end).

    The ELTAN year (September to August) is the default, because that is the
    year membership, the association's calendar and most schools' sessions run
    on — and so the one a promotion panel will ask about.
    """
    key = params.get('period', 'this_year')
    if key == 'last_year':
        label, start, end = eltan_year_bounds(-1)
        return key, f'ELTAN year {label}', start, end
    if key == 'all':
        return key, 'All time', None, None
    if key == 'custom':
        try:
            start = date.fromisoformat(params.get('from', ''))
            end = date.fromisoformat(params.get('to', ''))
        except ValueError:
            start = end = None
        if start and end and start <= end:
            return key, f'{start:%d %b %Y} – {end:%d %b %Y}', start, end
    label, start, end = eltan_year_bounds(0)
    return 'this_year', f'ELTAN year {label}', start, end
