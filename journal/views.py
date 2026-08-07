"""Public JELTAN pages, the author's submission area, and file access control."""

import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import emails
from .forms import RevisionForm, SubmissionAuthorFormSet, SubmissionForm
from .models import (
    Article,
    EditorialBoardMember,
    Issue,
    JournalRole,
    JournalSettings,
    ReviewAssignment,
    Section,
    Submission,
    SubmissionFile,
)

logger = logging.getLogger(__name__)


def journal_context(**extra):
    """Context every JELTAN page needs."""
    context = {'journal': JournalSettings.load()}
    context.update(extra)
    return context


# ---------------------------------------------------------------- public

def home(request):
    """The journal front page: current issue and the most recent articles."""
    current_issue = Issue.objects.filter(is_published=True).first()
    recent_articles = (
        Article.objects.filter(is_published=True)
        .select_related('issue', 'section')
        .prefetch_related('authors')
        .order_by('-published_at')[:6]
    )
    return render(request, 'journal/home.html', journal_context(
        current_issue=current_issue,
        current_issue_articles=current_issue.public_articles.prefetch_related('authors') if current_issue else [],
        recent_articles=recent_articles,
        sections=Section.objects.filter(is_active=True),
        board_count=EditorialBoardMember.objects.filter(is_active=True).count(),
    ))


def about(request):
    return render(request, 'journal/about.html', journal_context())


def editorial_board(request):
    return render(request, 'journal/editorial_board.html', journal_context(
        board=EditorialBoardMember.objects.filter(is_active=True),
    ))


def guidelines(request):
    return render(request, 'journal/guidelines.html', journal_context(
        sections=Section.objects.filter(is_active=True),
    ))


def policies(request):
    """Peer review, publication ethics, open access and copyright in one place."""
    return render(request, 'journal/policies.html', journal_context())


def issue_list(request):
    issues = Issue.objects.filter(is_published=True).prefetch_related('articles')
    return render(request, 'journal/issue_list.html', journal_context(issues=issues))


def issue_detail(request, slug):
    issue = get_object_or_404(Issue, slug=slug, is_published=True)
    articles = issue.public_articles.select_related('section').prefetch_related('authors')
    return render(request, 'journal/issue_detail.html', journal_context(
        issue=issue, articles=articles,
    ))


def article_detail(request, slug):
    article = get_object_or_404(
        Article.objects.select_related('issue', 'section').prefetch_related('authors'),
        slug=slug,
        is_published=True,
    )
    # Counted with an UPDATE rather than a save() so two readers at once cannot
    # each write back the same stale number.
    Article.objects.filter(pk=article.pk).update(view_count=article.view_count + 1)
    return render(request, 'journal/article_detail.html', journal_context(article=article))


def article_pdf(request, slug):
    """Serve a published article's PDF and count the download."""
    article = get_object_or_404(Article, slug=slug, is_published=True)
    if not article.pdf:
        raise Http404('This article has no PDF.')
    Article.objects.filter(pk=article.pk).update(download_count=article.download_count + 1)
    return FileResponse(
        article.pdf.open('rb'),
        as_attachment=True,
        filename=f'{article.slug}.pdf',
    )


def search(request):
    """Search published articles by title, abstract, keywords or author."""
    query = (request.GET.get('q') or '').strip()
    articles = Article.objects.filter(is_published=True).select_related('issue').prefetch_related('authors')

    if query:
        articles = articles.filter(
            Q(title__icontains=query)
            | Q(abstract__icontains=query)
            | Q(keywords__icontains=query)
            | Q(authors__first_name__icontains=query)
            | Q(authors__last_name__icontains=query)
        ).distinct()

    page = Paginator(articles.order_by('-published_at'), 10).get_page(request.GET.get('page'))
    return render(request, 'journal/search.html', journal_context(
        query=query, page_obj=page, result_count=articles.count() if query else None,
    ))


# ---------------------------------------------------------------- author

@login_required
def submit(request):
    """The submission form.

    Everything is written in one transaction: a manuscript recorded without its
    authors or its files is worse than a submission that failed outright, because
    an editor would have to work out what is missing.
    """
    journal = JournalSettings.load()
    if not journal.is_accepting_submissions:
        return render(request, 'journal/submissions_closed.html', journal_context())

    form = SubmissionForm(request.POST or None, request.FILES or None)
    formset = SubmissionAuthorFormSet(request.POST or None, prefix='authors')

    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            submission = form.save(commit=False)
            submission.submitter = request.user
            submission.save()

            authors = _save_authors(formset, submission, request.user)
            _store_upload(submission, form.cleaned_data['anonymised_manuscript'],
                          SubmissionFile.ANONYMISED_MANUSCRIPT, request.user)
            _store_upload(submission, form.cleaned_data['title_page'],
                          SubmissionFile.TITLE_PAGE, request.user)
            if form.cleaned_data.get('supplementary_file'):
                _store_upload(submission, form.cleaned_data['supplementary_file'],
                              SubmissionFile.SUPPLEMENTARY, request.user)

            submission.log('Manuscript submitted', actor=request.user)

        emails.send_submission_received(submission, request)
        emails.send_editors_new_submission(submission, request)

        messages.success(
            request,
            f'Your manuscript has been submitted. Its reference is {submission.manuscript_id} — '
            f'we have emailed you a confirmation.',
        )
        return redirect('journal:submission_detail', pk=submission.pk)

    return render(request, 'journal/submit.html', journal_context(form=form, formset=formset))


