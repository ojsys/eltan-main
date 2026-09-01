"""The editorial office: the queue, peer review management, decisions, publishing."""

import logging
import uuid
from datetime import datetime, time
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from . import emails, ingest, typeset
from .forms import (
    ArticleAuthorFormSet,
    ArticleImportForm,
    CopyeditForm,
    DecisionForm,
    DirectArticleForm,
    DocumentUploadForm,
    ImportedArticleForm,
    ImportedArticleFormSet,
    IssueForm,
    ProofForm,
    PublishArticleForm,
    ReviewerInviteForm,
    ScreeningForm,
)
from .models import (
    Article,
    ArticleAuthor,
    EditorialDecision,
    Issue,
    JournalRole,
    JournalSettings,
    Proof,
    ReviewAssignment,
    Section,
    Submission,
    SubmissionEvent,
    SubmissionFile,
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


def chief_required(view):
    """Editors-in-chief, managing editors and site administrators only.

    Publishing an article without review, and editing the published record after
    the fact, are the two things in this system that no peer reviewer and no
    author ever checks. They belong to the people who answer for the journal.
    """
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not JournalRole.is_chief(request.user):
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
        'awaiting_screening': submissions.filter(status=Submission.SUBMITTED).count(),
        'awaiting_decision': submissions.filter(
            status__in=[Submission.EDITORIAL_SCREENING, Submission.RESUBMITTED]
        ).count(),
        'under_review': submissions.filter(status=Submission.UNDER_REVIEW).count(),
        'awaiting_revision': submissions.filter(
            status__in=Submission.AUTHOR_ACTION_STATUSES + [Submission.RETURNED]
        ).count(),
        'in_production': submissions.filter(
            status__in=Submission.PRODUCTION_STATUSES + [Submission.ACCEPTED]
        ).count(),
        'overdue_reviews': ReviewAssignment.objects.filter(
            status=ReviewAssignment.ACCEPTED, due_date__lt=timezone.now().date(),
        ).count(),
    }

    return render(request, 'journal/editor/dashboard.html', journal_context(
        nav='editor',
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

    return render(
        request, 'journal/editor/submission.html',
        _submission_context(submission_row),
    )


def _submission_context(submission_row, decision_form=None):
    """The editor's view of one manuscript.

    One place, because the decision form re-renders this page when it fails
    validation and two copies of the context drift apart.
    """
    return journal_context(
        nav='editor',
        submission=submission_row,
        files_by_round=_files_by_round(submission_row),
        assignments=submission_row.review_assignments.all(),
        decisions=submission_row.decisions.select_related('editor'),
        events=submission_row.events.select_related('actor'),
        decision_form=decision_form or DecisionForm(submission=submission_row),
        invite_form=ReviewerInviteForm(submission=submission_row),
        editors=JournalRole.objects.filter(is_active=True).select_related('user'),
        screening_reports=submission_row.screening_reports.select_related('screened_by'),
        needs_screening=submission_row.status == Submission.SUBMITTED,
        is_screened=submission_row.is_screened,
        proofs=submission_row.proofs.all(),
        latest_proof=submission_row.latest_proof,
        in_production=submission_row.status in Submission.PRODUCTION_STATUSES,
        can_publish=submission_row.status in (
            Submission.PRODUCTION_STATUSES + [Submission.ACCEPTED]
        ),
        article=getattr(submission_row, 'article', None),
    )


def _files_by_round(submission_row):
    """Files grouped by round, newest round first — the shape the page reads in."""
    grouped = {}
    for file_row in submission_row.files.all():
        grouped.setdefault(file_row.round, []).append(file_row)
    return sorted(grouped.items(), reverse=True)


@editor_required
def screen(request, pk):
    """Administrative screening: the technical check before an editor sees it.

    Passing sends the manuscript on to editorial screening; failing returns it to
    the author for correction, which is not a rejection and keeps the same
    manuscript record.
    """
    submission_row = get_object_or_404(Submission, pk=pk)
    form = ScreeningForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        passed = form.cleaned_data['outcome'] == 'pass'
        with transaction.atomic():
            report = form.save(commit=False)
            report.submission = submission_row
            report.round = submission_row.current_round
            report.passed = passed
            report.screened_by = request.user
            report.save()

            submission_row.status = (
                Submission.EDITORIAL_SCREENING if passed else Submission.RETURNED
            )
            submission_row.save(update_fields=['status', 'updated_at'])
            submission_row.log(
                'Passed administrative screening' if passed
                else 'Returned to the author for correction',
                actor=request.user,
                note=report.notes_to_author if not passed else '',
            )

        if passed:
            emails.send_screening_passed(submission_row, request)
            messages.success(request, 'Screening passed — the manuscript is ready for an editorial decision.')
        else:
            emails.send_returned_to_author(submission_row, report, request)
            messages.success(request, 'Returned to the author with your notes.')
        return redirect('journal:editor_submission', pk=pk)

    return render(request, 'journal/editor/screen.html', journal_context(
        submission=submission_row,
        form=form,
        files=submission_row.files_for_round(),
        previous=submission_row.screening_reports.all(),
    ))


@editor_required
def upload_copyedit(request, pk):
    """Store the copyedited manuscript against the paper."""
    submission_row = get_object_or_404(Submission, pk=pk)
    form = CopyeditForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        SubmissionFile.objects.create(
            submission=submission_row,
            kind=SubmissionFile.PRODUCTION,
            file=form.cleaned_data['copyedited_file'],
            round=submission_row.current_round,
            uploaded_by=request.user,
        )
        submission_row.log(
            'Copyedited manuscript uploaded',
            actor=request.user,
            note=form.cleaned_data.get('note', ''),
        )
        messages.success(request, 'Copyedited manuscript saved. You can now send a proof to the author.')
        return redirect('journal:editor_submission', pk=pk)

    return render(request, 'journal/editor/copyedit.html', journal_context(
        submission=submission_row, form=form,
    ))


@editor_required
def send_proof(request, pk):
    """Send a typeset proof to the author for approval."""
    submission_row = get_object_or_404(Submission, pk=pk)
    form = ProofForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Any earlier proof is superseded — only one is ever live, so an
            # author cannot approve a version that has been replaced.
            submission_row.proofs.filter(status=Proof.SENT).update(status=Proof.SUPERSEDED)

            proof = form.save(commit=False)
            proof.submission = submission_row
            proof.version = submission_row.proofs.count() + 1
            proof.sent_by = request.user
            proof.save()

            submission_row.status = Submission.PROOF_REVIEW
            submission_row.save(update_fields=['status', 'updated_at'])
            submission_row.log(f'Proof v{proof.version} sent to the author', actor=request.user)

        ok, error = emails.send_proof_to_author(proof, request)
        if ok:
            messages.success(request, 'The proof has been sent to the author for approval.')
        else:
            messages.warning(
                request,
                f'The proof was saved, but the email failed: {error}. The author has not been told.',
            )
        return redirect('journal:editor_submission', pk=pk)

    return render(request, 'journal/editor/proof.html', journal_context(
        submission=submission_row, form=form, proofs=submission_row.proofs.all(),
    ))


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

    # The screening gate. Administrative screening is where a manuscript's
    # anonymity is verified, so inviting a reviewer before it has passed would
    # put an un-checked paper in front of the person judging it.
    if not submission_row.is_screened:
        messages.error(
            request,
            'This manuscript has not passed administrative screening for the current round. '
            'Screen it first — that check is what confirms it is properly anonymised.',
        )
        return redirect('journal:editor_submission', pk=pk)

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
        if submission_row.status in [
            Submission.SUBMITTED, Submission.EDITORIAL_SCREENING, Submission.RESUBMITTED,
        ]:
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
            elif decision.decision == EditorialDecision.WITHDRAW:
                # Reviewers must not keep working on a paper that has been pulled.
                for assignment in submission_row.review_assignments.filter(
                    status__in=[ReviewAssignment.INVITED, ReviewAssignment.ACCEPTED]
                ):
                    assignment.cancel()

        reviews = list(
            submission_row.review_assignments.filter(
                round=decision.round, status=ReviewAssignment.SUBMITTED,
            )
        )
        # Sending a paper for review is an internal move — the author is told
        # when the outcome arrives, not every time it changes desk.
        internal_only = [
            EditorialDecision.SEND_FOR_REVIEW, EditorialDecision.ANOTHER_ROUND,
        ]
        if decision.decision == EditorialDecision.ACCEPT and submission_row.apc_is_due:
            emails.send_acceptance_with_apc(submission_row, request)
        elif decision.decision not in internal_only:
            emails.send_decision(submission_row, decision, reviews, request)

        messages.success(request, f'Decision recorded: {decision.get_decision_display()}.')
        return redirect('journal:editor_submission', pk=pk)

    messages.error(request, 'Please correct the decision form.')
    return render(
        request, 'journal/editor/submission.html',
        _submission_context(submission_row, decision_form=form),
    )


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


# ------------------------------------------------------------------ portal

def _median(values):
    """Median of a list of numbers, or None when there is nothing to average.

    The mean is the wrong summary for editorial turnaround: one manuscript that
    sat for two years drags it somewhere no paper actually went.
    """
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _action_lanes(submissions):
    """What the editorial office owes someone, in the order it should be cleared.

    Each lane is work that stops if nobody picks it up. Things waiting on an
    author or a reviewer are not lanes — chasing those is a different job, and
    mixing them in is how a queue stops meaning anything.
    """
    today = timezone.now().date()

    overdue_review_ids = list(
        ReviewAssignment.objects.filter(
            status=ReviewAssignment.ACCEPTED, due_date__lt=today,
        ).values_list('submission_id', flat=True)
    )

    lanes = [
        {
            'key': 'screening',
            'title': 'Awaiting administrative screening',
            'blurb': 'Nothing may go to a reviewer until anonymity has been checked.',
            'tone': 'warn',
            'rows': submissions.filter(status=Submission.SUBMITTED),
        },
        {
            'key': 'decision',
            'title': 'Awaiting an editorial decision',
            'blurb': 'Screened or revised, and now waiting on an editor.',
            'tone': 'warn',
            'rows': submissions.filter(
                status__in=[Submission.EDITORIAL_SCREENING, Submission.RESUBMITTED]
            ),
        },
        {
            'key': 'unassigned',
            'title': 'No handling editor',
            'blurb': 'Open manuscripts nobody owns.',
            'tone': 'alert',
            'rows': submissions.in_progress().filter(handling_editor__isnull=True),
        },
        {
            'key': 'overdue',
            'title': 'Overdue reviews',
            'blurb': 'A reviewer accepted and the date has passed.',
            'tone': 'alert',
            'rows': submissions.filter(pk__in=overdue_review_ids),
        },
        {
            'key': 'apc',
            'title': 'Awaiting the article processing charge',
            'blurb': 'Accepted, but the charge is unpaid and production has not started.',
            'tone': 'info',
            'rows': submissions.filter(
                status=Submission.ACCEPTED, apc_status=Submission.APC_PENDING,
            ),
        },
        {
            'key': 'production',
            'title': 'In production',
            'blurb': 'Copyediting, proofs and papers ready to be published.',
            'tone': 'info',
            'rows': submissions.filter(status__in=Submission.PRODUCTION_STATUSES),
        },
    ]

    for lane in lanes:
        rows = list(lane['rows'][:25])
        lane['rows'] = rows
        lane['count'] = len(rows)
    return lanes


def _decision_statistics(decisions):
    """Headline numbers for the filtered decision log."""
    by_decision = []
    labels = dict(EditorialDecision.DECISION_CHOICES)
    counts = dict(
        decisions.values_list('decision').annotate(total=Count('id'))
    )
    total = sum(counts.values())
    for value, label in EditorialDecision.DECISION_CHOICES:
        if counts.get(value):
            by_decision.append({
                'label': label,
                'count': counts[value],
                'share': round(counts[value] * 100 / total) if total else 0,
            })

    # Acceptance rate is counted over decisions that settled a paper, so a
    # revision request is not read as a rejection while the paper is still live.
    accepted = counts.get(EditorialDecision.ACCEPT, 0)
    settled = accepted + sum(
        counts.get(value, 0) for value in EditorialDecision.CLOSING_DECISIONS
        if value != EditorialDecision.WITHDRAW
    )

    turnarounds = [
        (decision.decided_at.date() - decision.submission.submitted_at.date()).days
        for decision in decisions.select_related('submission')[:500]
        if decision.submission.submitted_at
    ]

    return {
        'total': total,
        'by_decision': by_decision,
        'labels': labels,
        'accepted': accepted,
        'settled': settled,
        'acceptance_rate': round(accepted * 100 / settled) if settled else None,
        'median_days': _median(turnarounds),
    }


@editor_required
def portal(request):
    """The editorial portal: every decision, and everything still owed one.

    The dashboard answers 'what is in the pipeline'. This answers the questions
    that span manuscripts — what has this journal decided, how fast, by whom,
    and what is stuck — which is what an editor-in-chief or an administrator is
    actually looking for, and what no per-manuscript page can show.
    """
    submissions = Submission.objects.select_related('section', 'handling_editor')

    decisions = EditorialDecision.objects.select_related(
        'submission', 'submission__section', 'editor',
    )

    filters = {
        'decision': request.GET.get('decision', ''),
        'section': request.GET.get('section', ''),
        'editor': request.GET.get('editor', ''),
        'q': request.GET.get('q', '').strip(),
    }
    if filters['decision']:
        decisions = decisions.filter(decision=filters['decision'])
    if filters['section']:
        decisions = decisions.filter(submission__section__slug=filters['section'])
    if filters['editor']:
        decisions = decisions.filter(editor_id=filters['editor'])
    if filters['q']:
        decisions = decisions.filter(
            Q(submission__manuscript_id__icontains=filters['q'])
            | Q(submission__title__icontains=filters['q'])
        )

    statistics = _decision_statistics(decisions)
    page = Paginator(decisions, 25).get_page(request.GET.get('page'))

    # The querystring minus `page`, so paging does not drop the filters.
    query = request.GET.copy()
    query.pop('page', None)

    return render(request, 'journal/editor/portal.html', journal_context(
        nav='portal',
        lanes=_action_lanes(submissions),
        decisions=page,
        page_obj=page,
        querystring=query.urlencode(),
        filters=filters,
        decision_choices=EditorialDecision.DECISION_CHOICES,
        sections=Section.objects.all(),
        editors=JournalRole.objects.filter(is_active=True).select_related('user'),
        statistics=statistics,
        events=SubmissionEvent.objects.select_related('submission', 'actor')
                                      .order_by('-created_at')[:30],
        issues=Issue.objects.all()[:8],
        my_role=JournalRole.describe(request.user),
        is_site_admin=JournalRole.is_site_admin(request.user),
        totals={
            'submissions': submissions.count(),
            'open': submissions.in_progress().count(),
            'published': Article.objects.filter(is_published=True).count(),
            'sections': Section.objects.filter(is_active=True).count(),
        },
    ))


# ------------------------------------------------------ articles loaded by hand

def _article_authors_formset(request, article, prefix='authors'):
    return ArticleAuthorFormSet(
        request.POST or None, prefix=prefix,
        instance=article if article.pk else None,
    )


def _save_article_authors(formset, article):
    """Save the byline, numbered by the order the forms appear on the page.

    ``formset.save(commit=False)`` hands back only the forms that changed, so
    numbering *those* would push a single edited author to position one and
    scramble a byline that nobody touched. The order has to come from the whole
    formset, every time.
    """
    formset.instance = article
    formset.save()

    position = 0
    for author_form in formset.forms:
        author = author_form.instance
        if author.pk is None or author_form in formset.deleted_forms:
            continue
        if author.order != position:
            author.order = position
            author.save(update_fields=['order'])
        position += 1


@chief_required
def article_list(request):
    """Everything in the published record, whatever route it took to get there."""
    articles = Article.objects.select_related('issue', 'section', 'added_by').prefetch_related('authors')

    view = request.GET.get('show', 'all')
    if view == 'published':
        articles = articles.filter(is_published=True)
    elif view == 'draft':
        articles = articles.filter(is_published=False)
    elif view == 'online_first':
        articles = articles.filter(is_published=True, issue__isnull=True)
    elif view == 'direct':
        articles = articles.filter(submission__isnull=True)

    search = request.GET.get('q', '').strip()
    if search:
        articles = articles.filter(
            Q(title__icontains=search) | Q(doi__icontains=search)
            | Q(authors__last_name__icontains=search)
        ).distinct()

    return render(request, 'journal/editor/articles.html', journal_context(
        nav='editor',
        articles=articles.order_by('-published_at', '-created_at')[:200],
        counts={
            'all': Article.objects.count(),
            'published': Article.objects.filter(is_published=True).count(),
            'draft': Article.objects.filter(is_published=False).count(),
            'direct': Article.objects.filter(submission__isnull=True).count(),
        },
        view=view,
        search=search,
    ))


@chief_required
def article_create(request):
    """Publish an article that has already been reviewed, without a manuscript.

    Papers reviewed elsewhere, invited pieces, and the back catalogue all arrive
    ready to typeset. Forcing them through the submission pipeline would mean
    inventing a review that never happened, so they are loaded here instead —
    and ``added_by`` records who did it, since nothing else in the record can.
    """
    article = Article()

    # Loading an issue is loading a run of articles, so the section and issue
    # of the last one carry over to the next.
    initial = {}
    for field in ('section', 'issue'):
        if request.GET.get(field):
            initial[field] = request.GET[field]

    form = DirectArticleForm(request.POST or None, request.FILES or None, initial=initial)
    formset = _article_authors_formset(request, article)

    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            saved.added_by = request.user
            saved.save()
            _save_article_authors(formset, saved)

        # After the byline is stored, never before: the galley prints the
        # authors, so typesetting first would set a paper with no names on it.
        typeset.typeset(saved)

        if saved.is_published and form.cleaned_data.get('notify_authors'):
            emails.send_published(saved, request)
        messages.success(
            request,
            f'"{saved.title[:60]}" published.' if saved.is_published
            else f'"{saved.title[:60]}" saved as a draft — it is not public until you tick "Publish now".',
        )

        if 'save_and_add' in request.POST:
            carry = {'section': saved.section_id or '', 'issue': saved.issue_id or ''}
            return redirect(
                reverse('journal:article_create') + '?'
                + urlencode({key: value for key, value in carry.items() if value})
            )
        return redirect('journal:editor_articles')

    return render(request, 'journal/editor/article_form.html', journal_context(
        nav='editor', form=form, formset=formset, article=None,
    ))


@chief_required
def article_edit(request, pk):
    """Correct a published article — metadata, PDF, authors, issue placement.

    Corrections have to be possible without the Django admin, because the admin
    does not run the slug, page-range or publication-date rules that keep the
    published record citable.
    """
    article = get_object_or_404(
        Article.objects.select_related('submission', 'issue', 'section'), pk=pk,
    )
    was_published = article.is_published

    form = DirectArticleForm(request.POST or None, request.FILES or None, instance=article)
    formset = _article_authors_formset(request, article)

    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            saved = form.save()
            _save_article_authors(formset, saved)

            # An article published from a manuscript has to keep the manuscript
            # in step, or the author's own page still says "in production".
            if saved.is_published and saved.submission_id:
                submission_row = saved.submission
                if submission_row.status != Submission.PUBLISHED:
                    submission_row.status = Submission.PUBLISHED
                    submission_row.save(update_fields=['status', 'updated_at'])
                    submission_row.log('Published', actor=request.user)

        # The galley prints the title, byline and front matter, so a correction
        # to any of them means the PDF readers download is now out of date.
        if saved.source_file or saved.pdf:
            typeset.typeset(saved)

        # Only on the transition: editing the pages of a live article must not
        # email its authors again.
        if saved.is_published and not was_published and form.cleaned_data.get('notify_authors'):
            emails.send_published(saved, request)
            messages.success(request, 'The article is published and the authors have been told.')
        else:
            messages.success(request, 'Saved.')
        return redirect('journal:editor_articles')

    return render(request, 'journal/editor/article_form.html', journal_context(
        nav='editor', form=form, formset=formset, article=article,
    ))


# ------------------------------------------------------------- bulk import

def _apply_byline(article, names):
    """Replace an article's byline with the names given, in order.

    Rewritten rather than reconciled: on the import screen the text field *is*
    the byline, so what it says is what the article should credit.
    """
    existing = list(article.authors.all())
    for position, (first_name, last_name) in enumerate(names):
        if position < len(existing):
            author = existing[position]
            author.first_name, author.last_name, author.order = first_name, last_name, position
            author.save(update_fields=['first_name', 'last_name', 'order'])
        else:
            ArticleAuthor.objects.create(
                article=article, first_name=first_name, last_name=last_name, order=position,
            )
    for surplus in existing[len(names):]:
        surplus.delete()


@chief_required
def article_import(request):
    """Step one: take a folder of ready papers and stage one article per file.

    Each file becomes a staged article straight away rather than sitting in a
    temporary area, so a browser crash between the upload and the review screen
    costs nothing — the batch is already in the database, just not public.
    """
    form = ArticleImportForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        batch = uuid.uuid4()
        date = form.cleaned_data.get('publication_date')
        unreadable = []

        with transaction.atomic():
            for uploaded in form.cleaned_data['files']:
                metadata = ingest.extract(uploaded)
                if metadata.error:
                    unreadable.append(uploaded.name)

                article = Article.objects.create(
                    section=form.cleaned_data['section'],
                    issue=form.cleaned_data.get('issue'),
                    licence=form.cleaned_data['licence'],
                    title=metadata.title or ingest.title_from_filename(uploaded.name),
                    abstract=metadata.abstract,
                    keywords=metadata.keywords,
                    source_file=uploaded,
                    is_published=False,
                    added_by=request.user,
                    import_batch=batch,
                    published_at=_publication_datetime(date),
                )
                _apply_byline(article, metadata.authors)

        count = len(form.cleaned_data['files'])
        messages.success(
            request,
            f'{count} file{pluralize(count)} staged. Nothing is public yet — '
            'check the details below, then publish.',
        )
        if unreadable:
            messages.warning(
                request,
                'Could not read the details out of: ' + ', '.join(unreadable[:5])
                + ('…' if len(unreadable) > 5 else '')
                + '. Their titles come from the filenames — type the rest in.',
            )
        return redirect('journal:article_import_review', batch=batch)

    return render(request, 'journal/editor/article_import.html', journal_context(
        nav='editor', form=form,
    ))


def _publication_datetime(date):
    """Midnight on the chosen day, or nothing at all.

    A staged article with no date shows none; ``Article.save`` stamps one the
    moment it is actually published.
    """
    if not date:
        return None
    return timezone.make_aware(
        datetime.combine(date, time.min), timezone.get_current_timezone(),
    )


@chief_required
def article_import_review(request, batch):
    """Step two: check what was read out of the files, then publish the batch.

    Extraction guesses. This screen is where the guesses become the published
    record or get corrected, and nothing in the batch is public until an editor
    has ticked it here.
    """
    articles = (
        Article.objects.filter(import_batch=batch)
        .select_related('section', 'issue').prefetch_related('authors')
        .order_by('created_at', 'pk')
    )
    if not articles.exists():
        messages.error(request, 'That import batch no longer exists.')
        return redirect('journal:editor_articles')

    formset = ImportedArticleFormSet(request.POST or None, queryset=articles, prefix='rows')

    if request.method == 'POST' and formset.is_valid():
        published, discarded, saved = 0, 0, 0
        deleted_rows = formset.deleted_forms
        with transaction.atomic():
            for row in formset.forms:
                if row in deleted_rows:
                    # The galley goes with the record: a discarded import must
                    # not leave its file behind on disk.
                    row.instance.pdf.delete(save=False)
                    row.instance.delete()
                    discarded += 1
                    continue

                article = row.save(commit=False)
                if row.cleaned_data.get('publish'):
                    article.is_published = True
                    published += 1
                article.save()
                _apply_byline(article, ingest.names_to_pairs(row.cleaned_data.get('authors', '')))
                # Now, not at upload: the galley prints the metadata that was
                # just corrected on this screen.
                typeset.typeset(article)
                saved += 1

        parts = []
        if published:
            parts.append(f'{published} article{pluralize(published)} published')
        if saved - published:
            parts.append(f'{saved - published} still staged')
        if discarded:
            parts.append(f'{discarded} discarded')
        messages.success(request, ', '.join(parts).capitalize() + '.' if parts else 'Nothing to do.')

        # Authors imported this way have no email address on file, so nobody was
        # written to. Saying so beats leaving an editor to assume otherwise.
        if published:
            messages.info(
                request,
                'No emails were sent: imported articles carry no author addresses. '
                'Add them on an article if you want to write to its authors.',
            )

        if Article.objects.filter(import_batch=batch).exists():
            return redirect('journal:article_import_review', batch=batch)
        return redirect('journal:editor_articles')

    return render(request, 'journal/editor/article_import_review.html', journal_context(
        nav='editor',
        formset=formset,
        batch=batch,
        rows=list(zip(formset.forms, articles)),
        staged=articles.filter(is_published=False).count(),
        live=articles.filter(is_published=True).count(),
        non_pdf=[article for article in articles if not article.galley_is_pdf],
    ))


@chief_required
def article_retypeset(request, pk):
    """Generate the JELTAN galley again from the source manuscript.

    Needed whenever something outside an article's own form changes what its
    galley should say — the journal's name, its ISSN, the template itself — none
    of which touch the article record, and all of which are printed on the page.
    """
    article = get_object_or_404(Article, pk=pk)
    if request.method != 'POST':
        return redirect('journal:article_edit', pk=pk)

    if not (article.source_file or article.pdf):
        messages.error(request, 'There is no file to typeset for this article.')
        return redirect('journal:article_edit', pk=pk)

    if typeset.typeset(article):
        messages.success(request, article.typeset_note or 'The galley has been generated again.')
    else:
        messages.error(request, article.typeset_note or 'The galley could not be generated.')
    return redirect('journal:article_edit', pk=pk)


@chief_required
def article_retypeset_batch(request, batch):
    """Re-typeset a whole import batch, for when a template change lands."""
    articles = list(Article.objects.filter(import_batch=batch))
    if request.method != 'POST' or not articles:
        return redirect('journal:article_import_review', batch=batch)

    done = sum(1 for article in articles if typeset.typeset(article))
    messages.success(
        request,
        f'{done} of {len(articles)} galley{pluralize(len(articles))} generated again.',
    )
    return redirect('journal:article_import_review', batch=batch)


# ------------------------------------------- one document, whole article

@chief_required
def article_from_document(request):
    """Generate an article from a single manuscript.

    The other two doors into the record ask for different things: the manual
    form asks an editor to type metadata that is already in the file, and the
    bulk importer is built for a run of twenty and never shows what it read.
    This is the one-file case — hand over the document, and read back the
    article that came out of it before anything is published.
    """
    form = DocumentUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        uploaded = form.cleaned_data['document']
        metadata = ingest.extract(uploaded)

        with transaction.atomic():
            article = Article.objects.create(
                section=form.cleaned_data['section'],
                issue=form.cleaned_data.get('issue'),
                licence=form.cleaned_data['licence'],
                title=metadata.title or ingest.title_from_filename(uploaded.name),
                abstract=metadata.abstract,
                keywords=metadata.keywords,
                source_file=uploaded,
                is_published=False,
                added_by=request.user,
            )
            _apply_byline(article, metadata.authors)

        # Typeset now, unlike a bulk import: the whole point of this page is to
        # show what came out, and what came out is the typeset article.
        typeset.typeset(article)

        if metadata.error:
            messages.warning(request, metadata.error)
        messages.success(
            request,
            'The article has been generated. Nothing is public yet — check it below.',
        )
        return redirect('journal:article_generated', pk=article.pk)

    return render(request, 'journal/editor/article_from_document.html', journal_context(
        nav='editor', form=form,
    ))


@chief_required
def article_generated(request, pk):
    """Read back the article that came out of the document, then publish it."""
    article = get_object_or_404(
        Article.objects.select_related('section', 'issue').prefetch_related('authors'), pk=pk,
    )
    form = ImportedArticleForm(request.POST or None, instance=article)

    # Before validation, not after: a document whose title could not be read is
    # exactly the one an editor wants to throw away, and refusing to discard it
    # until they have typed a title in would be a trap.
    if request.method == 'POST' and 'discard' in request.POST:
        article.source_file.delete(save=False)
        article.pdf.delete(save=False)
        typeset.clear_figures(article)
        article.delete()
        messages.success(request, 'Discarded, along with its files.')
        return redirect('journal:editor_articles')

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            if form.cleaned_data.get('publish'):
                saved.is_published = True
            saved.save()
            _apply_byline(saved, ingest.names_to_pairs(form.cleaned_data.get('authors', '')))

        # The galley prints the title and byline that were just corrected.
        typeset.typeset(saved)

        if saved.is_published:
            messages.success(request, 'Published.')
            return redirect('journal:article_detail', slug=saved.slug)
        messages.success(request, 'Saved. It stays out of public view until you publish it.')
        return redirect('journal:article_generated', pk=pk)

    return render(request, 'journal/editor/article_generated.html', journal_context(
        nav='editor',
        article=article,
        form=form,
        outline=typeset.outline_of(article.body_html),
    ))
