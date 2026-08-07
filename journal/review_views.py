"""The reviewer's side of JELTAN.

Reviewers are academics who mostly have no account here, so everything they do
runs off the private token in their invitation email. The token is the
credential: it identifies one reviewer, on one manuscript, for one round, and it
stops working the moment the assignment is completed or cancelled.
"""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import emails
from .forms import ReviewForm
from .models import JournalSettings, ReviewAssignment, SubmissionFile
from .views import journal_context


def _get_assignment(token):
    assignment = ReviewAssignment.objects.filter(token=token).select_related('submission').first()
    if not assignment:
        raise Http404('This review link is not valid.')
    return assignment


def review(request, token):
    """One page for the whole reviewer journey: invitation, then the report.

    Which state the reviewer is in decides what they see, so a single
    bookmarkable link works from invitation through to submission — reviewers
    lose emails, and a link that stops working is a review that never arrives.
    """
    assignment = _get_assignment(token)
    submission = assignment.submission

    if assignment.status == ReviewAssignment.CANCELLED:
        return render(request, 'journal/review_closed.html', journal_context(
            assignment=assignment,
            reason='This review request has been withdrawn by the editor.',
        ))

    if not submission.is_open and assignment.status != ReviewAssignment.SUBMITTED:
        return render(request, 'journal/review_closed.html', journal_context(
            assignment=assignment,
            reason='This manuscript is no longer under consideration.',
        ))

    if assignment.status == ReviewAssignment.SUBMITTED:
        return render(request, 'journal/review_done.html', journal_context(
            assignment=assignment, submission=submission,
        ))

    if assignment.status == ReviewAssignment.DECLINED:
        return render(request, 'journal/review_closed.html', journal_context(
            assignment=assignment,
            reason='You declined this invitation. Thank you for letting us know.',
        ))

    if assignment.status == ReviewAssignment.INVITED:
        return render(request, 'journal/review_invitation.html', journal_context(
            assignment=assignment, submission=submission,
        ))

    # Accepted — show the manuscript and the review form.
    # Remembering the token lets the file download check recognise the reviewer
    # without the token having to be pasted onto every link.
    request.session['journal_review_token'] = assignment.token

    form = ReviewForm(request.POST or None, request.FILES or None, instance=assignment)
    if request.method == 'POST' and form.is_valid():
        assignment = form.save(commit=False)
        assignment.status = ReviewAssignment.SUBMITTED
        assignment.completed_at = timezone.now()
        assignment.save()

        if form.cleaned_data.get('attachment'):
            SubmissionFile.objects.create(
                submission=submission,
                kind=SubmissionFile.REVIEW_ATTACHMENT,
                file=form.cleaned_data['attachment'],
                round=assignment.round,
                uploaded_by=assignment.reviewer_user,
            )

        # Not public: which reviewer said what, and when, is exactly what
        # double-blind review conceals from the author.
        submission.log(
            f'Review received from {assignment.reviewer_name}',
            note=f'Recommendation: {assignment.get_recommendation_display()}',
            is_public=False,
        )

        emails.send_review_thanks(assignment, request)
        emails.send_editors_review_submitted(assignment, request)

        return render(request, 'journal/review_done.html', journal_context(
            assignment=assignment, submission=submission, just_submitted=True,
        ))

    return render(request, 'journal/review_form.html', journal_context(
        assignment=assignment,
        submission=submission,
        form=form,
        files=submission.reviewer_files,
        journal_settings=JournalSettings.load(),
    ))


def review_respond(request, token):
    """Accept or decline an invitation."""
    assignment = _get_assignment(token)

    if request.method != 'POST':
        return redirect('journal:review', token=token)

    if assignment.status != ReviewAssignment.INVITED:
        messages.info(request, 'You have already responded to this invitation.')
        return redirect('journal:review', token=token)

    answer = request.POST.get('answer')
    if answer == 'accept':
        assignment.accept()
        assignment.submission.log(
            f'{assignment.reviewer_name} accepted the review invitation', is_public=False,
        )
        emails.send_editors_reviewer_response(assignment, request)
        messages.success(request, 'Thank you for accepting. The manuscript is below.')
    elif answer == 'decline':
        assignment.decline(request.POST.get('reason', '').strip())
        emails.send_editors_reviewer_response(assignment, request)
        messages.success(request, 'Thank you for letting us know.')
    else:
        messages.error(request, 'Please choose whether to accept or decline.')

    return redirect('journal:review', token=token)


def review_file(request, token, pk):
    """Download a manuscript file as a reviewer.

    Goes through the same permission check as every other manuscript download,
    with the token supplied from the URL — the title page is not on the list of
    files a reviewer may open.
    """
    assignment = _get_assignment(token)
    file_row = get_object_or_404(SubmissionFile, pk=pk, submission=assignment.submission)

    if assignment.status not in [ReviewAssignment.ACCEPTED, ReviewAssignment.SUBMITTED]:
        raise Http404('No such file.')
    if not file_row.is_reviewer_visible:
        raise Http404('No such file.')

    from django.http import FileResponse
    try:
        handle = file_row.file.open('rb')
    except FileNotFoundError:
        raise Http404('That file is no longer on the server.')
    return FileResponse(handle, as_attachment=True, filename=file_row.original_name or 'manuscript')