def _save_authors(formset, submission, user):
    """Attach the author list, guaranteeing exactly one corresponding author.

    Nobody to write to is a real failure mode — every decision email is addressed
    to the corresponding author — so if the form did not mark one, the first
    author becomes it.
    """
    formset.instance = submission
    authors = formset.save(commit=False)
    for index, author in enumerate(authors):
        author.submission = submission
        author.order = index
        author.save()
    for deleted in formset.deleted_objects:
        deleted.delete()

    saved = list(submission.authors.all())
    if saved and not any(author.is_corresponding for author in saved):
        first = saved[0]
        first.is_corresponding = True
        first.save(update_fields=['is_corresponding'])
    return saved


def _store_upload(submission, uploaded, kind, user, round_number=None):
    return SubmissionFile.objects.create(
        submission=submission,
        kind=kind,
        file=uploaded,
        round=submission.current_round if round_number is None else round_number,
        uploaded_by=user,
    )


@login_required
def my_submissions(request):
    submissions = (
        Submission.objects.filter(submitter=request.user)
        .select_related('section')
        .prefetch_related('authors')
    )
    return render(request, 'journal/my_submissions.html', journal_context(submissions=submissions))


@login_required
def submission_detail(request, pk):
    """The author's view of one manuscript: status, history, decisions, reviews.

    Reviewer identities and confidential comments are never in this context —
    only what the editor chose to share.
    """
    submission = get_object_or_404(
        Submission.objects.prefetch_related('authors', 'files', 'decisions'), pk=pk,
    )
    if submission.submitter != request.user and not JournalRole.is_editor(request.user):
        raise Http404('No such submission.')

    shared_reviews = []
    for decision in submission.decisions.filter(share_reviews_with_author=True):
        shared_reviews += list(
            submission.review_assignments.filter(
                round=decision.round, status=ReviewAssignment.SUBMITTED,
            )
        )

    return render(request, 'journal/submission_detail.html', journal_context(
        submission=submission,
        events=submission.events.filter(is_public=True).select_related('actor'),
        decisions=submission.decisions.select_related('editor'),
        shared_reviews=shared_reviews,
        can_revise=submission.awaiting_author,
    ))


@login_required
def upload_revision(request, pk):
    """Author uploads the next round of a manuscript."""
    submission = get_object_or_404(Submission, pk=pk, submitter=request.user)
    if not submission.awaiting_author:
        messages.error(request, 'This manuscript is not awaiting a revision.')
        return redirect('journal:submission_detail', pk=submission.pk)

    form = RevisionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # The round advances first so the new files are stamped with it and
            # the previous round stays intact and readable.
            submission.current_round += 1
            submission.status = Submission.RESUBMITTED
            submission.save(update_fields=['current_round', 'status', 'updated_at'])

            _store_upload(submission, form.cleaned_data['revised_manuscript'],
                          SubmissionFile.ANONYMISED_MANUSCRIPT, request.user)
            _store_upload(submission, form.cleaned_data['response_to_reviewers'],
                          SubmissionFile.RESPONSE_TO_REVIEWERS, request.user)
            if form.cleaned_data.get('revised_title_page'):
                _store_upload(submission, form.cleaned_data['revised_title_page'],
                              SubmissionFile.TITLE_PAGE, request.user)

            submission.log(
                f'Revision submitted (round {submission.current_round})',
                actor=request.user,
                note=form.cleaned_data.get('note_to_editor', ''),
            )

        emails.send_editors_revision_received(submission, request)
        messages.success(request, 'Your revision has been submitted and the editor notified.')
        return redirect('journal:submission_detail', pk=submission.pk)

    return render(request, 'journal/upload_revision.html', journal_context(
        submission=submission, form=form,
    ))


@login_required
def withdraw_submission(request, pk):
    submission = get_object_or_404(Submission, pk=pk, submitter=request.user)
    if request.method != 'POST':
        return redirect('journal:submission_detail', pk=submission.pk)
    if not submission.is_open:
        messages.error(request, 'This manuscript is already closed.')
        return redirect('journal:submission_detail', pk=submission.pk)

    submission.status = Submission.WITHDRAWN
    submission.save(update_fields=['status', 'updated_at'])
    submission.log('Withdrawn by the author', actor=request.user)
    # Reviewers should not keep working on a paper that has been pulled.
    for assignment in submission.review_assignments.filter(
        status__in=[ReviewAssignment.INVITED, ReviewAssignment.ACCEPTED]
    ):
        assignment.cancel()

    messages.success(request, 'Your manuscript has been withdrawn.')
    return redirect('journal:my_submissions')


