"""Registration, post-event activity and certificates for ELTAN events.

An event is still the `membership.Events` row the site has always listed. What
this app adds hangs off it rather than widening that table, because the
homepage and the events page both query it: an unapplied migration here can
only break the new pages, never the front door.

The path an attendee takes:

1. **Register** on the site — a member from their account, a guest with a name
   and an email. Free events confirm at once; paid ones go through Paystack and
   confirm when the payment does.
2. **Attend.** Confirmed registrants are sent the joining link. During the
   session the facilitator announces an attendance code.
3. **Complete the post-event activity**: the code, plus a short feedback and
   reflection form. That submission is the evidence a certificate rests on —
   it shows the person was there and engaged, which a registration alone does
   not.
4. **Receive the certificate**, with an id anyone can verify, a badge on their
   dashboard and a link that adds it to their LinkedIn profile.
"""

import datetime
import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.signing import BadSignature, Signer
from django.db import models
from django.urls import reverse
from django.utils import timezone

from membership.models import Events

TOKEN_SALT = 'events.registration'
MAX_CODE_ATTEMPTS = 8

# Created with every new event, so an admin starts from a sensible activity and
# edits it rather than facing an empty form. Each is (prompt, kind, required).
DEFAULT_QUESTIONS = [
    ('How useful was this session for your teaching?', 'rating', True),
    ('What is the most important idea you are taking away from the session?', 'long_text', True),
    ('How will you apply it in your classroom in the next month?', 'long_text', True),
]


