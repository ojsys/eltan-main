"""Transactional mail for JELTAN.

Every editorial step is something someone is waiting on — an invitation, a
decision, a request for revisions — so these go out through
``membership.email_utils.send_now``: synchronous, with the outcome returned, and
never raising into the view that triggered them. A journal that silently fails to
tell an author their paper was accepted is worse than one that shows an error.

All of them render one shared template. The content of a decision letter differs;
the shape (heading, body, details, action button) does not, and keeping it in one
place is what stops the fifteenth notification from looking like a different
journal wrote it.
"""

import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from membership.email_utils import build_html_email, send_now

from .models import JournalRole, JournalSettings, ReviewAssignment, Submission

logger = logging.getLogger(__name__)


def _absolute(request, path):
    """Build a full URL for an email link.

    Emails are read outside the request, so a relative link is useless. When
    there is no request to build from (a management command, a shell), fall back
    to SITE_URL.
    """
    if request is not None:
        return request.build_absolute_uri(path)
    base = getattr(settings, 'SITE_URL', 'https://eltanigeria.org').rstrip('/')
    return f"{base}{path}"


def _send(subject, heading, intro, to, details=None, body_paragraphs=None,
          action_url=None, action_label=None, footnote=''):
    """Render and send one notification. Returns ``(ok, error)``."""
    if not to:
        return False, 'No recipient address.'

    journal = JournalSettings.load()
    context = {
        'journal': journal,
        'heading': heading,
        'intro': intro,
        'details': details or [],
        'body_paragraphs': body_paragraphs or [],
        'action_url': action_url,
        'action_label': action_label,
        'footnote': footnote,
        'year': timezone.now().year,
        'contact_email': journal.contact_email or getattr(
            settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL
        ),
    }
    html = render_to_string('journal/emails/notification.html', context)
    text = render_to_string('journal/emails/notification.txt', context)

    recipients = [to] if isinstance(to, str) else list(to)
    message = build_html_email(
        subject=f'[{journal.short_name}] {subject}',
        html_body=html,
        to=recipients,
        text_body=text,
    )
    ok, error = send_now(message)
    if not ok:
        logger.error(f'JELTAN email failed ({subject} -> {recipients}): {error}')
    return ok, error


def _submission_details(submission):
    return [
        ('Manuscript ID', submission.manuscript_id),
        ('Title', submission.title),
        ('Section', submission.section.name),
        ('Status', submission.get_status_display()),
    ]


# --- Author notifications ------------------------------------------------

def send_submission_received(submission, request=None):
    """Confirm to the author that the manuscript arrived, with its id."""
    return _send(
        subject=f'Submission received — {submission.manuscript_id}',
        heading='Thank you for your submission',
        intro=(
            f'We have received your manuscript and it is now with the editorial office. '
            f'Please quote {submission.manuscript_id} in any correspondence.'
        ),
        to=submission.notification_email,
        details=_submission_details(submission),
        body_paragraphs=[
            'Your paper will first be checked by an editor for scope and completeness. '
            'If it passes that check it will be sent to at least two reviewers for '
            'double-blind peer review.',
            'You can follow its progress at any time from your submissions page.',
        ],
        action_url=_absolute(request, reverse('journal:submission_detail', args=[submission.pk])),
        action_label='View my submission',
    )


def send_editors_new_submission(submission, request=None):
    """Tell the editorial team a manuscript is waiting for a desk check."""
    editors = JournalRole.editor_emails()
    if not editors:
        return False, 'No editors configured.'
    return _send(
        subject=f'New submission awaiting desk check — {submission.manuscript_id}',
        heading='A new manuscript has been submitted',
        intro=f'{submission.manuscript_id} is waiting for an initial editorial check.',
        to=editors,
        details=_submission_details(submission) + [('Author', submission.author_list)],
        action_url=_absolute(request, reverse('journal:editor_submission', args=[submission.pk])),
        action_label='Open in the editor queue',
    )


