"""Forms for the JELTAN editorial workflow."""

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import (
    Article,
    ArticleAuthor,
    EditorialDecision,
    Issue,
    ReviewAssignment,
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

        # Desk decisions and post-review decisions are different moments; offering
        # all six choices at both invites the wrong one to be clicked.
        if submission and submission.status == Submission.SUBMITTED:
            allowed = [EditorialDecision.SEND_FOR_REVIEW, EditorialDecision.DESK_REJECT]
        else:
            allowed = [
                EditorialDecision.ACCEPT,
                EditorialDecision.MINOR_REVISION,
                EditorialDecision.MAJOR_REVISION,
                EditorialDecision.REJECT,
                EditorialDecision.SEND_FOR_REVIEW,
            ]
        self.fields['decision'].choices = [
            (value, label) for value, label in EditorialDecision.DECISION_CHOICES if value in allowed
        ]


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


class ArticleAuthorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ArticleAuthor
        fields = ['first_name', 'last_name', 'affiliation', 'country', 'email', 'orcid']


ArticleAuthorFormSet = inlineformset_factory(
    Article, ArticleAuthor, form=ArticleAuthorForm, extra=1, min_num=1, validate_min=True, can_delete=True,
)
