"""JELTAN — the Journal of ELTAN.

The models here follow the standard scholarly publishing workflow, the one
reviewers, authors and indexing services already expect:

    submit -> desk check -> peer review -> decision -> revision rounds
           -> acceptance -> article processing charge -> production
           -> issue assembly -> publication -> archive

Two deliberate splits shape everything else:

* **Submission vs Article.** A Submission is the editorial record of a
  manuscript moving through review; an Article is the published record that
  appears in an issue. Keeping them apart means an editor can publish the back
  catalogue — issues from before this system existed — without inventing a fake
  review history, and can correct published metadata without touching what was
  actually decided during review.

* **Files are versioned rows, not fields.** Peer review is iterative: every
  revision round produces a new manuscript and a new response letter, and the
  earlier ones must stay readable. So files live in SubmissionFile rows stamped
  with their round rather than in FileFields that would be overwritten.

Double-blind review is enforced by the data model: authors upload an anonymised
manuscript and a separate title page, and only the anonymised file is ever
exposed to a reviewer (see SubmissionFile.REVIEWER_VISIBLE_KINDS).
"""

import secrets
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from account.models import CustomUser
from ckeditor.fields import RichTextField

from .storage import private_storage


# How long a reviewer has to return a report unless the editor says otherwise.
DEFAULT_REVIEW_DAYS = 28

# Reviewers are invited by email and work through a private link, so the token
# is the only thing standing between the internet and a review. 32 bytes of
# urandom, url-safe.
REVIEW_TOKEN_BYTES = 32


def generate_review_token():
    return secrets.token_urlsafe(REVIEW_TOKEN_BYTES)


class JournalSettings(models.Model):
    """Journal-wide configuration and front matter, editable in the admin.

    A single row: aims and scope, the policies a journal is expected to publish,
    and the article processing charge. Loaded through :meth:`load` so a site with
    no row configured still renders.
    """

    name = models.CharField(max_length=200, default='Journal of ELTAN (JELTAN)')
    short_name = models.CharField(max_length=50, default='JELTAN')
    tagline = models.CharField(max_length=250, blank=True)
    issn_online = models.CharField('ISSN (online)', max_length=20, blank=True)
    issn_print = models.CharField('ISSN (print)', max_length=20, blank=True)
    publisher = models.CharField(max_length=200, default='English Language Teachers Association of Nigeria')

    aims_and_scope = RichTextField(blank=True)
    author_guidelines = RichTextField(blank=True)
    peer_review_policy = RichTextField(blank=True)
    publication_ethics = RichTextField(
        blank=True,
        help_text='Malpractice statement, authorship, plagiarism, corrections and retractions.',
    )
    open_access_policy = RichTextField(blank=True)
    copyright_notice = RichTextField(blank=True)

    # A submission cannot be accepted into production until this is paid.
    apc_amount = models.DecimalField(
        'Article processing charge',
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Charged to the corresponding author once an article is accepted. Set to 0 to waive it.',
    )
    apc_currency = models.CharField(max_length=10, default='NGN')

    review_days = models.PositiveIntegerField(
        default=DEFAULT_REVIEW_DAYS,
        help_text='Days a reviewer is given to return a report, by default.',
    )
    reviews_required = models.PositiveIntegerField(
        default=2,
        help_text='Completed reviews an editor is advised to have before deciding.',
    )

    contact_email = models.EmailField(blank=True)
    cover_image = models.ImageField(upload_to='journal/covers/', blank=True, null=True)
    is_accepting_submissions = models.BooleanField(
        default=True,
        help_text='Untick to close submissions — the submit form then explains that the journal is closed.',
    )
    closed_message = models.CharField(
        max_length=300,
        blank=True,
        default='JELTAN is not accepting new submissions at the moment. Please check back soon.',
    )

    class Meta:
        verbose_name = 'Journal Settings'
        verbose_name_plural = 'Journal Settings'

    def __str__(self):
        return self.name

    @classmethod
    def load(cls):
        """The settings row, created on first access.

        Never returns None: every template and view can rely on there being a
        journal name and an APC to quote.
        """
        settings_row = cls.objects.first()
        if settings_row is None:
            settings_row = cls.objects.create()
        return settings_row

    @property
    def apc_is_waived(self):
        return not self.apc_amount or self.apc_amount <= 0