def send_decision(submission, decision, reviews=None, request=None):
    """The decision letter — the email that matters most to an author."""
    paragraphs = [decision.letter_to_author]

    if decision.share_reviews_with_author and reviews:
        for index, review in enumerate(reviews, start=1):
            paragraphs.append(f'--- Reviewer {index} ---')
            if review.recommendation:
                paragraphs.append(f'Recommendation: {review.get_recommendation_display()}')
            paragraphs.append(review.comments_to_author)

    needs_action = decision.decision in [
        decision.MINOR_REVISION, decision.MAJOR_REVISION,
    ]
    return _send(
        subject=f'Editorial decision — {submission.manuscript_id}',
        heading=f'Decision: {decision.get_decision_display()}',
        intro=f'A decision has been reached on {submission.manuscript_id}, "{submission.title}".',
        to=submission.notification_email,
        details=_submission_details(submission),
        body_paragraphs=paragraphs,
        action_url=_absolute(request, reverse('journal:submission_detail', args=[submission.pk])),
        action_label='Upload my revision' if needs_action else 'View my submission',
    )


def send_acceptance_with_apc(submission, request=None):
    """Acceptance, plus the article processing charge that follows it."""
    journal = JournalSettings.load()
    details = _submission_details(submission) + [
        ('Article processing charge', f'{journal.apc_currency} {submission.apc_amount:,.2f}'),
    ]
    return _send(
        subject=f'Accepted for publication — {submission.manuscript_id}',
        heading='Your paper has been accepted',
        intro=(
            f'We are pleased to tell you that "{submission.title}" has been accepted '
            f'for publication in {journal.name}.'
        ),
        to=submission.notification_email,
        details=details,
        body_paragraphs=[
            f'Before the paper goes into production, the article processing charge of '
            f'{journal.apc_currency} {submission.apc_amount:,.2f} is payable by the '
            f'corresponding author.',
            'Once payment is confirmed your paper moves to typesetting, and you will be '
            'sent a proof to approve before it is published.',
        ],
        action_url=_absolute(request, reverse('journal:pay_apc', args=[submission.pk])),
        action_label='Pay the article processing charge',
    )


def send_apc_receipt(submission, request=None):
    journal = JournalSettings.load()
    return _send(
        subject=f'Payment received — {submission.manuscript_id}',
        heading='Article processing charge received',
        intro=f'Thank you. Your payment for {submission.manuscript_id} has been confirmed.',
        to=submission.notification_email,
        details=_submission_details(submission) + [
            ('Amount paid', f'{journal.apc_currency} {submission.apc_amount:,.2f}'),
            ('Reference', submission.apc_reference or '—'),
            ('Paid on', timezone.localtime(submission.apc_paid_at).strftime('%d %B %Y')
             if submission.apc_paid_at else '—'),
        ],
        body_paragraphs=['Your paper is now in production. This email is your receipt.'],
        action_url=_absolute(request, reverse('journal:submission_detail', args=[submission.pk])),
        action_label='View my submission',
    )


def send_published(article, request=None):
    """Tell the author their article is live, with the link to it."""
    submission = article.submission
    recipient = submission.notification_email if submission else None
    if not recipient:
        recipient = article.authors.first().email if article.authors.exists() else None
    if not recipient:
        return False, 'No author address on the article.'

    return _send(
        subject=f'Published — {article.title[:60]}',
        heading='Your article is published',
        intro=f'"{article.title}" is now live in {JournalSettings.load().name}.',
        to=recipient,
        details=[
            ('Issue', article.issue.label if article.issue else 'Online first'),
            ('Pages', article.page_range or '—'),
            ('DOI', article.doi or '—'),
            ('Licence', article.licence),
        ],
        body_paragraphs=[
            'Please cite it as:',
            article.citation,
        ],
        action_url=_absolute(request, article.get_absolute_url()),
        action_label='Read the article',
    )


# --- Reviewer notifications ---------------------------------------------

def send_review_invitation(assignment, personal_message='', request=None):
    """Invite a reviewer.

    The manuscript is described by title and abstract only — no authors — because
    a reviewer who declines has still learned nothing about who wrote it.
    """
    submission = assignment.submission
    paragraphs = []
    if personal_message:
        paragraphs.append(personal_message)
    paragraphs += [
        'The review is double-blind: the manuscript has been anonymised, and your '
        'identity will not be disclosed to the authors.',
        f'Abstract: {submission.abstract}',
        'Please use the link below to accept or decline. If you accept, the same link '
        'takes you to the manuscript and the review form.',
    ]

    return _send(
        subject=f'Invitation to review — {submission.manuscript_id}',
        heading='Invitation to review a manuscript',
        intro=(
            f'Dear {assignment.reviewer_name}, you are invited to review a manuscript '
            f'submitted to {JournalSettings.load().name}.'
        ),
        to=assignment.reviewer_email,
        details=[
            ('Manuscript ID', submission.manuscript_id),
            ('Title', submission.title),
            ('Section', submission.section.name),
            ('Review due by', assignment.due_date.strftime('%d %B %Y') if assignment.due_date else '—'),
        ],
        body_paragraphs=paragraphs,
        action_url=_absolute(request, assignment.review_url),
        action_label='Accept or decline this invitation',
        footnote='This link is personal to you. Please do not forward it.',
    )


