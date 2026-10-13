"""A member's career portfolio: professional development recorded in one place.

Two kinds of record make up a portfolio, and the difference is the point:

* **ELTAN-issued** — event and conference certificates, membership years,
  JELTAN articles. These are read live from the records that issued them
  (see sources.py), never copied here, and are shown as verified.
* **Self-reported** — everything a member did elsewhere: a British Council
  course, a postgraduate diploma, a talk at their school. Recorded here with
  the evidence attached, and always labelled as self-reported, because ELTAN
  has not checked it and a reader of the portfolio should know that.

Premium: the portfolio is free for every member while the client decides what
to charge. PortfolioSettings.premium_enabled is the switch; until it is on,
everyone has every feature. When it is turned on, the record keeping stays free
and the insight — summaries, the report, the public link — needs premium.
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .storage import evidence_storage

EVIDENCE_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'webp', 'docx']
MAX_EVIDENCE_BYTES = 5 * 1024 * 1024


class PortfolioSettings(models.Model):
    """Portfolio-wide switches, a single row."""

    premium_enabled = models.BooleanField(
        'Charge for premium features', default=False,
        help_text=(
            'Off: every member has every portfolio feature. On: period summaries, the PDF '
            'report, public sharing and unlimited uploads need premium access.'
        ),
    )
    free_upload_limit = models.PositiveIntegerField(
        default=5, help_text='Self-reported achievements a member without premium may record.',
    )
    premium_description = models.TextField(
        blank=True,
        help_text='Shown to members without premium: what it costs and how to get it.',
    )

    class Meta:
        verbose_name = 'Portfolio settings'
        verbose_name_plural = 'Portfolio settings'

    def __str__(self):
        return 'Portfolio settings'

    @classmethod
    def load(cls):
        row = cls.objects.first()
        return row or cls.objects.create()


class PremiumGrant(models.Model):
    """Premium access for one member for a period — granted by staff, or later, paid for."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='portfolio_grants')
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField()
    note = models.CharField(max_length=200, blank=True, help_text='Why, e.g. "Exco 2026" or a payment reference.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ends_on']

    def __str__(self):
        return f'{self.user} until {self.ends_on}'


def has_premium(user):
    """Whether this member has premium features right now."""
    if not PortfolioSettings.load().premium_enabled:
        return True
    if not user or not user.is_authenticated:
        return False
    today = timezone.localdate()
    return user.portfolio_grants.filter(starts_on__lte=today, ends_on__gte=today).exists()


class PortfolioProfile(models.Model):
    """What a member says about themselves, their CPD goal, and whether the portfolio is shared."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='portfolio')
    headline = models.CharField(
        max_length=160, blank=True, help_text='e.g. "English teacher, Government Secondary School, Kaduna".',
    )
    bio = models.TextField(blank=True, help_text='A few lines about your teaching and interests.')
    cpd_goal_hours = models.DecimalField(
        'Yearly CPD goal (hours)', max_digits=5, decimal_places=1, null=True, blank=True,
        help_text='Hours of professional development you aim for each ELTAN year.',
    )
    share_enabled = models.BooleanField(default=False)
    share_token = models.CharField(max_length=40, unique=True, null=True, blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Portfolio of {self.user}'

    def new_share_token(self):
        self.share_token = secrets.token_urlsafe(18)

    def get_share_url(self):
        return reverse('portfolio:shared', args=[self.share_token]) if self.share_token else ''


class Achievement(models.Model):
    """A self-reported piece of professional development."""

    WORKSHOP = 'workshop'
    COURSE = 'course'
    QUALIFICATION = 'qualification'
    CONFERENCE = 'conference'
    PRESENTATION = 'presentation'
    PUBLICATION = 'publication'
    AWARD = 'award'
    MEMBERSHIP = 'membership'
    OTHER = 'other'
    CATEGORY_CHOICES = [
        (WORKSHOP, 'Workshop or webinar'),
        (COURSE, 'Course or training'),
        (QUALIFICATION, 'Qualification or certification'),
        (CONFERENCE, 'Conference attended'),
        (PRESENTATION, 'Presentation or talk given'),
        (PUBLICATION, 'Publication'),
        (AWARD, 'Award or recognition'),
        (MEMBERSHIP, 'Membership'),
        (OTHER, 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='achievements')
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=WORKSHOP)
    provider = models.CharField(
        'Provider or issuer', max_length=255, blank=True, help_text='Who ran it or awarded it.',
    )
    completed_on = models.DateField('Date', help_text='When it was completed or awarded.')
    cpd_hours = models.DecimalField(
        'CPD hours', max_digits=5, decimal_places=1, null=True, blank=True,
        help_text='Hours of professional development, if it counts towards CPD.',
    )
    description = models.TextField(blank=True, help_text='What you did or learned.')
    credential_url = models.URLField('Credential link', blank=True, help_text="A link to verify it, if the issuer provides one.")
    evidence = models.FileField(
        upload_to='evidence/%Y/', storage=evidence_storage, blank=True,
        validators=[FileExtensionValidator(EVIDENCE_EXTENSIONS)],
        help_text='The certificate or other evidence: PDF, image or Word file, up to 5 MB.',
    )
    is_public = models.BooleanField(
        'Show on my shared portfolio', default=True,
        help_text='Evidence files are never shown publicly, only the entry itself.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-completed_on', '-created_at']

    def __str__(self):
        return self.title

    @property
    def hours(self):
        return self.cpd_hours or Decimal('0')
