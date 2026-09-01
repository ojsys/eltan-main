"""Forms for the JELTAN editorial workflow."""

from datetime import datetime, time

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .ingest import SUPPORTED_EXTENSIONS
from .models import (
    Article,
    ArticleAuthor,
    EditorialDecision,
    Issue,
    Proof,
    ReviewAssignment,
    ScreeningReport,
    Section,
    Submission,
    SubmissionAuthor,
)

# Manuscripts are read by human reviewers, not parsed by us, so the list is about
# keeping out things that cannot be opened (or should not be uploaded) rather
# than about format policing.
MANUSCRIPT_EXTENSIONS = ['.doc', '.docx', '.rtf', '.odt', '.pdf']
SUPPLEMENTARY_EXTENSIONS = MANUSCRIPT_EXTENSIONS + ['.xls', '.xlsx', '.csv', '.zip', '.png', '.jpg', '.jpeg']
MAX_UPLOAD_MB = 20


def validate_upload(uploaded, allowed_extensions, label):
    """Reject a file the journal cannot accept, with a message that says why."""
    if not uploaded:
        return uploaded
    name = getattr(uploaded, 'name', '') or ''
    extension = ('.' + name.rsplit('.', 1)[1].lower()) if '.' in name else ''
    if extension not in allowed_extensions:
        raise forms.ValidationError(
            f"{label} must be one of: {', '.join(allowed_extensions)}. "
            f"You uploaded '{extension or name}'."
        )
    size = getattr(uploaded, 'size', 0) or 0
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        raise forms.ValidationError(
            f'{label} is {size / (1024 * 1024):.1f} MB — the limit is {MAX_UPLOAD_MB} MB.'
        )
    return uploaded