def _readable_code(prefix):
    """PREFIX-YYYY-XXXXXX — short enough to read out, long enough not to guess."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    tail = ''.join(secrets.choice(alphabet) for _ in range(6))
    return f'{prefix}-{timezone.now().year}-{tail}'


class EventSetup(models.Model):
    """What an event needs beyond its listing: registration, activity, certificate."""

    event = models.OneToOneField(Events, on_delete=models.CASCADE, related_name='setup')

    # --- registration ------------------------------------------------------
    accepts_registrations = models.BooleanField(
        'Take registrations on this site', default=False,
        help_text='Tick to register attendees here instead of through the external registration link.',
    )
    starts_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the session starts. Leave blank to use the event date.",
    )
    registration_closes_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Leave blank to keep registration open until the event ends.',
    )
    member_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        help_text='Fee in naira for ELTAN members with a current subscription. 0 makes it free.',
    )
    guest_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        help_text='Fee in naira for everyone else. 0 makes it free.',
    )
    join_link = models.URLField(
        blank=True,
        help_text='Zoom, Google Meet or similar. Shown only to confirmed registrants.',
    )
    joining_instructions = models.TextField(
        blank=True, help_text='Anything else registrants need: venue directions, meeting passcode, what to bring.',
    )

    # --- the post-event activity ------------------------------------------
    activity_is_open = models.BooleanField(
        'Post-event activity is open', default=False,
        help_text='Tick once the session is under way to let registrants submit the activity and receive certificates.',
    )
    activity_closes_at = models.DateTimeField(
        null=True, blank=True, help_text='Leave blank to keep the activity open until it is unticked.',
    )
    attendance_code = models.CharField(
        max_length=40, blank=True,
        help_text=(
            'A word or short code announced live during the session. Attendees must enter it '
            'to complete the activity. Not case-sensitive. Leave blank to not ask for one.'
        ),
    )
    activity_intro = models.TextField(
        blank=True, help_text='Shown above the activity questions.',
    )

    # --- the certificate --------------------------------------------------
    issues_certificates = models.BooleanField(
        default=True, help_text='Issue a certificate to everyone who completes the activity.',
    )
    certificate_title = models.CharField(max_length=120, default='Certificate of Participation')
    cpd_hours = models.DecimalField(
        'CPD hours', max_digits=5, decimal_places=1, null=True, blank=True,
        help_text='Continuing professional development hours, printed on the certificate.',
    )
    certificate_template = models.FileField(
        upload_to='event_certificate_templates/', null=True, blank=True,
        help_text=(
            "Optional: a single-page PDF of the certificate artwork with the name left blank. "
            "Leave empty to use the standard ELTAN certificate design."
        ),
    )
    certificate_name_x = models.FloatField(
        default=0.5, help_text="With uploaded artwork: horizontal centre of the name, as a fraction of page width.",
    )
    certificate_name_baseline = models.FloatField(
        default=0.47, help_text='With uploaded artwork: baseline of the name, as a fraction of page height from the top.',
    )
    certificate_name_max_width = models.FloatField(
        default=0.55, help_text='With uploaded artwork: widest the name may run, as a fraction of page width.',
    )
    certificate_name_font_size = models.FloatField(
        default=30, help_text='With uploaded artwork: point size of the name on an A4 landscape page.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Registration and certificate settings'
        verbose_name_plural = 'Registration and certificate settings'

    def __str__(self):
        return f'Setup for {self.event.event_title}'

    @property
    def title(self):
        return self.event.event_title

    # --- when things are open ---------------------------------------------

    @property
    def start(self):
        if self.starts_at:
            return self.starts_at
        return timezone.make_aware(
            datetime.datetime.combine(self.event.event_date, datetime.time.min)
        )

    @property
    def end(self):
        last_day = self.event.event_end_date or self.event.event_date
        return timezone.make_aware(
            datetime.datetime.combine(last_day, datetime.time.max)
        )

    @property
    def is_free(self):
        return not self.member_fee and not self.guest_fee

    def fee_for(self, is_member):
        return self.member_fee if is_member else self.guest_fee

    @property
    def confirmed_count(self):
        return self.event.registrations.filter(status=EventRegistration.CONFIRMED).count()

    @property
    def is_full(self):
        capacity = self.event.capacity
        return bool(capacity) and self.confirmed_count >= capacity

    def registration_closed_reason(self, now=None):
        """Why registration is closed right now, or '' when it is open."""
        now = now or timezone.now()
        if not self.accepts_registrations:
            return 'Registration for this event is not taken on this site.'
        if self.registration_closes_at and now > self.registration_closes_at:
            return 'Registration for this event has closed.'
        if now > self.end:
            return 'This event has ended.'
        if self.is_full:
            return 'This event is fully booked.'
        return ''

    @property
    def registration_is_open(self):
        return not self.registration_closed_reason()

    @property
    def activity_available(self):
        if not self.activity_is_open:
            return False
        return not self.activity_closes_at or timezone.now() <= self.activity_closes_at

    def code_matches(self, entered):
        if not self.attendance_code:
            return True
        return (entered or '').strip().casefold() == self.attendance_code.strip().casefold()

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.event.questions.exists():
            EventQuestion.objects.bulk_create([
                EventQuestion(event=self.event, prompt=prompt, kind=kind, required=required, order=index)
                for index, (prompt, kind, required) in enumerate(DEFAULT_QUESTIONS)
            ])


class EventQuestion(models.Model):
    """One question on an event's post-event activity."""

    SHORT_TEXT = 'text'
    LONG_TEXT = 'long_text'
    RATING = 'rating'
    CHOICE = 'choice'
    KIND_CHOICES = [
        (SHORT_TEXT, 'Short answer'),
        (LONG_TEXT, 'Paragraph'),
        (RATING, 'Rating, 1 to 5'),
        (CHOICE, 'Multiple choice'),
    ]

    event = models.ForeignKey(Events, on_delete=models.CASCADE, related_name='questions')
    prompt = models.CharField(max_length=300)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=LONG_TEXT)
    choices = models.TextField(blank=True, help_text='Multiple choice only: one option per line.')
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']

    def __str__(self):
        return self.prompt

    @property
    def choice_list(self):
        return [line.strip() for line in self.choices.splitlines() if line.strip()]


