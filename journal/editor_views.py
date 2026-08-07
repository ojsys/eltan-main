"""The editorial office: the queue, peer review management, decisions, publishing."""

import logging
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import emails
from .forms import (
    ArticleAuthorFormSet,
    DecisionForm,
    IssueForm,
    PublishArticleForm,
    ReviewerInviteForm,
)
from .models import (
    Article,
    ArticleAuthor,
    EditorialDecision,
    Issue,
    JournalRole,
    JournalSettings,
    ReviewAssignment,
    Submission,
)
from .views import journal_context

logger = logging.getLogger(__name__)


def editor_required(view):
    """Only journal editors get in — not every member of website staff."""
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not JournalRole.is_editor(request.user):
            raise Http404('Not found.')
        return view(request, *args, **kwargs)
    return wrapper


@editor_required
def dashboard(request):
    """The editorial queue, ordered by what is actually waiting on someone."""
    submissions = Submission.objects.select_related('section', 'handling_editor').prefetch_related('authors')

    status_filter = request.GET.get('status', 'open')
    if status_filter == 'open':
        queryset = submissions.in_progress()
    elif status_filter == 'mine':
        queryset = submissions.in_progress().filter(handling_editor=request.user)
    elif status_filter == 'all':
        queryset = submissions
    else:
        queryset = submissions.filter(status=status_filter)

    counts = {
        'awaiting_desk_check': submissions.needing_editor_attention().count(),
        'under_review': submissions.filter(status=Submission.UNDER_REVIEW).count(),
        'awaiting_revision': submissions.filter(
            status__in=Submission.AUTHOR_ACTION_STATUSES
        ).count(),
        'accepted': submissions.filter(
            status__in=[Submission.ACCEPTED, Submission.IN_PRODUCTION]
        ).count(),
        'overdue_reviews': ReviewAssignment.objects.filter(
            status=ReviewAssignment.ACCEPTED, due_date__lt=timezone.now().date(),
        ).count(),
    }

    return render(request, 'journal/editor/dashboard.html', journal_context(
        submissions=queryset.annotate(
            review_count=Count('review_assignments', filter=Q(
                review_assignments__status=ReviewAssignment.SUBMITTED
            )),
        )[:100],
        counts=counts,
        status_filter=status_filter,
        status_choices=Submission.STATUS_CHOICES,
    ))


@editor_required
def submission(request, pk):
    """Everything an editor needs on one manuscript, including author identities."""
    submission_row = get_object_or_404(
        Submission.objects.select_related('section', 'handling_editor')
        .prefetch_related('authors', 'files', 'review_assignments', 'decisions'),
        pk=pk,
    )

    return render(request, 'journal/editor/submission.html', journal_context(
        submission=submission_row,
        files_by_round=_files_by_round(submission_row),
        assignments=submission_row.review_assignments.all(),
        decisions=submission_row.decisions.select_related('editor'),
        events=submission_row.events.select_related('actor'),
        decision_form=DecisionForm(submission=submission_row),
        invite_form=ReviewerInviteForm(submission=submission_row),
        editors=JournalRole.objects.filter(is_active=True).select_related('user'),
        can_publish=submission_row.status in [Submission.IN_PRODUCTION, Submission.ACCEPTED],
        article=getattr(submission_row, 'article', None),
    ))


def _files_by_round(submission_row):
    """Files grouped by round, newest round first — the shape the page reads in."""
    grouped = {}
    for file_row in submission_row.files.all():
        grouped.setdefault(file_row.round, []).append(file_row)
    return sorted(grouped.items(), reverse=True)


@editor_required
def assign_editor(request, pk):
    """Hand a manuscript to a handling editor."""
    submission_row = get_object_or_404(Submission, pk=pk)
    if request.method != 'POST':
        return redirect('journal:editor_submission', pk=pk)

    editor_id = request.POST.get('editor')
    if not editor_id:
        submission_row.handling_editor = None
        submission_row.save(update_fields=['handling_editor', 'updated_at'])
        messages.success(request, 'Handling editor cleared.')
        return redirect('journal:editor_submission', pk=pk)

    role = get_object_or_404(JournalRole, pk=editor_id, is_active=True)
    submission_row.handling_editor = role.user
    submission_row.save(update_fields=['handling_editor', 'updated_at'])
    submission_row.log(
        f'Assigned to {role.user.get_full_name() or role.user.email}',
        actor=request.user,
        is_public=False,
    )
    messages.success(request, f'Assigned to {role.user.get_full_name() or role.user.email}.')
    return redirect('journal:editor_submission', pk=pk)