def send_review_reminder(assignment, request=None):
    submission = assignment.submission
    overdue = assignment.is_overdue
    return _send(
        subject=f'{"Overdue" if overdue else "Reminder"}: review of {submission.manuscript_id}',
        heading='Your review is ' + ('overdue' if overdue else 'due soon'),
        intro=(
            f'Dear {assignment.reviewer_name}, this is a reminder about the manuscript '
            f'you agreed to review for {JournalSettings.load().name}.'
        ),
        to=assignment.reviewer_email,
        details=[
            ('Manuscript ID', submission.manuscript_id),
            ('Title', submission.title),
            ('Due', assignment.due_date.strftime('%d %B %Y') if assignment.due_date else '—'),
        ],
        body_paragraphs=[
            'If you are no longer able to review this paper, please let us know using the '
            'same link so we can invite someone else.',
        ],
        action_url=_absolute(request, assignment.review_url),
        action_label='Open the review form',
    )


def send_review_thanks(assignment, request=None):
    return _send(
        subject=f'Thank you for your review — {assignment.submission.manuscript_id}',
        heading='Your review has been received',
        intro=(
            f'Thank you for reviewing {assignment.submission.manuscript_id}. '
            'Your report has been sent to the handling editor.'
        ),
        to=assignment.reviewer_email,
        body_paragraphs=[
            'We are grateful for the time you gave this manuscript. Peer review is '
            'unpaid work that the whole field depends on.',
        ],
    )


def send_editors_review_submitted(assignment, request=None):
    submission = assignment.submission
    editors = [submission.handling_editor.email] if submission.handling_editor else JournalRole.editor_emails()
    if not editors:
        return False, 'No editors configured.'
    return _send(
        subject=f'Review received — {submission.manuscript_id}',
        heading='A review has come in',
        intro=f'{assignment.reviewer_name} has submitted a review of {submission.manuscript_id}.',
        to=editors,
        details=[
            ('Manuscript ID', submission.manuscript_id),
            ('Title', submission.title),
            ('Recommendation', assignment.get_recommendation_display()),
            ('Reviews completed this round',
             str(submission.reviews_this_round.filter(status=ReviewAssignment.SUBMITTED).count())),
        ],
        action_url=_absolute(request, reverse('journal:editor_submission', args=[submission.pk])),
        action_label='Read the review',
    )


def send_editors_reviewer_response(assignment, request=None):
    """Tell the editor a reviewer accepted or declined, so a decline is not a silence."""
    submission = assignment.submission
    editors = [submission.handling_editor.email] if submission.handling_editor else JournalRole.editor_emails()
    if not editors:
        return False, 'No editors configured.'
    declined = assignment.status == ReviewAssignment.DECLINED
    return _send(
        subject=f'Reviewer {"declined" if declined else "accepted"} — {submission.manuscript_id}',
        heading=f'{assignment.reviewer_name} has {"declined" if declined else "accepted"} the invitation',
        intro=f'Regarding {submission.manuscript_id}, "{submission.title}".',
        to=editors,
        details=[
            ('Reviewer', assignment.reviewer_name),
            ('Reason', assignment.decline_reason or '—') if declined else
            ('Due', assignment.due_date.strftime('%d %B %Y') if assignment.due_date else '—'),
        ],
        body_paragraphs=(
            ['You may want to invite a replacement reviewer.'] if declined else []
        ),
        action_url=_absolute(request, reverse('journal:editor_submission', args=[submission.pk])),
        action_label='Open the manuscript',
    )


def send_editors_revision_received(submission, request=None):
    editors = [submission.handling_editor.email] if submission.handling_editor else JournalRole.editor_emails()
    if not editors:
        return False, 'No editors configured.'
    return _send(
        subject=f'Revision received — {submission.manuscript_id}',
        heading='A revised manuscript has been uploaded',
        intro=f'The author has submitted round {submission.current_round} of {submission.manuscript_id}.',
        to=editors,
        details=_submission_details(submission),
        action_url=_absolute(request, reverse('journal:editor_submission', args=[submission.pk])),
        action_label='Review the revision',
    )