class EventRegistration(models.Model):
    """One person's place at an event, member or guest."""

    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (PENDING, 'Awaiting payment'),
        (CONFIRMED, 'Confirmed'),
        (CANCELLED, 'Cancelled'),
    ]

    event = models.ForeignKey(Events, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='event_registrations',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    is_member = models.BooleanField(default=False, help_text='Registered at the member rate.')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    payment_reference = models.CharField(max_length=60, unique=True, editable=False)
    paystack_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    ticket_id = models.CharField(max_length=30, unique=True, null=True, blank=True, editable=False)

    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    confirmation_error = models.CharField(max_length=500, blank=True)
    # Wrong attendance codes entered. Capped so the code cannot be guessed by
    # someone who registered but did not attend; staff can reset it.
    failed_code_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['event', 'email'], name='one_registration_per_email'),
        ]

    def __str__(self):
        return f'{self.full_name} — {self.event.event_title}'

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        if not self.payment_reference:
            self.payment_reference = f'EVT-{uuid.uuid4().hex}'
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_confirmed(self):
        return self.status == self.CONFIRMED

    def confirm(self, paystack_reference=''):
        """Confirm the place and issue a ticket. Returns True only for the call that did it.

        A Paystack payment is reported twice — the browser's return and the
        webhook — often within the same second. The update is conditional on
        the row still being pending, so exactly one of them confirms it and only
        that one goes on to send the confirmation email.
        """
        now = timezone.now()
        fields = {'status': self.CONFIRMED, 'confirmed_at': now}
        if paystack_reference:
            fields.update(paystack_reference=paystack_reference, paid_at=now)
        updated = EventRegistration.objects.filter(pk=self.pk, status=self.PENDING).update(**fields)
        self.refresh_from_db()
        if updated and not self.ticket_id:
            while True:
                candidate = _readable_code('EVT')
                if not EventRegistration.objects.filter(ticket_id=candidate).exists():
                    break
            EventRegistration.objects.filter(pk=self.pk).update(ticket_id=candidate)
            self.ticket_id = candidate
        return bool(updated)

    # --- the attendee's own link -------------------------------------------

    @property
    def token(self):
        """A link credential: the registration page opens for whoever holds it.

        Guests have no account, so their emailed link has to be the way back in.
        It is signed, not stored, and does not expire — it is their ticket.
        """
        return Signer(salt=TOKEN_SALT).sign(str(self.pk))

    @classmethod
    def from_token(cls, token):
        try:
            pk = Signer(salt=TOKEN_SALT).unsign(token)
        except BadSignature:
            return None
        return cls.objects.select_related('event', 'event__setup').filter(pk=pk).first()

    def get_absolute_url(self):
        return reverse('events:registration', args=[self.token])

    @property
    def has_completed_activity(self):
        return hasattr(self, 'response')


class EventResponse(models.Model):
    """A completed post-event activity — the record behind a certificate."""

    registration = models.OneToOneField(EventRegistration, on_delete=models.CASCADE, related_name='response')
    submitted_at = models.DateTimeField(auto_now_add=True)
    code_entered = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Activity by {self.registration.full_name}'


class EventAnswer(models.Model):
    response = models.ForeignKey(EventResponse, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(EventQuestion, on_delete=models.SET_NULL, null=True, blank=True)
    # The question as it was asked, so an answer still reads correctly after
    # the question is reworded or deleted.
    prompt = models.CharField(max_length=300)
    answer = models.TextField(blank=True)

    class Meta:
        ordering = ['pk']


class EventCertificate(models.Model):
    """A certificate earned by completing an event's activity."""

    registration = models.OneToOneField(EventRegistration, on_delete=models.CASCADE, related_name='certificate')
    certificate_id = models.CharField(max_length=40, unique=True, editable=False)
    # Snapshotted, so what verification reports always matches what was printed.
    participant_name = models.CharField(max_length=255)
    event_title = models.CharField(max_length=255)
    certificate_title = models.CharField(max_length=120)
    cpd_hours = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    download_count = models.PositiveIntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    is_revoked = models.BooleanField(
        default=False, help_text='Tick to withdraw the certificate. Verification will report it as revoked.',
    )

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f'{self.certificate_id} — {self.participant_name}'

    def save(self, *args, **kwargs):
        if not self.certificate_id:
            while True:
                candidate = _readable_code('ELTAN-EVT')
                if not EventCertificate.objects.filter(certificate_id=candidate).exists():
                    break
            self.certificate_id = candidate
        super().save(*args, **kwargs)

    @property
    def event(self):
        return self.registration.event

    def record_download(self):
        EventCertificate.objects.filter(pk=self.pk).update(
            download_count=models.F('download_count') + 1, last_downloaded_at=timezone.now(),
        )

    def get_verify_url(self):
        return reverse('events:verify_certificate', args=[self.certificate_id])