@editor_required
def invite_reviewer(request, pk):
    """Invite a reviewer for the current round."""
    submission_row = get_object_or_404(Submission, pk=pk)
    form = ReviewerInviteForm(request.POST or None, submission=submission_row)

    if request.method == 'POST' and form.is_valid():
        assignment = form.save(commit=False)
        assignment.submission = submission_row
        assignment.round = submission_row.current_round
        assignment.invited_by = request.user
        # A reviewer who already has an account gets their history linked.
        assignment.reviewer_user = _find_user(assignment.reviewer_email)
        assignment.save()

        ok, error = emails.send_review_invitation(
            assignment, form.cleaned_data.get('personal_message', ''), request,
        )
        submission_row.log(
            f'Review invitation sent to {assignment.reviewer_name}',
            actor=request.user,
            is_public=False,
        )
        # Moving to 'under review' on the first invitation saves the editor a
        # second click and keeps the queue honest about where the paper is.
        if submission_row.status in [Submission.SUBMITTED, Submission.RESUBMITTED]:
            submission_row.status = Submission.UNDER_REVIEW
            submission_row.save(update_fields=['status', 'updated_at'])

        if ok:
            messages.success(request, f'Invitation sent to {assignment.reviewer_email}.')
        else:
            messages.warning(
                request,
                f'The reviewer was added, but the invitation email failed: {error}. '
                f'You can resend it from the manuscript page.',
            )
        return redirect('journal:editor_submission', pk=pk)

    return render(request, 'journal/editor/invite_reviewer.html', journal_context(
        submission=submission_row, form=form,
    ))


def _find_user(email):
    from account.models import CustomUser
    return CustomUser.objects.filter(email__iexact=email).first()


@editor_required
def resend_invitation(request, pk):
    assignment = get_object_or_404(ReviewAssignment, pk=pk)
    if request.method != 'POST':
        return redirect('journal:editor_submission', pk=assignment.submission_id)

    ok, error = emails.send_review_invitation(assignment, '', request)
    if ok:
        messages.success(request, f'Invitation resent to {assignment.reviewer_email}.')
    else:
        messages.error(request, f'The email failed: {error}')
    return redirect('journal:editor_submission', pk=assignment.submission_id)


@editor_required
def remind_reviewer(request, pk):
    assignment = get_object_or_404(ReviewAssignment, pk=pk)
    if request.method != 'POST':
        return redirect('journal:editor_submission', pk=assignment.submission_id)

    ok, error = emails.send_review_reminder(assignment, request)
    if ok:
        assignment.reminder_sent_at = timezone.now()
        assignment.save(update_fields=['reminder_sent_at'])
        messages.success(request, f'Reminder sent to {assignment.reviewer_email}.')
    else:
        messages.error(request, f'The reminder failed: {error}')
    return redirect('journal:editor_submission', pk=assignment.submission_id)


@editor_required
def cancel_review(request, pk):
    assignment = get_object_or_404(ReviewAssignment, pk=pk)
    if request.method != 'POST':
        return redirect('journal:editor_submission', pk=assignment.submission_id)

    assignment.cancel()
    assignment.submission.log(
        f'Review request to {assignment.reviewer_name} cancelled',
        actor=request.user,
        is_public=False,
    )
    messages.success(request, 'Review request cancelled — their link no longer works.')
    return redirect('journal:editor_submission', pk=assignment.submission_id)


@editor_required
def record_decision(request, pk):
    """Record an editorial decision and send the letter.

    The decision drives the manuscript's status through
    ``EditorialDecision.RESULTING_STATUS``, so a decision can never be recorded
    without the paper actually moving.
    """
    submission_row = get_object_or_404(Submission, pk=pk)
    form = DecisionForm(request.POST or None, submission=submission_row)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            decision = form.save(commit=False)
            decision.submission = submission_row
            decision.round = submission_row.current_round
            decision.editor = request.user
            decision.save()

            submission_row.status = EditorialDecision.RESULTING_STATUS[decision.decision]
            submission_row.decided_at = timezone.now()
            submission_row.save(update_fields=['status', 'decided_at', 'updated_at'])
            submission_row.log(
                f'Editorial decision: {decision.get_decision_display()}',
                actor=request.user,
            )

            if decision.decision == EditorialDecision.ACCEPT:
                # Acceptance raises the article processing charge, or clears it
                # straight to production when the journal has waived the fee.
                submission_row.start_apc()

        reviews = list(
            submission_row.review_assignments.filter(
                round=decision.round, status=ReviewAssignment.SUBMITTED,
            )
        )
        if decision.decision == EditorialDecision.ACCEPT and submission_row.apc_is_due:
            emails.send_acceptance_with_apc(submission_row, request)
        elif decision.decision != EditorialDecision.SEND_FOR_REVIEW:
            emails.send_decision(submission_row, decision, reviews, request)

        messages.success(request, f'Decision recorded: {decision.get_decision_display()}.')
        return redirect('journal:editor_submission', pk=pk)

    messages.error(request, 'Please correct the decision form.')
    return render(request, 'journal/editor/submission.html', journal_context(
        submission=submission_row,
        files_by_round=_files_by_round(submission_row),
        assignments=submission_row.review_assignments.all(),
        decisions=submission_row.decisions.select_related('editor'),
        events=submission_row.events.select_related('actor'),
        decision_form=form,
        invite_form=ReviewerInviteForm(submission=submission_row),
        editors=JournalRole.objects.filter(is_active=True).select_related('user'),
        can_publish=submission_row.status in [Submission.IN_PRODUCTION, Submission.ACCEPTED],
        article=getattr(submission_row, 'article', None),
    ))