class BootstrapFormMixin:
    """Give every widget the form styling the rest of the site uses."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                continue
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = (existing + ' form-control').strip()


class SubmissionForm(BootstrapFormMixin, forms.ModelForm):
    """The manuscript submission form.

    Double-blind review is enforced here: the anonymised manuscript and the title
    page are separate, required uploads, because a single file with the authors'
    names on page one cannot be sent to a reviewer.
    """

    anonymised_manuscript = forms.FileField(
        label='Anonymised manuscript',
        help_text=(
            'Your paper with all identifying details removed — no author names, '
            'affiliations, acknowledgements or self-citations that give you away. '
            f"Accepted formats: {', '.join(MANUSCRIPT_EXTENSIONS)}."
        ),
    )
    title_page = forms.FileField(
        label='Title page',
        help_text=(
            'A separate file with the title, all authors, their affiliations and '
            'the corresponding author. This is never shown to reviewers.'
        ),
    )
    supplementary_file = forms.FileField(
        label='Supplementary material (optional)',
        required=False,
        help_text='Data, instruments or appendices, if any.',
    )

    class Meta:
        model = Submission
        fields = [
            'section', 'title', 'abstract', 'keywords', 'cover_letter',
            'conflict_of_interest', 'funding_statement', 'ethics_statement',
            'is_original_work', 'not_under_review_elsewhere', 'agrees_to_policies',
        ]
        widgets = {
            'abstract': forms.Textarea(attrs={'rows': 6}),
            'cover_letter': forms.Textarea(attrs={'rows': 5}),
            'conflict_of_interest': forms.Textarea(attrs={'rows': 3}),
            'funding_statement': forms.Textarea(attrs={'rows': 2}),
            'ethics_statement': forms.Textarea(attrs={'rows': 3}),
            'title': forms.TextInput(attrs={'placeholder': 'The full title of your paper'}),
            'keywords': forms.TextInput(attrs={'placeholder': 'e.g. reading comprehension, ESL, secondary school'}),
        }
        labels = {
            'is_original_work': 'This manuscript is my/our original work and has not been published elsewhere.',
            'not_under_review_elsewhere': 'This manuscript is not under consideration by another journal.',
            'agrees_to_policies': "I have read and accept the author guidelines, peer review and publication ethics policies.",
        }
        help_texts = {
            'conflict_of_interest': "State any competing interests, or write 'None'.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.filter(is_active=True)
        self.fields['section'].empty_label = 'Select a section'
        for name in ['is_original_work', 'not_under_review_elsewhere', 'agrees_to_policies']:
            self.fields[name].required = True

    def clean_abstract(self):
        abstract = self.cleaned_data['abstract'].strip()
        words = len(abstract.split())
        if words > 250:
            raise forms.ValidationError(f'The abstract is {words} words — the limit is 250.')
        if words < 50:
            raise forms.ValidationError(f'The abstract is only {words} words. Please write at least 50.')
        return abstract

    def clean_keywords(self):
        keywords = [k.strip() for k in self.cleaned_data['keywords'].split(',') if k.strip()]
        if not 3 <= len(keywords) <= 6:
            raise forms.ValidationError(f'Give between 3 and 6 keywords — you gave {len(keywords)}.')
        return ', '.join(keywords)

    def clean_anonymised_manuscript(self):
        return validate_upload(
            self.cleaned_data.get('anonymised_manuscript'), MANUSCRIPT_EXTENSIONS, 'The manuscript',
        )

    def clean_title_page(self):
        return validate_upload(
            self.cleaned_data.get('title_page'), MANUSCRIPT_EXTENSIONS, 'The title page',
        )

    def clean_supplementary_file(self):
        return validate_upload(
            self.cleaned_data.get('supplementary_file'), SUPPLEMENTARY_EXTENSIONS, 'Supplementary material',
        )


class SubmissionAuthorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SubmissionAuthor
        fields = ['first_name', 'last_name', 'email', 'affiliation', 'country', 'orcid', 'is_corresponding']


SubmissionAuthorFormSet = inlineformset_factory(
    Submission,
    SubmissionAuthor,
    form=SubmissionAuthorForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class RevisionForm(BootstrapFormMixin, forms.Form):
    """What an author uploads when revisions have been requested.

    The response letter is required, not optional: a revision without a
    point-by-point reply cannot be sent back to a reviewer.
    """

    revised_manuscript = forms.FileField(
        label='Revised anonymised manuscript',
        help_text='Still anonymised — reviewers see this file.',
    )
    response_to_reviewers = forms.FileField(
        label='Response to reviewers',
        help_text="A point-by-point reply to each reviewer's comments.",
    )
    revised_title_page = forms.FileField(
        label='Updated title page (optional)',
        required=False,
        help_text='Only if the authors or affiliations have changed.',
    )
    note_to_editor = forms.CharField(
        label='Note to the editor (optional)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def clean_revised_manuscript(self):
        return validate_upload(
            self.cleaned_data.get('revised_manuscript'), MANUSCRIPT_EXTENSIONS, 'The revised manuscript',
        )

    def clean_response_to_reviewers(self):
        return validate_upload(
            self.cleaned_data.get('response_to_reviewers'), MANUSCRIPT_EXTENSIONS, 'The response to reviewers',
        )

    def clean_revised_title_page(self):
        return validate_upload(
            self.cleaned_data.get('revised_title_page'), MANUSCRIPT_EXTENSIONS, 'The title page',
        )


class ScreeningForm(BootstrapFormMixin, forms.ModelForm):
    """The administrative screening checklist.

    Failing the check returns the manuscript to the author, so the notes are
    required in that case — 'returned' with no explanation is a message the
    author cannot act on.
    """

    class Meta:
        model = ScreeningReport
        fields = [
            'files_complete', 'is_anonymised', 'title_page_separate',
            'abstract_and_keywords', 'declarations_complete', 'references_formatted',
            'notes_to_author', 'internal_notes',
        ]
        widgets = {
            'notes_to_author': forms.Textarea(attrs={'rows': 5}),
            'internal_notes': forms.Textarea(attrs={'rows': 3}),
        }
        labels = dict(ScreeningReport.CHECKS)
        help_texts = {
            'notes_to_author': 'Required if you are returning the manuscript. Say exactly what to put right.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 'outcome' rather than a bare 'passed' checkbox: an editor should have to
        # say what they are doing, not leave a box unticked by accident.
        self.fields['outcome'] = forms.ChoiceField(
            label='Outcome',
            choices=[
                ('pass', 'Passes screening — send to editorial screening'),
                ('return', 'Return to the author for correction'),
            ],
            widget=forms.RadioSelect,
            initial='pass',
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('outcome') == 'return' and not (cleaned.get('notes_to_author') or '').strip():
            self.add_error(
                'notes_to_author',
                'Tell the author what needs correcting — they cannot act on a bare "returned".',
            )
        if cleaned.get('outcome') == 'pass' and not cleaned.get('is_anonymised'):
            self.add_error(
                'is_anonymised',
                'A manuscript cannot pass screening until it is confirmed anonymised — '
                'reviewers must not be able to identify the authors.',
            )
        return cleaned


class CorrectedSubmissionForm(BootstrapFormMixin, forms.Form):
    """What an author uploads after a manuscript is returned at screening.

    Deliberately not the revision form: nothing has been reviewed yet, so there
    are no reviewers to respond to, and this does not open a new review round.
    """

    corrected_manuscript = forms.FileField(
        label='Corrected anonymised manuscript',
        help_text='With the points raised by the editorial office put right.',
    )
    corrected_title_page = forms.FileField(
        label='Title page (optional)',
        required=False,
        help_text='Only if the title page also needed correcting.',
    )
    note_to_editor = forms.CharField(
        label='What you changed',
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text='A short note on how you addressed each point.',
    )

    def clean_corrected_manuscript(self):
        return validate_upload(
            self.cleaned_data.get('corrected_manuscript'), MANUSCRIPT_EXTENSIONS, 'The manuscript',
        )

    def clean_corrected_title_page(self):
        return validate_upload(
            self.cleaned_data.get('corrected_title_page'), MANUSCRIPT_EXTENSIONS, 'The title page',
        )


class CopyeditForm(BootstrapFormMixin, forms.Form):
    """The copyedited manuscript, uploaded by the editorial office."""

    copyedited_file = forms.FileField(
        label='Copyedited manuscript',
        help_text='The manuscript after copyediting. Kept on file; not sent to the author by itself.',
    )
    note = forms.CharField(
        label='Note (optional)', required=False, widget=forms.Textarea(attrs={'rows': 2}),
    )

    def clean_copyedited_file(self):
        return validate_upload(
            self.cleaned_data.get('copyedited_file'), SUPPLEMENTARY_EXTENSIONS, 'The copyedited file',
        )


class ProofForm(BootstrapFormMixin, forms.ModelForm):
    """An editor sending a typeset proof to the author for approval."""

    class Meta:
        model = Proof
        fields = ['file', 'note_to_author', 'due_date']
        widgets = {
            'note_to_author': forms.Textarea(attrs={'rows': 4}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'file': 'Typeset proof (PDF)',
            'note_to_author': 'Note to the author',
            'due_date': 'Corrections due by',
        }
        help_texts = {
            'note_to_author': 'What to check, and what may still be changed at this stage.',
        }

    def clean_file(self):
        return validate_upload(self.cleaned_data.get('file'), ['.pdf'], 'The proof')

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise forms.ValidationError('That date has already passed.')
        return due_date


class ProofResponseForm(BootstrapFormMixin, forms.Form):
    """The author approving a proof, or asking for corrections.

    Approval is the last point at which an error can be caught, so the two
    outcomes are an explicit choice rather than two buttons that look alike.
    """

    APPROVE = 'approve'
    CORRECTIONS = 'corrections'

    response = forms.ChoiceField(
        label='Your response',
        choices=[
            (APPROVE, 'I approve this proof for publication'),
            (CORRECTIONS, 'Corrections are needed before publication'),
        ],
        widget=forms.RadioSelect,
    )
    corrections = forms.CharField(
        label='Corrections',
        required=False,
        widget=forms.Textarea(attrs={'rows': 8}),
        help_text='List each correction with the page and line it applies to.',
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('response') == self.CORRECTIONS and not (cleaned.get('corrections') or '').strip():
            self.add_error('corrections', 'List the corrections you need.')
        return cleaned


class ReviewerInviteForm(BootstrapFormMixin, forms.ModelForm):
    """An editor inviting someone to review."""

    personal_message = forms.CharField(
        label='Personal message (optional)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Added to the invitation email above the manuscript details.',
    )

    class Meta:
        model = ReviewAssignment
        fields = ['reviewer_name', 'reviewer_email', 'reviewer_affiliation', 'due_date']
        widgets = {'due_date': forms.DateInput(attrs={'type': 'date'})}
        labels = {
            'reviewer_name': 'Reviewer name',
            'reviewer_email': 'Reviewer email',
            'reviewer_affiliation': 'Affiliation (optional)',
            'due_date': 'Review due by',
        }

    def __init__(self, *args, submission=None, **kwargs):
        self.submission = submission
        super().__init__(*args, **kwargs)

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise forms.ValidationError('The due date is in the past.')
        return due_date

    def clean_reviewer_email(self):
        email = self.cleaned_data['reviewer_email'].lower().strip()
        if not self.submission:
            return email

        # An author must never review their own paper.
        author_emails = {a.email.lower() for a in self.submission.authors.all() if a.email}
        author_emails.add(self.submission.submitter.email.lower())
        if email in author_emails:
            raise forms.ValidationError(
                'That address belongs to an author of this manuscript — they cannot review it.'
            )

        already = self.submission.review_assignments.filter(
            reviewer_email__iexact=email,
            round=self.submission.current_round,
        ).exclude(status=ReviewAssignment.CANCELLED)
        if already.exists():
            raise forms.ValidationError('This reviewer has already been invited for the current round.')
        return email


class ReviewForm(BootstrapFormMixin, forms.ModelForm):
    """The review report itself.

    ``comments_to_author`` is passed on verbatim; ``confidential_comments`` never
    leaves the editorial team — the labels say so, because reviewers routinely
    put candour in the wrong box.
    """

    attachment = forms.FileField(
        label='Annotated manuscript or attachment (optional)',
        required=False,
        help_text='If you marked up the manuscript, upload it here.',
    )

    class Meta:
        model = ReviewAssignment
        fields = [
            'recommendation',
            'rating_originality', 'rating_methodology', 'rating_clarity', 'rating_relevance',
            'comments_to_author', 'confidential_comments',
        ]
        widgets = {
            'comments_to_author': forms.Textarea(attrs={'rows': 10}),
            'confidential_comments': forms.Textarea(attrs={'rows': 5}),
            'recommendation': forms.RadioSelect(),
        }
        labels = {
            'recommendation': 'Your recommendation',
            'comments_to_author': 'Comments to the author',
            'confidential_comments': 'Confidential comments to the editor',
            'rating_originality': 'Originality (1–5)',
            'rating_methodology': 'Methodology (1–5)',
            'rating_clarity': 'Clarity of writing (1–5)',
            'rating_relevance': 'Relevance to the journal (1–5)',
        }
        help_texts = {
            'comments_to_author': 'Sent to the author, anonymously. Be specific and constructive.',
            'confidential_comments': 'The editors only. The author never sees this.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recommendation'].required = True
        self.fields['comments_to_author'].required = True
        for name in ['rating_originality', 'rating_methodology', 'rating_clarity', 'rating_relevance']:
            self.fields[name].widget = forms.Select(
                choices=[('', '—')] + [(n, str(n)) for n in range(1, 6)],
                attrs={'class': 'form-control'},
            )

    def clean_comments_to_author(self):
        comments = self.cleaned_data['comments_to_author'].strip()
        if len(comments) < 50:
            raise forms.ValidationError(
                'Please give the author more than a line or two — at least 50 characters.'
            )
        return comments

    def clean_attachment(self):
        return validate_upload(
            self.cleaned_data.get('attachment'), SUPPLEMENTARY_EXTENSIONS, 'The attachment',
        )


class DecisionForm(BootstrapFormMixin, forms.ModelForm):
    """An editor recording a decision and the letter that goes with it."""

    class Meta:
        model = EditorialDecision
        fields = ['decision', 'letter_to_author', 'share_reviews_with_author']
        widgets = {'letter_to_author': forms.Textarea(attrs={'rows': 10})}
        labels = {
            'decision': 'Decision',
            'letter_to_author': 'Decision letter to the author',
            'share_reviews_with_author': "Include the reviewers' comments to the author",
        }

    def __init__(self, *args, submission=None, **kwargs):
        self.submission = submission
        super().__init__(*args, **kwargs)
        self.fields['letter_to_author'].required = True

        # Desk decisions and post-review decisions are different moments, so the
        # dropdown offers what this manuscript can actually do next rather than
        # every decision the journal knows about. The list lives on the model:
        # the portal shows the same one, and the two must not drift apart.
        self.fields['decision'].choices = EditorialDecision.choices_for(submission)


class IssueForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Issue
        fields = ['volume', 'number', 'year', 'title', 'description', 'cover_image', 'is_published']


class PublishArticleForm(BootstrapFormMixin, forms.ModelForm):
    """Turn an accepted manuscript into a published article."""

    class Meta:
        model = Article
        fields = [
            'issue', 'title', 'abstract', 'keywords', 'pdf',
            'first_page', 'last_page', 'doi', 'licence', 'is_published',
        ]
        widgets = {'abstract': forms.Textarea(attrs={'rows': 6})}
        labels = {
            'pdf': 'Typeset article (PDF)',
            'is_published': 'Publish now (visible to the public)',
        }
        help_texts = {
            'issue': 'Leave blank to publish online first, ahead of an issue.',
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_published') and not cleaned.get('pdf') and not self.instance.pdf:
            raise forms.ValidationError('Upload the typeset PDF before publishing the article.')
        return cleaned


class DirectArticleForm(BootstrapFormMixin, forms.ModelForm):
    """Load an article that never went through this system's review.

    Two cases, one form: the back catalogue, and papers reviewed elsewhere or
    on paper that are ready to publish as they stand. Both need the publication
    date to be set by hand — an article from 2019 must not be dated today — and
    both need a section, because that is what drives the OAI sets that indexers
    harvest.
    """

    publication_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Publication date',
        help_text='The date this article was published. Leave blank to use today.',
    )
    notify_authors = forms.BooleanField(
        required=False,
        initial=True,
        label='Email the authors that it is live',
        help_text='Untick when loading a back issue — the authors were told years ago.',
    )

    class Meta:
        model = Article
        fields = [
            'section', 'issue', 'title', 'abstract', 'keywords', 'source_file',
            'first_page', 'last_page', 'doi', 'licence', 'is_published',
        ]
        widgets = {'abstract': forms.Textarea(attrs={'rows': 6})}
        labels = {
            'source_file': 'Article file (Word or PDF)',
            'is_published': 'Publish now (visible to the public)',
        }
        help_texts = {
            'issue': 'Leave blank to publish online first, ahead of an issue.',
            'keywords': 'Comma separated.',
            'source_file': (
                'A Word manuscript is typeset into the JELTAN template, full text and all. '
                'A PDF keeps its own pages, with a JELTAN cover page in front of them.'
            ),
        }

    # The three publication controls read as one decision — when it came out,
    # whether it goes public, and who hears about it — so they sit together and
    # in that order, rather than wherever the model happened to declare them.
    field_order = [
        'section', 'issue', 'title', 'abstract', 'keywords', 'source_file',
        'first_page', 'last_page', 'doi', 'licence',
        'publication_date', 'is_published', 'notify_authors',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.filter(is_active=True)
        self.fields['section'].empty_label = 'Select a section'
        # The section is optional on the model so old rows survive, but a new
        # article without one is invisible to a harvester and unlabelled on the
        # page, so it is required here.
        self.fields['section'].required = True
        self.fields['issue'].empty_label = 'Online first — no issue yet'

        if self.instance.pk and self.instance.published_at:
            self.fields['publication_date'].initial = self.instance.published_at.date()

    def clean_source_file(self):
        return validate_upload(
            self.cleaned_data.get('source_file'), SUPPORTED_EXTENSIONS, 'The article file',
        )

    def clean(self):
        cleaned = super().clean()
        has_file = cleaned.get('source_file') or self.instance.source_file or self.instance.pdf
        if cleaned.get('is_published') and not has_file:
            raise forms.ValidationError('Upload the article file before publishing it.')
        return cleaned

    def save(self, commit=True):
        article = super().save(commit=False)

        # A date, not a datetime, is what an editor knows. Midnight in the
        # project's timezone is the honest reading of it, and storing it aware
        # keeps it from shifting a day when it is rendered.
        date = self.cleaned_data.get('publication_date')
        if date:
            article.published_at = timezone.make_aware(
                datetime.combine(date, time.min), timezone.get_current_timezone(),
            )
        elif not article.is_published:
            # Unpublishing should not leave a publication date behind, or the
            # article claims a date it never had.
            article.published_at = None

        if commit:
            article.save()
        return article


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A file input that accepts a whole folder's worth at once.

    Django's own FileField cleans a single upload; the documented way to take
    several is to widen both the widget and the cleaning, which is all this is.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(item, initial) for item in data]
        return [clean_one(data, initial)]


class ArticleImportForm(BootstrapFormMixin, forms.Form):
    """Step one of a bulk import: the files, and what they have in common.

    Section, issue and licence are asked once rather than per article because a
    batch is nearly always one issue of one journal, and asking twenty times is
    how a wrong value gets clicked through.
    """

    MAX_FILES = 40

    files = MultipleFileField(
        label='Article files',
        help_text=f'PDF or Word (.docx), up to {MAX_FILES} at a time. Select them all at once.',
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.none(), empty_label='Select a section',
        help_text='Applied to every article in this batch. It can be changed per article on the next screen.',
    )
    issue = forms.ModelChoiceField(
        queryset=Issue.objects.none(), required=False,
        empty_label='Online first — no issue yet',
    )
    licence = forms.CharField(max_length=120, initial='CC BY 4.0')
    publication_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='The date these articles were published. Leave blank to use today.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.filter(is_active=True)
        self.fields['issue'].queryset = Issue.objects.all()

    def clean_files(self):
        uploaded = self.cleaned_data['files']
        if len(uploaded) > self.MAX_FILES:
            raise forms.ValidationError(
                f'{len(uploaded)} files — {self.MAX_FILES} is the most in one batch. '
                'Split the upload and run it twice.'
            )
        for item in uploaded:
            validate_upload(item, SUPPORTED_EXTENSIONS, f'"{item.name}"')
        return uploaded


class DocumentUploadForm(BootstrapFormMixin, forms.Form):
    """One manuscript, from which the whole article is generated.

    Deliberately short. Everything else about the article — its title, byline,
    abstract, keywords and sections — is read out of the document itself and
    shown for checking on the next screen, so asking for any of it here would
    be asking twice.
    """

    document = forms.FileField(
        label='The manuscript',
        help_text=(
            'A Word file (.docx) is read in full — title, authors, abstract, keywords '
            'and every section. A PDF gives its front matter only, and keeps its own pages.'
        ),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.none(), empty_label='Select a section',
    )
    issue = forms.ModelChoiceField(
        queryset=Issue.objects.none(), required=False,
        empty_label='Online first — no issue yet',
    )
    licence = forms.CharField(max_length=120, initial='CC BY 4.0')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.filter(is_active=True)
        self.fields['issue'].queryset = Issue.objects.all()

    def clean_document(self):
        return validate_upload(
            self.cleaned_data.get('document'), SUPPORTED_EXTENSIONS, 'The manuscript',
        )


class ImportedArticleForm(BootstrapFormMixin, forms.ModelForm):
    """One row on the import review screen.

    The byline is one text field rather than a nested formset: twenty articles
    of six author sub-forms each is a screen nobody can work. Affiliations and
    ORCIDs belong on the article's own page, and there is a link to it.
    """

    authors = forms.CharField(
        required=False,
        label='Authors',
        help_text='Comma separated, in credit order — "Ada Obi, Chidi Eze".',
    )
    publish = forms.BooleanField(required=False, label='Publish')

    class Meta:
        model = Article
        fields = ['section', 'issue', 'title', 'authors', 'abstract', 'keywords',
                  'first_page', 'last_page', 'doi']
        widgets = {'abstract': forms.Textarea(attrs={'rows': 4})}

    field_order = ['title', 'authors', 'abstract', 'keywords', 'section', 'issue',
                   'first_page', 'last_page', 'doi', 'publish']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.filter(is_active=True)
        self.fields['issue'].queryset = Issue.objects.all()
        self.fields['issue'].empty_label = 'Online first'
        # Both were explained once when the batch was set up; repeating the help
        # text on every row only pushes the short fields out of alignment.
        self.fields['issue'].help_text = ''
        self.fields['section'].help_text = ''
        if self.instance.pk and 'authors' not in self.initial:
            self.initial['authors'] = self.instance.author_list

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('publish'):
            if not cleaned.get('title'):
                self.add_error('title', 'A title is needed before this can be published.')
            if not (cleaned.get('authors') or '').strip():
                self.add_error(
                    'authors',
                    'Add the byline before publishing — an article with no credited author '
                    'is worse in the record than one still waiting.',
                )
        return cleaned


ImportedArticleFormSet = forms.modelformset_factory(
    Article, form=ImportedArticleForm, extra=0,
    # Discarding a row is the formset's own delete, which is what makes Django
    # skip validating it: complaining that a file being thrown away has no
    # title would leave an editor unable to throw it away.
    can_delete=True,
)


class ArticleAuthorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ArticleAuthor
        fields = ['first_name', 'last_name', 'affiliation', 'country', 'email', 'orcid']


ArticleAuthorFormSet = inlineformset_factory(
    Article, ArticleAuthor, form=ArticleAuthorForm, extra=1, min_num=1, validate_min=True,
    # Saved authors can be removed; an empty slot has nothing to delete, and
    # offering it there only invites the question of what it would do.
    can_delete=True, can_delete_extra=False,
)