class JournalRole(models.Model):
    """Who may act as an editor on JELTAN.

    Kept separate from ``is_staff``: running the journal is not the same job as
    running the website, and an editor-in-chief should not need Django admin
    rights to make a decision.
    """

    EDITOR_IN_CHIEF = 'editor_in_chief'
    EDITOR = 'editor'
    MANAGING_EDITOR = 'managing_editor'

    ROLE_CHOICES = [
        (EDITOR_IN_CHIEF, 'Editor-in-Chief'),
        (MANAGING_EDITOR, 'Managing Editor'),
        (EDITOR, 'Section / Handling Editor'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='journal_roles')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=EDITOR)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'role')
        ordering = ['role', 'user__last_name']
        verbose_name = 'Journal Editor'
        verbose_name_plural = 'Journal Editors'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} — {self.get_role_display()}"

    @staticmethod
    def is_editor(user):
        """True for anyone who may work the editorial queue."""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return JournalRole.objects.filter(user=user, is_active=True).exists()

    @staticmethod
    def is_chief(user):
        """Editors-in-chief and managing editors — they may publish and assign."""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return JournalRole.objects.filter(
            user=user,
            is_active=True,
            role__in=[JournalRole.EDITOR_IN_CHIEF, JournalRole.MANAGING_EDITOR],
        ).exists()

    @staticmethod
    def editor_emails():
        """Addresses to notify when a manuscript needs editorial attention."""
        return list(
            JournalRole.objects.filter(is_active=True)
            .exclude(user__email='')
            .values_list('user__email', flat=True)
        )


class EditorialBoardMember(models.Model):
    """The published editorial board — front matter, not access control.

    Separate from JournalRole on purpose: most board members are academics who
    lend their name and never log in, while some editors who do log in are not
    listed publicly.
    """

    name = models.CharField(max_length=200)
    position = models.CharField(max_length=150, help_text="e.g. 'Editor-in-Chief', 'Associate Editor'.")
    affiliation = models.CharField(max_length=300, blank=True)
    country = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    orcid = models.CharField('ORCID', max_length=30, blank=True)
    photo = models.ImageField(upload_to='journal/board/', blank=True, null=True)
    bio = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Editorial Board Member'
        verbose_name_plural = 'Editorial Board'

    def __str__(self):
        return f"{self.name} — {self.position}"