# ------------------------------------------------- article processing charge

@login_required
def pay_apc(request, pk):
    """Start payment of the article processing charge through Paystack."""
    submission = get_object_or_404(Submission, pk=pk, submitter=request.user)
    journal = JournalSettings.load()

    if not submission.apc_is_due:
        messages.info(request, 'There is nothing to pay on this manuscript.')
        return redirect('journal:submission_detail', pk=submission.pk)

    reference = f'JELTAN-APC-{submission.pk}-{timezone.now().strftime("%Y%m%d%H%M%S")}'
    payload = {
        'email': submission.notification_email,
        'amount': int(submission.apc_amount * 100),  # kobo
        'reference': reference,
        'callback_url': request.build_absolute_uri(reverse('journal:apc_success')),
        'currency': journal.apc_currency,
        'metadata': {
            'submission_id': submission.pk,
            'manuscript_id': submission.manuscript_id,
            'purpose': 'JELTAN article processing charge',
        },
    }

    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            headers={
                'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        submission.apc_reference = reference
        submission.save(update_fields=['apc_reference', 'updated_at'])
        return redirect(data['data']['authorization_url'])

    except (requests.exceptions.RequestException, KeyError, ValueError) as e:
        logger.error(f'JELTAN APC initialisation failed for {submission.manuscript_id}: {e}')
        messages.error(
            request,
            'We could not start the payment just now. Please try again in a few minutes.',
        )
        return redirect('journal:submission_detail', pk=submission.pk)


@csrf_exempt
def apc_success(request):
    """Verify an article processing charge with Paystack and move the paper on."""
    reference = request.GET.get('reference') or request.POST.get('reference')
    submission = Submission.objects.filter(apc_reference=reference).first()

    if not reference or not submission:
        messages.error(request, 'That payment reference was not recognised.')
        return redirect('journal:my_submissions')

    try:
        response = requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
            timeout=30,
        )
        response.raise_for_status()
        verification = response.json()['data']
    except (requests.exceptions.RequestException, KeyError, ValueError) as e:
        logger.error(f'JELTAN APC verification failed for {reference}: {e}')
        messages.error(request, 'We could not verify the payment. Please contact the editorial office.')
        return redirect('journal:submission_detail', pk=submission.pk)

    if verification.get('status') != 'success':
        messages.error(request, 'The payment was not completed.')
        return redirect('journal:submission_detail', pk=submission.pk)

    # Paystack adds its fee on top, so an overpayment is normal; only a short
    # payment is a problem.
    if verification.get('amount', 0) < int(submission.apc_amount * 100):
        messages.error(request, 'The amount received is short of the article processing charge.')
        return redirect('journal:submission_detail', pk=submission.pk)

    if submission.apc_status != Submission.APC_PAID:
        submission.mark_apc_paid(reference)
        submission.log('Article processing charge paid')
        emails.send_apc_receipt(submission, request)

    messages.success(request, 'Payment received — your paper is now in production. A receipt is on its way.')
    return redirect('journal:submission_detail', pk=submission.pk)


# ------------------------------------------------------------ file access

def submission_file(request, pk):
    """Hand out a manuscript file, but only to someone entitled to it.

    Manuscript files live outside MEDIA_ROOT precisely so that this check cannot
    be walked around (see journal/storage.py). The rules:

    * the submitting author and any editor may read anything;
    * a reviewer with a live assignment may read the anonymised manuscript and
      the supplementary material, and never the title page.
    """
    submission_file_row = get_object_or_404(SubmissionFile.objects.select_related('submission'), pk=pk)
    submission = submission_file_row.submission

    if not _may_read_file(request, submission, submission_file_row):
        raise Http404('No such file.')

    try:
        handle = submission_file_row.file.open('rb')
    except FileNotFoundError:
        raise Http404('That file is no longer on the server.')

    return FileResponse(
        handle,
        as_attachment=True,
        filename=submission_file_row.original_name or 'manuscript',
    )


def _may_read_file(request, submission, file_row):
    user = request.user
    if user.is_authenticated:
        if user == submission.submitter or JournalRole.is_editor(user):
            return True

    # Reviewers arrive with the token from their invitation email.
    token = request.GET.get('token') or request.session.get('journal_review_token')
    if token:
        assignment = ReviewAssignment.objects.filter(
            token=token, submission=submission,
        ).first()
        if assignment and assignment.status in [ReviewAssignment.ACCEPTED, ReviewAssignment.SUBMITTED]:
            return file_row.is_reviewer_visible
    return False