@editor_required
def waive_apc(request, pk):
    """Waive the charge for one paper — hardship, invited papers, editorials."""
    submission_row = get_object_or_404(Submission, pk=pk)
    if request.method != 'POST':
        return redirect('journal:editor_submission', pk=pk)

    submission_row.apc_status = Submission.APC_WAIVED
    if submission_row.status == Submission.ACCEPTED:
        submission_row.status = Submission.IN_PRODUCTION
    submission_row.save(update_fields=['apc_status', 'status', 'updated_at'])
    submission_row.log('Article processing charge waived', actor=request.user)
    messages.success(request, 'The charge has been waived and the paper moved to production.')
    return redirect('journal:editor_submission', pk=pk)


@editor_required
def publish(request, pk):
    """Turn an accepted manuscript into a published article.

    The form is pre-filled from the manuscript — title, abstract, keywords and
    the author list — because retyping metadata at the last step is where
    published records pick up errors.
    """
    submission_row = get_object_or_404(Submission, pk=pk)
    article = getattr(submission_row, 'article', None)

    if article is None:
        article = Article(
            submission=submission_row,
            section=submission_row.section,
            title=submission_row.title,
            abstract=submission_row.abstract,
            keywords=submission_row.keywords,
        )

    form = PublishArticleForm(request.POST or None, request.FILES or None, instance=article)
    formset = ArticleAuthorFormSet(
        request.POST or None,
        instance=article if article.pk else None,
        prefix='authors',
        initial=[] if article.pk else [
            {
                'first_name': author.first_name,
                'last_name': author.last_name,
                'affiliation': author.affiliation,
                'country': author.country,
                'email': author.email,
                'orcid': author.orcid,
            }
            for author in submission_row.authors.all()
        ],
    )
    if not article.pk:
        formset.extra = max(submission_row.authors.count(), 1)

    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            published_article = form.save(commit=False)
            published_article.submission = submission_row
            published_article.section = submission_row.section
            published_article.save()

            formset.instance = published_article
            for index, author in enumerate(formset.save(commit=False)):
                author.article = published_article
                author.order = index
                author.save()
            for deleted in formset.deleted_objects:
                deleted.delete()

            if published_article.is_published:
                submission_row.status = Submission.PUBLISHED
                submission_row.save(update_fields=['status', 'updated_at'])
                submission_row.log('Published', actor=request.user)

        if published_article.is_published:
            emails.send_published(published_article, request)
            messages.success(request, 'The article is published and the author has been told.')
        else:
            messages.success(request, 'Saved. The article is not public until you tick "Publish now".')
        return redirect('journal:editor_submission', pk=pk)

    return render(request, 'journal/editor/publish.html', journal_context(
        submission=submission_row, form=form, formset=formset, article=article,
    ))


# ------------------------------------------------------------------ issues

@editor_required
def issue_list(request):
    return render(request, 'journal/editor/issues.html', journal_context(
        issues=Issue.objects.annotate(article_count=Count('articles')),
        form=IssueForm(),
    ))


@editor_required
def issue_create(request):
    form = IssueForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        issue = form.save()
        messages.success(request, f'{issue.label} created.')
        return redirect('journal:editor_issues')
    return render(request, 'journal/editor/issue_form.html', journal_context(form=form))


@editor_required
def issue_edit(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    form = IssueForm(request.POST or None, request.FILES or None, instance=issue)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{issue.label} updated.')
        return redirect('journal:editor_issues')
    return render(request, 'journal/editor/issue_form.html', journal_context(
        form=form, issue=issue, articles=issue.articles.all(),
    ))