class Section(models.Model):
    """A part of the journal a manuscript is submitted to, e.g. Research Articles."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    peer_reviewed = models.BooleanField(
        default=True,
        help_text='Untick for sections that are editor-reviewed only, e.g. book reviews or editorials.',
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:160]
        super().save(*args, **kwargs)


class SubmissionQuerySet(models.QuerySet):
    def in_progress(self):
        """Everything still live in the editorial pipeline."""
        return self.exclude(status__in=Submission.CLOSED_STATUSES)

    def needing_editor_attention(self):
        return self.filter(status__in=[
            Submission.SUBMITTED, Submission.EDITORIAL_SCREENING, Submission.RESUBMITTED,
        ])


class Submission(models.Model):
    """A manuscript moving through peer review."""

    SUBMITTED = 'submitted'
    RETURNED = 'returned'
    EDITORIAL_SCREENING = 'editorial_screening'
    UNDER_REVIEW = 'under_review'
    MINOR_REVISION = 'minor_revision'
    MAJOR_REVISION = 'major_revision'
    RESUBMITTED = 'resubmitted'
    ACCEPTED = 'accepted'
    IN_PRODUCTION = 'in_production'
    PROOF_REVIEW = 'proof_review'
    PROOF_APPROVED = 'proof_approved'
    PUBLISHED = 'published'
    DESK_REJECTED = 'desk_rejected'
    REJECTED = 'rejected'
    WITHDRAWN = 'withdrawn'

    STATUS_CHOICES = [
        (SUBMITTED, 'Submitted — awaiting administrative screening'),
        (RETURNED, 'Returned to author for correction'),
        (EDITORIAL_SCREENING, 'Passed screening — awaiting editorial decision'),
        (UNDER_REVIEW, 'Under peer review'),
        (MINOR_REVISION, 'Minor revisions requested'),
        (MAJOR_REVISION, 'Major revisions requested'),
        (RESUBMITTED, 'Revision submitted — awaiting editor'),
        (ACCEPTED, 'Accepted'),
        (IN_PRODUCTION, 'In production — copyediting'),
        (PROOF_REVIEW, 'Proof with the author'),
        (PROOF_APPROVED, 'Proof approved — ready to publish'),
        (PUBLISHED, 'Published'),
        (DESK_REJECTED, 'Desk rejected'),
        (REJECTED, 'Rejected after review'),
        (WITHDRAWN, 'Withdrawn by author'),
    ]

    # Nothing further happens to a manuscript in one of these states.
    CLOSED_STATUSES = [PUBLISHED, DESK_REJECTED, REJECTED, WITHDRAWN]
    # States where the ball is in the author's court for a revision.
    AUTHOR_ACTION_STATUSES = [MINOR_REVISION, MAJOR_REVISION]
    # Production: accepted, but not yet public.
    PRODUCTION_STATUSES = [IN_PRODUCTION, PROOF_REVIEW, PROOF_APPROVED]

    APC_NOT_APPLICABLE = 'not_applicable'
    APC_PENDING = 'pending'
    APC_PAID = 'paid'
    APC_WAIVED = 'waived'

    APC_STATUS_CHOICES = [
        (APC_NOT_APPLICABLE, 'Not applicable yet'),
        (APC_PENDING, 'Awaiting payment'),
        (APC_PAID, 'Paid'),
        (APC_WAIVED, 'Waived'),
    ]

    manuscript_id = models.CharField(max_length=30, unique=True, blank=True, db_index=True)
    title = models.CharField(max_length=500)
    abstract = models.TextField(help_text='250 words or fewer.')
    keywords = models.CharField(max_length=300, help_text='Comma separated, 3–6 keywords.')
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name='submissions')

    # The account that submitted. Co-authors, including the corresponding author
    # when it is not the submitter, are SubmissionAuthor rows.
    submitter = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='journal_submissions')

    cover_letter = models.TextField(blank=True)

    # Declarations. A journal has to be able to show it asked for these.
    is_original_work = models.BooleanField(default=False)
    not_under_review_elsewhere = models.BooleanField(default=False)
    agrees_to_policies = models.BooleanField(default=False)
    conflict_of_interest = models.TextField(
        blank=True,
        help_text="Any competing interests, or 'None'.",
    )
    funding_statement = models.TextField(blank=True)
    ethics_statement = models.TextField(
        blank=True,
        help_text='Ethical approval and informed consent, where human participants were involved.',
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=SUBMITTED, db_index=True)
    handling_editor = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_handled_submissions',
    )
    # Bumped each time revisions are requested; files and reviews are stamped
    # with it, which is what keeps round 1 readable after round 2 exists.
    current_round = models.PositiveIntegerField(default=1)

    submitted_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    apc_status = models.CharField(max_length=20, choices=APC_STATUS_CHOICES, default=APC_NOT_APPLICABLE)
    apc_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    apc_reference = models.CharField(max_length=100, blank=True)
    apc_paid_at = models.DateTimeField(null=True, blank=True)

    objects = SubmissionQuerySet.as_manager()

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.manuscript_id} — {self.title[:60]}"

    def save(self, *args, **kwargs):
        if not self.manuscript_id:
            self.manuscript_id = self._next_manuscript_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _next_manuscript_id():
        """A human-quotable id: JELTAN-2026-0007.

        Sequential within the year, derived from the highest existing id rather
        than from a count, so deleting a submission cannot cause a collision.
        """
        year = timezone.now().year
        prefix = f'JELTAN-{year}-'
        last = (
            Submission.objects.filter(manuscript_id__startswith=prefix)
            .order_by('-manuscript_id')
            .values_list('manuscript_id', flat=True)
            .first()
        )
        next_number = 1
        if last:
            try:
                next_number = int(last.rsplit('-', 1)[1]) + 1
            except (IndexError, ValueError):
                next_number = Submission.objects.filter(manuscript_id__startswith=prefix).count() + 1
        return f'{prefix}{next_number:04d}'

    def get_absolute_url(self):
        return reverse('journal:submission_detail', args=[self.pk])

    # --- Authors -------------------------------------------------------

    @property
    def corresponding_author(self):
        return self.authors.filter(is_corresponding=True).first() or self.authors.first()

    @property
    def author_list(self):
        """'Ada Obi, Kunle Bello' — for editors and emails, never for reviewers."""
        return ', '.join(author.full_name for author in self.authors.all())

    @property
    def notification_email(self):
        """Where correspondence about this manuscript goes."""
        author = self.corresponding_author
        if author and author.email:
            return author.email
        return self.submitter.email

    # --- Files ---------------------------------------------------------

    def files_for_round(self, round_number=None):
        round_number = self.current_round if round_number is None else round_number
        return self.files.filter(round=round_number)

    def latest_file(self, kind):
        return self.files.filter(kind=kind).order_by('-round', '-uploaded_at').first()

    @property
    def reviewer_files(self):
        """Only what a reviewer may see — never the title page.

        Double-blind review is worth nothing if the file that names the authors
        is one click away, so the filter lives here rather than in a template.
        """
        return self.files.filter(kind__in=SubmissionFile.REVIEWER_VISIBLE_KINDS).order_by('round')

    # --- Workflow ------------------------------------------------------

    @property
    def is_open(self):
        return self.status not in self.CLOSED_STATUSES

    @property
    def awaiting_author(self):
        """Revisions have been asked for after review."""
        return self.status in self.AUTHOR_ACTION_STATUSES

    @property
    def needs_correction(self):
        """Returned at administrative screening — not rejected, just incomplete."""
        return self.status == self.RETURNED

    @property
    def awaiting_proof_approval(self):
        return self.status == self.PROOF_REVIEW

    @property
    def is_screened(self):
        """Whether administrative screening has been passed for this round.

        Peer review cannot start before it has: screening is where a manuscript's
        anonymity is actually verified, and sending an un-screened paper to a
        reviewer is how an author's name reaches the person judging them.
        """
        return self.screening_reports.filter(round=self.current_round, passed=True).exists()

    @property
    def latest_screening(self):
        return self.screening_reports.filter(round=self.current_round).first()

    @property
    def latest_proof(self):
        return self.proofs.first()

    @property
    def completed_reviews(self):
        return self.review_assignments.filter(status=ReviewAssignment.SUBMITTED)

    @property
    def reviews_this_round(self):
        return self.review_assignments.filter(round=self.current_round)

    @property
    def has_enough_reviews(self):
        """Whether the editor has the number of reports the journal expects."""
        required = JournalSettings.load().reviews_required
        return self.reviews_this_round.filter(status=ReviewAssignment.SUBMITTED).count() >= required

    @property
    def apc_is_due(self):
        return self.apc_status == self.APC_PENDING

    def start_apc(self):
        """Raise the article processing charge on acceptance.

        A journal that has waived its APC must not park accepted papers behind a
        zero-naira invoice, so a waived charge settles itself and the manuscript
        goes straight to production.
        """
        settings_row = JournalSettings.load()
        if settings_row.apc_is_waived:
            self.apc_status = self.APC_WAIVED
            self.apc_amount = 0
            self.status = self.IN_PRODUCTION
        else:
            self.apc_status = self.APC_PENDING
            self.apc_amount = settings_row.apc_amount
        self.save(update_fields=['apc_status', 'apc_amount', 'status', 'updated_at'])

    def mark_apc_paid(self, reference=''):
        self.apc_status = self.APC_PAID
        self.apc_reference = reference or self.apc_reference
        self.apc_paid_at = timezone.now()
        if self.status == self.ACCEPTED:
            self.status = self.IN_PRODUCTION
        self.save(update_fields=[
            'apc_status', 'apc_reference', 'apc_paid_at', 'status', 'updated_at',
        ])

    def log(self, event, actor=None, note='', is_public=True):
        """Append to the manuscript's history.

        ``is_public=False`` keeps an entry in the editor's view only — which
        reviewer accepted, declined or reported is precisely what double-blind
        review hides from the author.
        """
        return SubmissionEvent.objects.create(
            submission=self, event=event, actor=actor, note=note,
            round=self.current_round, is_public=is_public,
        )


class SubmissionAuthor(models.Model):
    """A named author on a manuscript, in the order they should be credited."""

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='authors')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    affiliation = models.CharField(max_length=300, blank=True)
    country = models.CharField(max_length=100, blank=True)
    orcid = models.CharField('ORCID', max_length=30, blank=True)
    is_corresponding = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class SubmissionFile(models.Model):
    """One uploaded file, stamped with the round it belongs to."""

    ANONYMISED_MANUSCRIPT = 'anonymised_manuscript'
    TITLE_PAGE = 'title_page'
    SUPPLEMENTARY = 'supplementary'
    RESPONSE_TO_REVIEWERS = 'response_to_reviewers'
    REVIEW_ATTACHMENT = 'review_attachment'
    PRODUCTION = 'production'

    KIND_CHOICES = [
        (ANONYMISED_MANUSCRIPT, 'Anonymised manuscript'),
        (TITLE_PAGE, 'Title page (with author details)'),
        (SUPPLEMENTARY, 'Supplementary material'),
        (RESPONSE_TO_REVIEWERS, 'Response to reviewers'),
        (REVIEW_ATTACHMENT, 'Reviewer attachment'),
        (PRODUCTION, 'Production / proof'),
    ]

    # What a reviewer is allowed to open. The title page is excluded by design.
    REVIEWER_VISIBLE_KINDS = [ANONYMISED_MANUSCRIPT, SUPPLEMENTARY, RESPONSE_TO_REVIEWERS]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='files')
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    # Private storage, not MEDIA_ROOT — see journal/storage.py.
    file = models.FileField(upload_to='submissions/%Y/%m/', storage=private_storage)
    original_name = models.CharField(max_length=255, blank=True)
    round = models.PositiveIntegerField(default=1)
    uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['round', 'kind', 'uploaded_at']

    def __str__(self):
        return f"{self.get_kind_display()} (round {self.round})"

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = self.file.name.rsplit('/', 1)[-1][:255]
        super().save(*args, **kwargs)

    @property
    def is_reviewer_visible(self):
        return self.kind in self.REVIEWER_VISIBLE_KINDS


class ReviewAssignment(models.Model):
    """An invitation to review, and the report that comes back.

    Reviewers are usually academics with no account here, so the invitation
    carries a private token and the whole review is done through that link. A
    reviewer who does happen to have an account is linked as well, so their
    history is not lost.
    """

    INVITED = 'invited'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'
    SUBMITTED = 'submitted'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (INVITED, 'Invited — awaiting response'),
        (ACCEPTED, 'Accepted — review in progress'),
        (DECLINED, 'Declined'),
        (SUBMITTED, 'Review submitted'),
        (CANCELLED, 'Cancelled by editor'),
    ]

    ACCEPT = 'accept'
    MINOR_REVISION = 'minor_revision'
    MAJOR_REVISION = 'major_revision'
    REJECT = 'reject'

    RECOMMENDATION_CHOICES = [
        (ACCEPT, 'Accept as is'),
        (MINOR_REVISION, 'Accept after minor revisions'),
        (MAJOR_REVISION, 'Major revisions required, then re-review'),
        (REJECT, 'Reject'),
    ]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='review_assignments')
    round = models.PositiveIntegerField(default=1)

    reviewer_name = models.CharField(max_length=200)
    reviewer_email = models.EmailField()
    reviewer_affiliation = models.CharField(max_length=300, blank=True)
    reviewer_user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_reviews',
    )

    token = models.CharField(max_length=100, unique=True, default=generate_review_token, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=INVITED, db_index=True)

    invited_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.TextField(blank=True)

    # The report itself.
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, blank=True)
    comments_to_author = models.TextField(blank=True)
    # Never shown to the author, under any status.
    confidential_comments = models.TextField(
        blank=True,
        help_text='Seen by the editors only — never sent to the author.',
    )
    rating_originality = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    rating_methodology = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    rating_clarity = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    rating_relevance = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    class Meta:
        ordering = ['round', 'invited_at']
        verbose_name = 'Review Assignment'

    def __str__(self):
        return f"{self.reviewer_name} — {self.submission.manuscript_id} (round {self.round})"

    def save(self, *args, **kwargs):
        if not self.due_date:
            days = JournalSettings.load().review_days or DEFAULT_REVIEW_DAYS
            self.due_date = (timezone.now() + timedelta(days=days)).date()
        super().save(*args, **kwargs)

    @property
    def review_url(self):
        return reverse('journal:review', args=[self.token])

    @property
    def is_open(self):
        return self.status in [self.INVITED, self.ACCEPTED]

    @property
    def is_overdue(self):
        return bool(
            self.is_open
            and self.status == self.ACCEPTED
            and self.due_date
            and self.due_date < timezone.now().date()
        )

    @property
    def days_until_due(self):
        if not self.due_date:
            return None
        return (self.due_date - timezone.now().date()).days

    def accept(self):
        self.status = self.ACCEPTED
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'responded_at'])

    def decline(self, reason=''):
        self.status = self.DECLINED
        self.decline_reason = reason
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'decline_reason', 'responded_at'])

    def cancel(self):
        self.status = self.CANCELLED
        self.save(update_fields=['status'])


class ScreeningReport(models.Model):
    """The administrative check a manuscript passes before it reaches an editor.

    This is the technical check, not a judgement on the work: are the files
    there, is the manuscript actually anonymised, are the declarations complete.
    Failing it returns the paper to the author for correction — it is not a
    rejection, and the author resubmits into the same record.

    It is recorded rather than done by eye because the anonymity check is the one
    thing standing between an author's name and the reviewer judging them, and
    'we always check' is not something a journal can demonstrate later.
    """

    CHECKS = [
        ('files_complete', 'All required files are present and open correctly'),
        ('is_anonymised', 'The manuscript is genuinely anonymised (no author names, affiliations, '
                          'identifying acknowledgements or self-identifying citations)'),
        ('title_page_separate', 'A separate title page carries the author details'),
        ('abstract_and_keywords', 'The abstract and keywords meet the guidelines'),
        ('declarations_complete', 'Declarations (originality, competing interests, ethics) are complete'),
        ('references_formatted', 'References follow the journal style'),
    ]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='screening_reports')
    round = models.PositiveIntegerField(default=1)

    files_complete = models.BooleanField(default=False)
    is_anonymised = models.BooleanField(default=False)
    title_page_separate = models.BooleanField(default=False)
    abstract_and_keywords = models.BooleanField(default=False)
    declarations_complete = models.BooleanField(default=False)
    references_formatted = models.BooleanField(default=False)

    passed = models.BooleanField(default=False)
    notes_to_author = models.TextField(
        blank=True,
        help_text='What the author must put right. Sent to them when the manuscript is returned.',
    )
    internal_notes = models.TextField(blank=True, help_text='Editorial office only.')

    screened_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    screened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-screened_at']
        verbose_name = 'Screening Report'

    def __str__(self):
        return f"{self.submission.manuscript_id} — {'passed' if self.passed else 'returned'}"

    @property
    def failed_checks(self):
        """The checklist items that were not ticked, for the letter to the author."""
        return [label for field, label in self.CHECKS if not getattr(self, field)]


class Proof(models.Model):
    """A typeset proof sent to the author for approval before publication.

    Versioned, because an author who asks for corrections gets a second proof —
    and the record of what they were shown, and what they said about it, is the
    journal's answer when a published error is disputed later.
    """

    SENT = 'sent'
    APPROVED = 'approved'
    CORRECTIONS_REQUESTED = 'corrections_requested'
    SUPERSEDED = 'superseded'

    STATUS_CHOICES = [
        (SENT, 'With the author'),
        (APPROVED, 'Approved by the author'),
        (CORRECTIONS_REQUESTED, 'Corrections requested'),
        (SUPERSEDED, 'Superseded by a later proof'),
    ]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='proofs')
    version = models.PositiveIntegerField(default=1)
    file = models.FileField(upload_to='proofs/%Y/', storage=private_storage)
    original_name = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=SENT)
    note_to_author = models.TextField(blank=True)
    due_date = models.DateField(
        null=True, blank=True,
        help_text='Proofs are usually returned within a few days.',
    )

    sent_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    corrections = models.TextField(blank=True, help_text="The author's corrections, in their words.")
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-version']

    def __str__(self):
        return f"{self.submission.manuscript_id} proof v{self.version}"

    def save(self, *args, **kwargs):
        if not self.pk and not self.version:
            self.version = self.submission.proofs.count() + 1
        if self.file and not self.original_name:
            self.original_name = self.file.name.rsplit('/', 1)[-1][:255]
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status == self.SENT

    @property
    def is_overdue(self):
        return bool(self.is_open and self.due_date and self.due_date < timezone.now().date())


class EditorialDecision(models.Model):
    """A decision recorded by an editor, with the letter the author was sent."""

    DESK_REJECT = 'desk_reject'
    SEND_FOR_REVIEW = 'send_for_review'
    ACCEPT = 'accept'
    MINOR_REVISION = 'minor_revision'
    MAJOR_REVISION = 'major_revision'
    REJECT = 'reject'

    DECISION_CHOICES = [
        (SEND_FOR_REVIEW, 'Send for peer review'),
        (DESK_REJECT, 'Desk reject (out of scope / below threshold)'),
        (MINOR_REVISION, 'Minor revisions required'),
        (MAJOR_REVISION, 'Major revisions required'),
        (ACCEPT, 'Accept'),
        (REJECT, 'Reject'),
    ]

    # What each decision does to the manuscript. A decision that does not move
    # the paper is not a decision, so every choice appears here.
    RESULTING_STATUS = {
        SEND_FOR_REVIEW: Submission.UNDER_REVIEW,
        DESK_REJECT: Submission.DESK_REJECTED,
        MINOR_REVISION: Submission.MINOR_REVISION,
        MAJOR_REVISION: Submission.MAJOR_REVISION,
        ACCEPT: Submission.ACCEPTED,
        REJECT: Submission.REJECTED,
    }

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='decisions')
    round = models.PositiveIntegerField(default=1)
    decision = models.CharField(max_length=30, choices=DECISION_CHOICES)
    editor = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    letter_to_author = models.TextField(
        blank=True,
        help_text='Sent to the corresponding author as the decision letter.',
    )
    share_reviews_with_author = models.BooleanField(
        default=True,
        help_text="Include the reviewers' comments to the author in the decision email.",
    )
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-decided_at']

    def __str__(self):
        return f"{self.submission.manuscript_id} — {self.get_decision_display()}"


class SubmissionEvent(models.Model):
    """The manuscript's history, in order.

    Authors ask 'where is my paper?' and editors have to answer months later, so
    every state change leaves a row here rather than only a changed status field.
    """

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='events')
    event = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    round = models.PositiveIntegerField(default=1)
    actor = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # Author-facing by default; confidential entries stay in the editor view.
    is_public = models.BooleanField(
        default=True,
        help_text='Whether the author sees this entry on their submission page.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.submission.manuscript_id}: {self.event}"


class Issue(models.Model):
    """A published issue — Volume 1, Issue 2 (2026)."""

    volume = models.PositiveIntegerField()
    number = models.PositiveIntegerField()
    year = models.PositiveIntegerField()
    title = models.CharField(max_length=250, blank=True, help_text='Optional theme, e.g. "Special Issue on Multilingual Classrooms".')
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = RichTextField(blank=True)
    cover_image = models.ImageField(upload_to='journal/issues/', blank=True, null=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-volume', '-number']
        unique_together = ('volume', 'number')

    def __str__(self):
        return self.label

    @property
    def label(self):
        return f"Vol. {self.volume}, No. {self.number} ({self.year})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"vol-{self.volume}-no-{self.number}-{self.year}")[:120]
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('journal:issue_detail', args=[self.slug])

    @property
    def public_articles(self):
        return self.articles.filter(is_published=True)


class Article(models.Model):
    """A published paper.

    Separate from Submission so the back catalogue can be loaded without a
    review history, and so publication metadata (pages, DOI, licence) can be
    corrected without rewriting what was decided during review.
    """

    submission = models.OneToOneField(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='article',
        help_text='The manuscript this was published from. Blank for back issues loaded by hand.',
    )
    issue = models.ForeignKey(
        Issue, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles',
        help_text='Leave blank to publish online first, ahead of an issue.',
    )
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')

    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    abstract = models.TextField()
    keywords = models.CharField(max_length=300, blank=True)

    pdf = models.FileField(upload_to='journal/articles/%Y/', help_text='The typeset article (galley PDF).')
    first_page = models.PositiveIntegerField(null=True, blank=True)
    last_page = models.PositiveIntegerField(null=True, blank=True)
    doi = models.CharField('DOI', max_length=120, blank=True)
    licence = models.CharField(
        max_length=120,
        default='CC BY 4.0',
        help_text='The licence the article is published under.',
    )

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['issue', 'first_page', 'title']

    def __str__(self):
        return self.title[:80]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.title)[:200] or 'article'
        slug = base
        suffix = 2
        while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def clean(self):
        if self.first_page and self.last_page and self.last_page < self.first_page:
            raise ValidationError({'last_page': 'The last page cannot come before the first page.'})

    def get_absolute_url(self):
        return reverse('journal:article_detail', args=[self.slug])

    @property
    def author_list(self):
        return ', '.join(author.full_name for author in self.authors.all())

    @property
    def page_range(self):
        if self.first_page and self.last_page:
            return f"{self.first_page}–{self.last_page}"
        return str(self.first_page or '')

    @property
    def keyword_list(self):
        """Keywords as a list — indexing metadata needs one tag per keyword."""
        return [keyword.strip() for keyword in (self.keywords or '').split(',') if keyword.strip()]

    @property
    def citation(self):
        """An APA-style citation for the article page and for anyone quoting it."""
        settings_row = JournalSettings.load()
        year = self.published_at.year if self.published_at else timezone.now().year
        parts = [f"{self.author_list} ({year}). {self.title}. {settings_row.name}"]
        if self.issue:
            parts.append(f", {self.issue.volume}({self.issue.number})")
        if self.page_range:
            parts.append(f", {self.page_range}")
        parts.append('.')
        if self.doi:
            parts.append(f" https://doi.org/{self.doi}")
        return ''.join(parts)


class ArticleAuthor(models.Model):
    """A credited author on a published article.

    Held as rows rather than one name string so the article page can emit the
    ``citation_author`` metadata that Google Scholar and other indexers read.
    """

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='authors')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    affiliation = models.CharField(max_length=300, blank=True)
    country = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    orcid = models.CharField('ORCID', max_length=30, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
