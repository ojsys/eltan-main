"""Tests for the JELTAN editorial pipeline.

The emphasis is on the things a journal cannot get wrong: that double-blind
review actually holds, that a manuscript can only move the way the workflow
allows, and that the record of each round survives the next one.
"""

from datetime import timedelta
from unittest.mock import patch
from xml.etree import ElementTree as ET

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from account.models import CustomUser
from journal.models import (
    Article,
    ArticleAuthor,
    EditorialDecision,
    Issue,
    JournalRole,
    JournalSettings,
    Proof,
    ReviewAssignment,
    ScreeningReport,
    Section,
    Submission,
    SubmissionAuthor,
    SubmissionFile,
)


def a_file(name='manuscript.docx'):
    return SimpleUploadedFile(name, b'manuscript body', content_type='application/msword')


class JournalTestCase(TestCase):
    """Shared fixtures: a journal, a section, an author, an editor."""

    def setUp(self):
        self.journal = JournalSettings.load()
        self.journal.apc_amount = 25000
        self.journal.reviews_required = 2
        self.journal.save()

        self.section = Section.objects.create(name='Research Articles')
        self.author = CustomUser.objects.create_user(
            email='author@example.com', password='pw-for-tests-only',
            first_name='Ada', last_name='Obi',
        )
        self.editor_user = CustomUser.objects.create_user(
            email='editor@example.com', password='pw-for-tests-only',
            first_name='Kunle', last_name='Bello',
        )
        JournalRole.objects.create(user=self.editor_user, role=JournalRole.EDITOR_IN_CHIEF)
        mail.outbox = []

    def make_submission(self, **overrides):
        fields = {
            'title': 'Reading comprehension in multilingual classrooms',
            'abstract': 'An abstract. ' * 20,
            'keywords': 'reading, multilingual, Nigeria',
            'section': self.section,
            'submitter': self.author,
            'is_original_work': True,
            'not_under_review_elsewhere': True,
            'agrees_to_policies': True,
        }
        fields.update(overrides)
        submission = Submission.objects.create(**fields)
        SubmissionAuthor.objects.create(
            submission=submission, first_name='Ada', last_name='Obi',
            email='author@example.com', is_corresponding=True,
        )
        SubmissionFile.objects.create(
            submission=submission, kind=SubmissionFile.ANONYMISED_MANUSCRIPT, file=a_file(),
        )
        SubmissionFile.objects.create(
            submission=submission, kind=SubmissionFile.TITLE_PAGE, file=a_file('title.docx'),
        )
        return submission

    def invite_reviewer(self, submission, email='reviewer@example.com', name='Dr Reviewer'):
        return ReviewAssignment.objects.create(
            submission=submission, round=submission.current_round,
            reviewer_name=name, reviewer_email=email,
        )

    def pass_screening(self, submission):
        """Clear administrative screening — the gate peer review sits behind."""
        return ScreeningReport.objects.create(
            submission=submission, round=submission.current_round, passed=True,
            files_complete=True, is_anonymised=True, title_page_separate=True,
            abstract_and_keywords=True, declarations_complete=True, references_formatted=True,
            screened_by=self.editor_user,
        )


class ManuscriptIdTests(JournalTestCase):
    def test_ids_are_sequential_within_the_year(self):
        first = self.make_submission()
        second = self.make_submission()
        year = timezone.now().year

        self.assertEqual(first.manuscript_id, f'JELTAN-{year}-0001')
        self.assertEqual(second.manuscript_id, f'JELTAN-{year}-0002')

    def test_deleting_a_submission_does_not_cause_a_duplicate_id(self):
        # Deleting the *first* of two is the case a count-based id gets wrong:
        # one row left, so a count would hand out 0002 again — a collision with
        # the submission still on file.
        first = self.make_submission()
        second = self.make_submission()
        first.delete()

        third = self.make_submission()

        self.assertNotEqual(third.manuscript_id, second.manuscript_id)
        self.assertEqual(third.manuscript_id, f'JELTAN-{timezone.now().year}-0003')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SubmissionFlowTests(JournalTestCase):
    def test_submitting_stores_files_authors_and_notifies_everyone(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse('journal:submit'), {
            'section': self.section.pk,
            'title': 'A study of classroom talk',
            'abstract': 'word ' * 80,
            'keywords': 'talk, classroom, discourse',
            'cover_letter': 'Please consider this paper.',
            'conflict_of_interest': 'None',
            'funding_statement': 'None',
            'ethics_statement': 'Approved by the university committee.',
            'is_original_work': 'on',
            'not_under_review_elsewhere': 'on',
            'agrees_to_policies': 'on',
            'anonymised_manuscript': a_file(),
            'title_page': a_file('title.docx'),
            'authors-TOTAL_FORMS': '1',
            'authors-INITIAL_FORMS': '0',
            'authors-MIN_NUM_FORMS': '1',
            'authors-MAX_NUM_FORMS': '1000',
            'authors-0-first_name': 'Ada',
            'authors-0-last_name': 'Obi',
            'authors-0-email': 'author@example.com',
            'authors-0-affiliation': 'University of Lagos',
            'authors-0-is_corresponding': 'on',
        })

        submission = Submission.objects.get(title='A study of classroom talk')
        self.assertRedirects(response, reverse('journal:submission_detail', args=[submission.pk]))
        self.assertEqual(submission.status, Submission.SUBMITTED)
        self.assertEqual(submission.authors.count(), 1)
        self.assertEqual(submission.files.count(), 2)
        # Author confirmation and the editorial office notification.
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(submission.manuscript_id, mail.outbox[0].subject)

    def test_an_author_list_without_a_corresponding_author_still_gets_one(self):
        self.client.force_login(self.author)
        self.client.post(reverse('journal:submit'), {
            'section': self.section.pk,
            'title': 'Nobody ticked the box',
            'abstract': 'word ' * 80,
            'keywords': 'one, two, three',
            'conflict_of_interest': 'None',
            'is_original_work': 'on',
            'not_under_review_elsewhere': 'on',
            'agrees_to_policies': 'on',
            'anonymised_manuscript': a_file(),
            'title_page': a_file('title.docx'),
            'authors-TOTAL_FORMS': '1',
            'authors-INITIAL_FORMS': '0',
            'authors-MIN_NUM_FORMS': '1',
            'authors-MAX_NUM_FORMS': '1000',
            'authors-0-first_name': 'Ada',
            'authors-0-last_name': 'Obi',
            'authors-0-email': 'author@example.com',
        })

        submission = Submission.objects.get(title='Nobody ticked the box')
        # Every decision email is addressed to the corresponding author, so there
        # must always be one.
        self.assertTrue(submission.authors.filter(is_corresponding=True).exists())
        self.assertEqual(submission.notification_email, 'author@example.com')

    def test_an_over_long_abstract_is_rejected(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse('journal:submit'), {
            'section': self.section.pk,
            'title': 'Too long',
            'abstract': 'word ' * 300,
            'keywords': 'one, two, three',
            'is_original_work': 'on',
            'not_under_review_elsewhere': 'on',
            'agrees_to_policies': 'on',
            'anonymised_manuscript': a_file(),
            'title_page': a_file('title.docx'),
            'authors-TOTAL_FORMS': '1', 'authors-INITIAL_FORMS': '0',
            'authors-MIN_NUM_FORMS': '1', 'authors-MAX_NUM_FORMS': '1000',
            'authors-0-first_name': 'Ada', 'authors-0-last_name': 'Obi',
            'authors-0-email': 'author@example.com',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Submission.objects.filter(title='Too long').exists())
        self.assertContains(response, 'the limit is 250')

    def test_submissions_can_be_closed(self):
        self.journal.is_accepting_submissions = False
        self.journal.save()
        self.client.force_login(self.author)

        response = self.client.get(reverse('journal:submit'))

        self.assertContains(response, 'Submissions are closed')

    def test_submitting_requires_login(self):
        response = self.client.get(reverse('journal:submit'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


class DoubleBlindTests(JournalTestCase):
    """The anonymity guarantees, which are the point of the whole model."""

    def test_a_reviewer_is_never_offered_the_title_page(self):
        submission = self.make_submission()
        kinds = {f.kind for f in submission.reviewer_files}

        self.assertIn(SubmissionFile.ANONYMISED_MANUSCRIPT, kinds)
        self.assertNotIn(SubmissionFile.TITLE_PAGE, kinds)

    def test_a_reviewer_cannot_download_the_title_page_by_url(self):
        submission = self.make_submission()
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        title_page = submission.files.get(kind=SubmissionFile.TITLE_PAGE)

        response = self.client.get(
            reverse('journal:review_file', args=[assignment.token, title_page.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_a_reviewer_can_download_the_anonymised_manuscript(self):
        submission = self.make_submission()
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        manuscript = submission.files.get(kind=SubmissionFile.ANONYMISED_MANUSCRIPT)

        response = self.client.get(
            reverse('journal:review_file', args=[assignment.token, manuscript.pk])
        )

        self.assertEqual(response.status_code, 200)

    def test_a_reviewer_who_has_not_accepted_cannot_read_anything(self):
        submission = self.make_submission()
        assignment = self.invite_reviewer(submission)  # still 'invited'
        manuscript = submission.files.get(kind=SubmissionFile.ANONYMISED_MANUSCRIPT)

        response = self.client.get(
            reverse('journal:review_file', args=[assignment.token, manuscript.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_a_stranger_cannot_download_a_manuscript(self):
        submission = self.make_submission()
        manuscript = submission.files.get(kind=SubmissionFile.ANONYMISED_MANUSCRIPT)
        other = CustomUser.objects.create_user(email='nosy@example.com', password='pw-for-tests-only')
        self.client.force_login(other)

        response = self.client.get(reverse('journal:submission_file', args=[manuscript.pk]))

        self.assertEqual(response.status_code, 404)

    def test_the_author_and_editors_can_download_anything(self):
        submission = self.make_submission()
        title_page = submission.files.get(kind=SubmissionFile.TITLE_PAGE)

        self.client.force_login(self.author)
        self.assertEqual(
            self.client.get(reverse('journal:submission_file', args=[title_page.pk])).status_code, 200,
        )
        self.client.force_login(self.editor_user)
        self.assertEqual(
            self.client.get(reverse('journal:submission_file', args=[title_page.pk])).status_code, 200,
        )

    def test_confidential_comments_never_reach_the_author(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        assignment = self.invite_reviewer(submission)
        assignment.status = ReviewAssignment.SUBMITTED
        assignment.recommendation = ReviewAssignment.MINOR_REVISION
        assignment.comments_to_author = 'The methodology section needs more detail.'
        assignment.confidential_comments = 'I suspect this overlaps with the author\'s earlier paper.'
        assignment.save()

        EditorialDecision.objects.create(
            submission=submission, round=1, decision=EditorialDecision.MINOR_REVISION,
            letter_to_author='Please revise.', share_reviews_with_author=True,
        )

        self.client.force_login(self.author)
        response = self.client.get(reverse('journal:submission_detail', args=[submission.pk]))

        self.assertContains(response, 'The methodology section needs more detail.')
        self.assertNotContains(response, 'I suspect this overlaps')
        # Nor the reviewer's name.
        self.assertNotContains(response, 'Dr Reviewer')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ReviewFlowTests(JournalTestCase):
    def test_an_author_cannot_be_invited_to_review_their_own_paper(self):
        from journal.forms import ReviewerInviteForm

        submission = self.make_submission()
        form = ReviewerInviteForm(
            data={'reviewer_name': 'Ada Obi', 'reviewer_email': 'author@example.com'},
            submission=submission,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('cannot review it', str(form.errors))

    def test_the_same_reviewer_cannot_be_invited_twice_in_a_round(self):
        from journal.forms import ReviewerInviteForm

        submission = self.make_submission()
        self.invite_reviewer(submission)
        form = ReviewerInviteForm(
            data={'reviewer_name': 'Dr Reviewer', 'reviewer_email': 'reviewer@example.com'},
            submission=submission,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('already been invited', str(form.errors))

    def test_inviting_a_reviewer_emails_them_and_starts_review(self):
        submission = self.make_submission(status=Submission.EDITORIAL_SCREENING)
        self.pass_screening(submission)
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:invite_reviewer', args=[submission.pk]), {
            'reviewer_name': 'Dr Reviewer',
            'reviewer_email': 'reviewer@example.com',
            'reviewer_affiliation': 'University of Ibadan',
            'due_date': (timezone.now() + timedelta(days=21)).date().isoformat(),
        })

        submission.refresh_from_db()
        assignment = submission.review_assignments.get()
        self.assertEqual(submission.status, Submission.UNDER_REVIEW)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Invitation to review', mail.outbox[0].subject)
        # The invitation must not name the authors.
        self.assertNotIn('Ada Obi', mail.outbox[0].body)
        self.assertIn(assignment.token, mail.outbox[0].body)

    def test_declining_tells_the_editor_and_closes_the_link(self):
        submission = self.make_submission()
        assignment = self.invite_reviewer(submission)

        self.client.post(
            reverse('journal:review_respond', args=[assignment.token]),
            {'answer': 'decline', 'reason': 'Outside my area.'},
        )

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, ReviewAssignment.DECLINED)
        self.assertEqual(assignment.decline_reason, 'Outside my area.')
        self.assertTrue(any('declined' in m.subject for m in mail.outbox))

    def test_submitting_a_review_records_it_and_notifies(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        mail.outbox = []

        response = self.client.post(reverse('journal:review', args=[assignment.token]), {
            'recommendation': ReviewAssignment.MINOR_REVISION,
            'comments_to_author': 'A solid paper that needs more detail in the methodology section.',
            'confidential_comments': 'Publishable after revision.',
            'rating_originality': '4',
            'rating_methodology': '3',
            'rating_clarity': '4',
            'rating_relevance': '5',
        })

        assignment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(assignment.status, ReviewAssignment.SUBMITTED)
        self.assertIsNotNone(assignment.completed_at)
        # Thanks to the reviewer, notification to the editor.
        self.assertEqual(len(mail.outbox), 2)

    def test_a_review_that_says_almost_nothing_is_rejected(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        assignment = self.invite_reviewer(submission)
        assignment.accept()

        self.client.post(reverse('journal:review', args=[assignment.token]), {
            'recommendation': ReviewAssignment.ACCEPT,
            'comments_to_author': 'Good.',
        })

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, ReviewAssignment.ACCEPTED)

    def test_a_cancelled_assignment_stops_working(self):
        submission = self.make_submission()
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        assignment.cancel()

        response = self.client.get(reverse('journal:review', args=[assignment.token]))

        self.assertContains(response, 'This review is closed')

    def test_an_unknown_token_is_a_404(self):
        self.assertEqual(
            self.client.get(reverse('journal:review', args=['not-a-real-token'])).status_code, 404,
        )

    def test_withdrawing_cancels_outstanding_reviews(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        self.client.force_login(self.author)

        self.client.post(reverse('journal:withdraw_submission', args=[submission.pk]))

        submission.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(submission.status, Submission.WITHDRAWN)
        self.assertEqual(assignment.status, ReviewAssignment.CANCELLED)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DecisionTests(JournalTestCase):
    def test_a_decision_moves_the_manuscript_and_writes_to_the_author(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:record_decision', args=[submission.pk]), {
            'decision': EditorialDecision.MAJOR_REVISION,
            'letter_to_author': 'Please address the reviewers’ comments.',
            'share_reviews_with_author': 'on',
        })

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.MAJOR_REVISION)
        self.assertEqual(submission.decisions.count(), 1)
        self.assertTrue(any('decision' in m.subject.lower() for m in mail.outbox))

    def test_acceptance_raises_the_article_processing_charge(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:record_decision', args=[submission.pk]), {
            'decision': EditorialDecision.ACCEPT,
            'letter_to_author': 'We are pleased to accept your paper.',
        })

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.ACCEPTED)
        self.assertEqual(submission.apc_status, Submission.APC_PENDING)
        self.assertEqual(submission.apc_amount, self.journal.apc_amount)
        self.assertTrue(any('Accepted for publication' in m.subject for m in mail.outbox))

    def test_a_waived_charge_sends_an_accepted_paper_straight_to_production(self):
        self.journal.apc_amount = 0
        self.journal.save()
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:record_decision', args=[submission.pk]), {
            'decision': EditorialDecision.ACCEPT,
            'letter_to_author': 'Accepted.',
        })

        submission.refresh_from_db()
        # A journal with no charge must not park accepted papers behind a
        # zero-naira invoice.
        self.assertEqual(submission.apc_status, Submission.APC_WAIVED)
        self.assertEqual(submission.status, Submission.IN_PRODUCTION)

    def _choices(self, submission):
        from journal.forms import DecisionForm

        return [value for value, _ in DecisionForm(submission=submission).fields['decision'].choices]

    def test_before_screening_review_is_the_one_thing_that_cannot_happen(self):
        submission = self.make_submission()  # awaiting administrative screening
        choices = self._choices(submission)

        # Sending for review before the anonymity check is the mistake screening
        # exists to prevent. Everything that does not involve a reviewer is open.
        self.assertNotIn(EditorialDecision.SEND_FOR_REVIEW, choices)
        self.assertIn(EditorialDecision.DESK_REJECT, choices)
        self.assertIn(EditorialDecision.RETURN_TO_AUTHOR, choices)
        self.assertIn(EditorialDecision.WITHDRAW, choices)

    def test_after_screening_the_paper_can_be_sent_for_review(self):
        submission = self.make_submission(status=Submission.EDITORIAL_SCREENING)
        choices = self._choices(submission)

        self.assertIn(EditorialDecision.SEND_FOR_REVIEW, choices)
        self.assertIn(EditorialDecision.DESK_REJECT, choices)
        # Nothing has been reviewed yet, so there is nothing to accept on.
        self.assertNotIn(EditorialDecision.ACCEPT, choices)

    def test_a_reviewed_paper_offers_the_full_set_of_outcomes(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        choices = self._choices(submission)

        for decision in [
            EditorialDecision.ACCEPT, EditorialDecision.ACCEPT_WITH_CHANGES,
            EditorialDecision.MINOR_REVISION, EditorialDecision.MAJOR_REVISION,
            EditorialDecision.REJECT_RESUBMIT, EditorialDecision.REJECT,
        ]:
            self.assertIn(decision, choices)

    def test_a_revision_can_be_sent_back_for_another_round(self):
        submission = self.make_submission(status=Submission.RESUBMITTED)
        self.assertIn(EditorialDecision.ANOTHER_ROUND, self._choices(submission))

    def test_an_editor_reviewed_section_can_be_accepted_without_peer_review(self):
        """A book review or an editorial never goes to a reviewer.

        Gating acceptance on peer review would leave those sections with no way
        of ever being published.
        """
        editorials = Section.objects.create(name='Editorial', peer_reviewed=False)
        submission = self.make_submission(section=editorials)

        self.assertIn(EditorialDecision.ACCEPT, self._choices(submission))

    def test_a_closed_manuscript_offers_no_decisions(self):
        submission = self.make_submission(status=Submission.REJECTED)
        self.assertEqual(self._choices(submission), [])

    def test_returning_a_paper_to_the_author_is_not_a_rejection(self):
        submission = self.make_submission(status=Submission.EDITORIAL_SCREENING)
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:record_decision', args=[submission.pk]), {
            'decision': EditorialDecision.RETURN_TO_AUTHOR,
            'letter_to_author': 'The anonymised file still names the authors.',
        })

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.RETURNED)
        self.assertTrue(submission.is_open)

    def test_withdrawing_stops_the_reviewers(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        assignment = ReviewAssignment.objects.create(
            submission=submission, reviewer_name='Chidi Eze',
            reviewer_email='reviewer@example.com', status=ReviewAssignment.ACCEPTED,
        )
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:record_decision', args=[submission.pk]), {
            'decision': EditorialDecision.WITHDRAW,
            'letter_to_author': 'Withdrawn at the corresponding author’s request.',
        })

        submission.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(submission.status, Submission.WITHDRAWN)
        self.assertEqual(assignment.status, ReviewAssignment.CANCELLED)

    def test_only_editors_reach_the_editorial_queue(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse('journal:editor_dashboard')).status_code, 404)

        self.client.force_login(self.editor_user)
        self.assertEqual(self.client.get(reverse('journal:editor_dashboard')).status_code, 200)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RevisionTests(JournalTestCase):
    def test_a_revision_advances_the_round_and_keeps_the_earlier_files(self):
        submission = self.make_submission(status=Submission.MAJOR_REVISION)
        self.client.force_login(self.author)

        self.client.post(reverse('journal:upload_revision', args=[submission.pk]), {
            'revised_manuscript': a_file('revised.docx'),
            'response_to_reviewers': a_file('response.docx'),
            'note_to_editor': 'We have addressed every point.',
        })

        submission.refresh_from_db()
        self.assertEqual(submission.current_round, 2)
        self.assertEqual(submission.status, Submission.RESUBMITTED)
        # Round 1 is still there — a later round never overwrites an earlier one.
        self.assertEqual(submission.files.filter(round=1).count(), 2)
        self.assertEqual(submission.files.filter(round=2).count(), 2)

    def test_a_revision_cannot_be_uploaded_when_none_was_asked_for(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        self.client.force_login(self.author)

        response = self.client.post(reverse('journal:upload_revision', args=[submission.pk]), {
            'revised_manuscript': a_file('revised.docx'),
            'response_to_reviewers': a_file('response.docx'),
        })

        submission.refresh_from_db()
        self.assertRedirects(response, reverse('journal:submission_detail', args=[submission.pk]))
        self.assertEqual(submission.current_round, 1)

    def test_one_author_cannot_revise_another_author_s_paper(self):
        submission = self.make_submission(status=Submission.MAJOR_REVISION)
        intruder = CustomUser.objects.create_user(email='other@example.com', password='pw-for-tests-only')
        self.client.force_login(intruder)

        response = self.client.get(reverse('journal:upload_revision', args=[submission.pk]))

        self.assertEqual(response.status_code, 404)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PublicationTests(JournalTestCase):
    def test_publishing_creates_the_article_and_closes_the_submission(self):
        submission = self.make_submission(status=Submission.IN_PRODUCTION)
        issue = Issue.objects.create(volume=1, number=1, year=2026, is_published=True)
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:publish', args=[submission.pk]), {
            'issue': issue.pk,
            'title': submission.title,
            'abstract': submission.abstract,
            'keywords': submission.keywords,
            'pdf': SimpleUploadedFile('article.pdf', b'%PDF-1.4', content_type='application/pdf'),
            'first_page': '1',
            'last_page': '18',
            'doi': '10.1234/jeltan.2026.1',
            'licence': 'CC BY 4.0',
            'is_published': 'on',
            'authors-TOTAL_FORMS': '1',
            'authors-INITIAL_FORMS': '0',
            'authors-MIN_NUM_FORMS': '1',
            'authors-MAX_NUM_FORMS': '1000',
            'authors-0-first_name': 'Ada',
            'authors-0-last_name': 'Obi',
            'authors-0-affiliation': 'University of Lagos',
        })

        submission.refresh_from_db()
        article = Article.objects.get(submission=submission)
        self.assertEqual(submission.status, Submission.PUBLISHED)
        self.assertTrue(article.is_published)
        self.assertEqual(article.authors.count(), 1)
        self.assertTrue(any('Published' in m.subject for m in mail.outbox))

    def test_an_unpublished_article_is_not_visible(self):
        article = Article.objects.create(
            title='Not yet public', abstract='x', is_published=False, section=self.section,
        )
        response = self.client.get(reverse('journal:article_detail', args=[article.slug]))
        self.assertEqual(response.status_code, 404)

    def test_a_published_article_carries_indexing_metadata(self):
        issue = Issue.objects.create(volume=1, number=1, year=2026, is_published=True)
        article = Article.objects.create(
            title='Talk in the classroom', abstract='An abstract.', issue=issue,
            section=self.section, is_published=True, first_page=1, last_page=20,
            doi='10.1234/jeltan.1',
        )
        ArticleAuthor.objects.create(article=article, first_name='Ada', last_name='Obi')

        response = self.client.get(reverse('journal:article_detail', args=[article.slug]))

        # Without these an article is published but invisible to Google Scholar.
        self.assertContains(response, 'citation_title')
        self.assertContains(response, 'citation_author')
        self.assertContains(response, 'citation_doi')

    def test_viewing_an_article_counts_the_view(self):
        article = Article.objects.create(
            title='Counted', abstract='x', is_published=True, section=self.section,
        )
        self.client.get(reverse('journal:article_detail', args=[article.slug]))
        article.refresh_from_db()
        self.assertEqual(article.view_count, 1)

    def test_a_back_issue_can_be_published_without_a_submission(self):
        # The archive has to be able to hold papers from before this system.
        issue = Issue.objects.create(volume=1, number=1, year=2019, is_published=True)
        article = Article.objects.create(
            title='A paper from 2019', abstract='x', issue=issue, is_published=True,
        )

        response = self.client.get(reverse('journal:issue_detail', args=[issue.slug]))

        self.assertContains(response, 'A paper from 2019')
        self.assertIsNone(article.submission)

    def test_search_finds_a_published_article_by_author(self):
        article = Article.objects.create(
            title='Findable', abstract='An abstract about reading.', is_published=True,
        )
        ArticleAuthor.objects.create(article=article, first_name='Ngozi', last_name='Eze')

        response = self.client.get(reverse('journal:search'), {'q': 'Eze'})

        self.assertContains(response, 'Findable')


class ApcTests(JournalTestCase):
    def test_paying_moves_the_paper_into_production(self):
        submission = self.make_submission(status=Submission.ACCEPTED)
        submission.start_apc()

        submission.mark_apc_paid('PAY-REF-1')

        self.assertEqual(submission.apc_status, Submission.APC_PAID)
        self.assertEqual(submission.status, Submission.IN_PRODUCTION)
        self.assertEqual(submission.apc_reference, 'PAY-REF-1')

    def test_an_editor_can_waive_the_charge(self):
        submission = self.make_submission(status=Submission.ACCEPTED)
        submission.start_apc()
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:waive_apc', args=[submission.pk]))

        submission.refresh_from_db()
        self.assertEqual(submission.apc_status, Submission.APC_WAIVED)
        self.assertEqual(submission.status, Submission.IN_PRODUCTION)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ReviewReminderCommandTests(JournalTestCase):
    def _run(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('send_review_reminders', *args, stdout=out)
        return out.getvalue()

    def test_an_overdue_reviewer_is_reminded(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        ReviewAssignment.objects.filter(pk=assignment.pk).update(
            due_date=timezone.now().date() - timedelta(days=5),
        )

        self._run()

        assignment.refresh_from_db()
        self.assertIsNotNone(assignment.reminder_sent_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_recently_reminded_reviewer_is_not_nagged_again(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        ReviewAssignment.objects.filter(pk=assignment.pk).update(
            due_date=timezone.now().date() - timedelta(days=5),
            reminder_sent_at=timezone.now() - timedelta(days=1),
        )

        self._run()

        self.assertEqual(len(mail.outbox), 0)

    def test_reviewers_on_a_closed_manuscript_are_left_alone(self):
        submission = self.make_submission(status=Submission.WITHDRAWN)
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        ReviewAssignment.objects.filter(pk=assignment.pk).update(
            due_date=timezone.now().date() - timedelta(days=5),
        )

        self._run()

        self.assertEqual(len(mail.outbox), 0)


class PublicPageTests(JournalTestCase):
    def test_every_public_page_renders(self):
        for name in ['home', 'about', 'editorial_board', 'guidelines', 'policies',
                     'issue_list', 'search']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f'journal:{name}')).status_code, 200)

    def test_the_journal_renders_before_anything_has_been_configured(self):
        # A fresh install must not 500 on its own front page.
        JournalSettings.objects.all().delete()
        Section.objects.all().delete()

        self.assertEqual(self.client.get(reverse('journal:home')).status_code, 200)


class SetupCommandTests(TestCase):
    """The one-shot command that makes a fresh install usable."""

    def _run(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('setup_jeltan', *args, stdout=out)
        return out.getvalue()

    def test_it_creates_the_settings_row_and_sections(self):
        JournalSettings.objects.all().delete()
        Section.objects.all().delete()

        self._run()

        self.assertTrue(JournalSettings.objects.exists())
        self.assertTrue(Section.objects.filter(name='Research Articles', peer_reviewed=True).exists())
        self.assertTrue(Section.objects.filter(name='Book Reviews', peer_reviewed=False).exists())

    def test_running_it_twice_changes_nothing(self):
        self._run()
        section = Section.objects.get(name='Research Articles')
        section.description = 'Edited by hand.'
        section.save()

        self._run()

        section.refresh_from_db()
        # Re-running after an upgrade must not undo the editors' own wording.
        self.assertEqual(section.description, 'Edited by hand.')
        self.assertEqual(Section.objects.filter(name='Research Articles').count(), 1)

    def test_the_apc_can_be_set_from_the_command_line(self):
        self._run('--apc', '25000')
        self.assertEqual(JournalSettings.load().apc_amount, 25000)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdministrativeScreeningTests(JournalTestCase):
    """The technical check, and the return-to-author path that follows a failure."""

    def _screen(self, submission, outcome='pass', **overrides):
        data = {
            'outcome': outcome,
            'files_complete': 'on',
            'is_anonymised': 'on',
            'title_page_separate': 'on',
            'abstract_and_keywords': 'on',
            'declarations_complete': 'on',
            'references_formatted': 'on',
            'notes_to_author': '',
            'internal_notes': '',
        }
        data.update(overrides)
        self.client.force_login(self.editor_user)
        return self.client.post(reverse('journal:screen', args=[submission.pk]), data)

    def test_passing_screening_sends_it_to_editorial_screening(self):
        submission = self.make_submission()

        self._screen(submission)

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.EDITORIAL_SCREENING)
        self.assertTrue(submission.is_screened)
        self.assertTrue(any('Passed initial checks' in m.subject for m in mail.outbox))

    def test_failing_screening_returns_it_rather_than_rejecting_it(self):
        submission = self.make_submission()

        self._screen(
            submission, outcome='return', is_anonymised='',
            notes_to_author='Your name appears in the running head on every page.',
        )

        submission.refresh_from_db()
        # Returned, not rejected — the manuscript is still alive and keeps its ID.
        self.assertEqual(submission.status, Submission.RETURNED)
        self.assertTrue(submission.needs_correction)
        self.assertTrue(submission.is_open)
        self.assertNotIn(submission.status, Submission.CLOSED_STATUSES)

    def test_the_return_email_lists_what_to_fix_and_says_it_is_not_a_rejection(self):
        submission = self.make_submission()

        self._screen(
            submission, outcome='return', is_anonymised='',
            notes_to_author='Your name appears in the running head.',
        )

        email = next(m for m in mail.outbox if 'correct and resubmit' in m.subject.lower())
        self.assertIn('has not been rejected', email.body)
        self.assertIn('running head', email.body)
        self.assertIn('anonymised', email.body)

    def test_a_return_needs_notes_for_the_author(self):
        submission = self.make_submission()

        response = self._screen(submission, outcome='return', notes_to_author='')

        submission.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(submission.status, Submission.SUBMITTED)
        self.assertContains(response, 'cannot act on a bare')

    def test_screening_cannot_be_passed_without_confirming_anonymity(self):
        submission = self.make_submission()

        response = self._screen(submission, outcome='pass', is_anonymised='')

        submission.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(submission.status, Submission.SUBMITTED)
        self.assertContains(response, 'confirmed anonymised')

    def test_a_reviewer_cannot_be_invited_before_screening(self):
        submission = self.make_submission(status=Submission.EDITORIAL_SCREENING)
        self.client.force_login(self.editor_user)

        response = self.client.post(reverse('journal:invite_reviewer', args=[submission.pk]), {
            'reviewer_name': 'Dr Reviewer',
            'reviewer_email': 'reviewer@example.com',
        })

        self.assertRedirects(response, reverse('journal:editor_submission', args=[submission.pk]))
        self.assertEqual(submission.review_assignments.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_correcting_and_resubmitting_keeps_the_same_record_and_round(self):
        submission = self.make_submission()
        self._screen(submission, outcome='return', is_anonymised='',
                     notes_to_author='Please anonymise the running head.')
        original_id = submission.manuscript_id
        mail.outbox = []
        self.client.force_login(self.author)

        self.client.post(reverse('journal:resubmit', args=[submission.pk]), {
            'corrected_manuscript': a_file('corrected.docx'),
            'note_to_editor': 'Running head removed.',
        })

        submission.refresh_from_db()
        self.assertEqual(submission.manuscript_id, original_id)
        # A screening return is not a review round.
        self.assertEqual(submission.current_round, 1)
        self.assertEqual(submission.status, Submission.SUBMITTED)
        self.assertTrue(any('Corrected submission' in m.subject for m in mail.outbox))

    def test_screening_must_be_passed_again_after_a_correction(self):
        submission = self.make_submission()
        self._screen(submission, outcome='return', is_anonymised='', notes_to_author='Anonymise it.')
        self.client.force_login(self.author)
        self.client.post(reverse('journal:resubmit', args=[submission.pk]), {
            'corrected_manuscript': a_file('corrected.docx'),
            'note_to_editor': 'Done.',
        })

        submission.refresh_from_db()
        # The failed report must not count as having cleared the gate.
        self.assertFalse(submission.is_screened)

    def test_an_author_cannot_resubmit_a_manuscript_that_was_not_returned(self):
        submission = self.make_submission(status=Submission.UNDER_REVIEW)
        self.client.force_login(self.author)

        response = self.client.post(reverse('journal:resubmit', args=[submission.pk]), {
            'corrected_manuscript': a_file('corrected.docx'),
            'note_to_editor': 'Nothing to correct.',
        })

        self.assertRedirects(response, reverse('journal:submission_detail', args=[submission.pk]))
        self.assertEqual(submission.files.count(), 2)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ProductionTests(JournalTestCase):
    """Copyediting, the proof, and the author's final approval."""

    def _in_production(self):
        submission = self.make_submission(status=Submission.IN_PRODUCTION)
        submission.apc_status = Submission.APC_WAIVED
        submission.save()
        return submission

    def _send_proof(self, submission, **overrides):
        data = {
            'file': SimpleUploadedFile('proof.pdf', b'%PDF-1.4', content_type='application/pdf'),
            'note_to_author': 'Please check the affiliations.',
            'due_date': (timezone.now() + timedelta(days=5)).date().isoformat(),
        }
        data.update(overrides)
        self.client.force_login(self.editor_user)
        return self.client.post(reverse('journal:send_proof', args=[submission.pk]), data)

    def test_the_copyedited_file_is_stored_against_the_paper(self):
        submission = self._in_production()
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:upload_copyedit', args=[submission.pk]), {
            'copyedited_file': a_file('copyedited.docx'),
            'note': 'Style applied.',
        })

        self.assertTrue(submission.files.filter(kind=SubmissionFile.PRODUCTION).exists())

    def test_sending_a_proof_puts_it_with_the_author(self):
        submission = self._in_production()

        self._send_proof(submission)

        submission.refresh_from_db()
        proof = submission.latest_proof
        self.assertEqual(submission.status, Submission.PROOF_REVIEW)
        self.assertTrue(submission.awaiting_proof_approval)
        self.assertEqual(proof.version, 1)
        self.assertEqual(proof.status, Proof.SENT)
        self.assertTrue(any('Proof for approval' in m.subject for m in mail.outbox))

    def test_approving_the_proof_clears_the_article_for_publication(self):
        submission = self._in_production()
        self._send_proof(submission)
        mail.outbox = []
        self.client.force_login(self.author)

        self.client.post(reverse('journal:proof_response', args=[submission.pk]), {
            'response': 'approve',
        })

        submission.refresh_from_db()
        proof = submission.latest_proof
        self.assertEqual(submission.status, Submission.PROOF_APPROVED)
        self.assertEqual(proof.status, Proof.APPROVED)
        self.assertIsNotNone(proof.responded_at)
        self.assertTrue(any('approved' in m.subject for m in mail.outbox))

    def test_requesting_corrections_sends_it_back_to_production(self):
        submission = self._in_production()
        self._send_proof(submission)
        mail.outbox = []
        self.client.force_login(self.author)

        self.client.post(reverse('journal:proof_response', args=[submission.pk]), {
            'response': 'corrections',
            'corrections': 'Page 3, line 12: my affiliation is misspelt.',
        })

        submission.refresh_from_db()
        proof = submission.latest_proof
        self.assertEqual(submission.status, Submission.IN_PRODUCTION)
        self.assertEqual(proof.status, Proof.CORRECTIONS_REQUESTED)
        self.assertIn('misspelt', proof.corrections)
        self.assertTrue(any('corrections requested' in m.subject for m in mail.outbox))

    def test_asking_for_corrections_without_listing_them_is_rejected(self):
        submission = self._in_production()
        self._send_proof(submission)
        self.client.force_login(self.author)

        response = self.client.post(reverse('journal:proof_response', args=[submission.pk]), {
            'response': 'corrections',
            'corrections': '',
        })

        submission.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(submission.status, Submission.PROOF_REVIEW)

    def test_a_second_proof_supersedes_the_first(self):
        submission = self._in_production()
        self._send_proof(submission)
        first = submission.latest_proof

        self._send_proof(submission)

        first.refresh_from_db()
        submission.refresh_from_db()
        # Only one proof is ever live, so an author cannot approve a replaced one.
        self.assertEqual(first.status, Proof.SUPERSEDED)
        self.assertEqual(submission.latest_proof.version, 2)
        self.assertEqual(submission.proofs.filter(status=Proof.SENT).count(), 1)

    def test_only_the_author_and_editors_can_download_a_proof(self):
        submission = self._in_production()
        self._send_proof(submission)
        proof = submission.latest_proof
        url = reverse('journal:proof_file', args=[proof.pk])

        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.editor_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        intruder = CustomUser.objects.create_user(email='nosy2@example.com', password='pw-for-tests-only')
        self.client.force_login(intruder)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_a_reviewer_cannot_reach_the_copyedited_file(self):
        submission = self._in_production()
        self.pass_screening(submission)
        assignment = self.invite_reviewer(submission)
        assignment.accept()
        copyedited = SubmissionFile.objects.create(
            submission=submission, kind=SubmissionFile.PRODUCTION, file=a_file('copyedited.docx'),
        )

        response = self.client.get(
            reverse('journal:review_file', args=[assignment.token, copyedited.pk])
        )

        # The copyedited file carries the author names again.
        self.assertEqual(response.status_code, 404)

    def test_the_full_production_chain_ends_in_a_published_article(self):
        submission = self._in_production()
        self._send_proof(submission)
        self.client.force_login(self.author)
        self.client.post(reverse('journal:proof_response', args=[submission.pk]), {'response': 'approve'})

        issue = Issue.objects.create(volume=1, number=1, year=2026, is_published=True)
        self.client.force_login(self.editor_user)
        self.client.post(reverse('journal:publish', args=[submission.pk]), {
            'issue': issue.pk,
            'title': submission.title,
            'abstract': submission.abstract,
            'keywords': submission.keywords,
            'pdf': SimpleUploadedFile('final.pdf', b'%PDF-1.4', content_type='application/pdf'),
            'first_page': '1', 'last_page': '20',
            'licence': 'CC BY 4.0',
            'is_published': 'on',
            'authors-TOTAL_FORMS': '1', 'authors-INITIAL_FORMS': '0',
            'authors-MIN_NUM_FORMS': '1', 'authors-MAX_NUM_FORMS': '1000',
            'authors-0-first_name': 'Ada', 'authors-0-last_name': 'Obi',
        })

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.PUBLISHED)
        self.assertTrue(Article.objects.filter(submission=submission, is_published=True).exists())


class DiscoveryTestCase(JournalTestCase):
    """Fixtures for the indexing layer: one published article in an issue."""

    def setUp(self):
        super().setUp()
        self.journal.issn_online = '2756-1234'
        self.journal.contact_email = 'jeltan@eltanigeria.org'
        self.journal.save()

        self.issue = Issue.objects.create(volume=2, number=1, year=2026, is_published=True)
        self.article = Article.objects.create(
            title='Reading comprehension in multilingual classrooms',
            abstract='A study of reading in Nigerian secondary schools.',
            keywords='reading, multilingual, Nigeria',
            issue=self.issue, section=self.section, is_published=True,
            first_page=1, last_page=20, licence='CC BY 4.0',
        )
        ArticleAuthor.objects.create(
            article=self.article, first_name='Ada', last_name='Obi',
            affiliation='University of Lagos',
        )
        self.hidden = Article.objects.create(
            title='Not yet public', abstract='x', section=self.section, is_published=False,
        )


class OaiPmhTests(DiscoveryTestCase):
    """OAI-PMH is how DOAJ and other aggregators harvest the journal."""

    def _oai(self, **params):
        response = self.client.get(reverse('journal:oai'), params)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response['Content-Type'])
        return ET.fromstring(response.content)

    def _find(self, root, path):
        return root.findall(path, {'oai': 'http://www.openarchives.org/OAI/2.0/'})

    def test_identify_describes_the_repository(self):
        root = self._oai(verb='Identify')
        identify = self._find(root, 'oai:Identify')[0]

        self.assertEqual(identify.find('{*}repositoryName').text, self.journal.name)
        self.assertEqual(identify.find('{*}protocolVersion').text, '2.0')
        self.assertEqual(identify.find('{*}granularity').text, 'YYYY-MM-DDThh:mm:ssZ')
        self.assertEqual(identify.find('{*}adminEmail').text, 'jeltan@eltanigeria.org')

    def test_list_records_returns_published_articles_only(self):
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc')
        titles = [node.text for node in root.iter('{http://purl.org/dc/elements/1.1/}title')]

        self.assertIn(self.article.title, titles)
        self.assertNotIn('Not yet public', titles)

    def test_a_record_carries_the_dublin_core_a_harvester_needs(self):
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc')
        dc = 'http://purl.org/dc/elements/1.1/'

        creators = [n.text for n in root.iter(f'{{{dc}}}creator')]
        subjects = [n.text for n in root.iter(f'{{{dc}}}subject')]
        identifiers = [n.text for n in root.iter(f'{{{dc}}}identifier')]

        self.assertIn('Obi, Ada', creators)
        self.assertIn('reading', subjects)
        self.assertIn('multilingual', subjects)
        self.assertTrue(any(self.article.slug in i for i in identifiers))
        self.assertIn('CC BY 4.0', [n.text for n in root.iter(f'{{{dc}}}rights')])

    def test_get_record_returns_one_article(self):
        listed = self._oai(verb='ListRecords', metadataPrefix='oai_dc')
        identifier = next(listed.iter('{http://www.openarchives.org/OAI/2.0/}identifier')).text

        root = self._oai(verb='GetRecord', metadataPrefix='oai_dc', identifier=identifier)

        self.assertEqual(len(self._find(root, 'oai:GetRecord')), 1)
        self.assertIn(
            self.article.title,
            [n.text for n in root.iter('{http://purl.org/dc/elements/1.1/}title')],
        )

    def test_an_unpublished_article_cannot_be_fetched_by_identifier(self):
        root = self._oai(
            verb='GetRecord', metadataPrefix='oai_dc',
            identifier=f'oai:testserver:jeltan/{self.hidden.slug}',
        )
        self.assertEqual(self._find(root, 'oai:error')[0].get('code'), 'idDoesNotExist')

    def test_list_sets_exposes_the_journal_sections(self):
        root = self._oai(verb='ListSets')
        specs = [n.text for n in root.iter('{http://www.openarchives.org/OAI/2.0/}setSpec')]
        self.assertIn(self.section.slug, specs)

    def test_harvesting_can_be_limited_to_a_set(self):
        other = Section.objects.create(name='Book Reviews')
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc', set=other.slug)
        self.assertEqual(self._find(root, 'oai:error')[0].get('code'), 'noRecordsMatch')

    def test_selective_harvesting_by_date(self):
        future = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc', **{'from': future})
        self.assertEqual(self._find(root, 'oai:error')[0].get('code'), 'noRecordsMatch')

        past = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc', **{'from': past})
        self.assertEqual(len(self._find(root, 'oai:error')), 0)

    def test_an_unknown_verb_is_a_bad_verb_error(self):
        root = self._oai(verb='Frobnicate')
        error = self._find(root, 'oai:error')[0]

        self.assertEqual(error.get('code'), 'badVerb')
        # The spec requires the request element to carry no attributes here.
        self.assertEqual(self._find(root, 'oai:request')[0].attrib, {})

    def test_an_unsupported_metadata_format_is_refused(self):
        root = self._oai(verb='ListRecords', metadataPrefix='marc21')
        self.assertEqual(self._find(root, 'oai:error')[0].get('code'), 'cannotDisseminateFormat')

    def test_a_missing_metadata_prefix_is_a_bad_argument(self):
        root = self._oai(verb='ListRecords')
        self.assertEqual(self._find(root, 'oai:error')[0].get('code'), 'badArgument')

    def test_a_resumption_token_cannot_be_combined_with_other_arguments(self):
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc', resumptionToken='x')
        self.assertEqual(self._find(root, 'oai:error')[0].get('code'), 'badArgument')

    def test_a_corrupt_resumption_token_is_rejected(self):
        root = self._oai(verb='ListRecords', resumptionToken='not-a-real-token')
        self.assertEqual(self._find(root, 'oai:error')[0].get('code'), 'badResumptionToken')

    def test_list_identifiers_returns_headers_without_metadata(self):
        root = self._oai(verb='ListIdentifiers', metadataPrefix='oai_dc')

        self.assertEqual(len(self._find(root, 'oai:ListIdentifiers/oai:header')), 1)
        self.assertEqual(len(list(root.iter('{http://purl.org/dc/elements/1.1/}title'))), 0)

    def test_the_endpoint_accepts_post_as_the_spec_requires(self):
        response = self.client.post(reverse('journal:oai'), {'verb': 'Identify'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'repositoryName', response.content)


class SitemapAndFeedTests(DiscoveryTestCase):
    def test_the_sitemap_lists_published_articles_and_pages(self):
        response = self.client.get(reverse('journal:django.contrib.sitemaps.views.sitemap'))
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.article.get_absolute_url(), body)
        self.assertIn(self.issue.get_absolute_url(), body)
        self.assertIn(reverse('journal:guidelines'), body)
        self.assertNotIn(self.hidden.get_absolute_url(), body)

    def test_the_articles_feed_carries_the_latest_articles(self):
        response = self.client.get(reverse('journal:articles_feed'))
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.article.title, body)
        self.assertNotIn('Not yet public', body)

    def test_the_atom_feed_renders(self):
        response = self.client.get(reverse('journal:articles_atom_feed'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.article.title, response.content.decode())

    def test_the_issues_feed_renders(self):
        response = self.client.get(reverse('journal:issues_feed'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.issue.label, response.content.decode())


class CitationExportTests(DiscoveryTestCase):
    def test_bibtex_downloads_as_a_file(self):
        response = self.client.get(
            reverse('journal:article_citation', args=[self.article.slug, 'bib'])
        )
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('x-bibtex', response['Content-Type'])
        self.assertIn(f'{self.article.slug}.bib', response['Content-Disposition'])
        self.assertIn('@article{obi2026reading', body)
        self.assertIn('author = {Obi, Ada}', body)
        self.assertIn('volume = {2}', body)
        self.assertIn('pages = {1--20}', body)

    def test_ris_downloads_as_a_file(self):
        response = self.client.get(
            reverse('journal:article_citation', args=[self.article.slug, 'ris'])
        )
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('TY  - JOUR', body)
        self.assertIn('AU  - Obi, Ada', body)
        self.assertIn('SP  - 1', body)
        self.assertIn('EP  - 20', body)
        self.assertTrue(body.rstrip().endswith('ER  -'))

    def test_bibtex_escapes_characters_that_would_break_it(self):
        self.article.title = 'Reading & writing: 100% of the {curriculum}'
        self.article.save()

        body = self.client.get(
            reverse('journal:article_citation', args=[self.article.slug, 'bib'])
        ).content.decode()

        self.assertIn(r'\&', body)
        self.assertIn(r'\%', body)
        self.assertIn(r'\{', body)

    def test_an_unpublished_article_has_no_citation(self):
        response = self.client.get(
            reverse('journal:article_citation', args=[self.hidden.slug, 'bib'])
        )
        self.assertEqual(response.status_code, 404)


class ArticleMetadataTests(DiscoveryTestCase):
    def test_the_article_page_carries_dublin_core_and_scholar_tags(self):
        response = self.client.get(reverse('journal:article_detail', args=[self.article.slug]))
        body = response.content.decode()

        for tag in ['DC.title', 'DC.creator', 'DC.publisher', 'DC.rights',
                    'citation_title', 'citation_author', 'citation_issn']:
            with self.subTest(tag=tag):
                self.assertIn(tag, body)

    def test_each_keyword_gets_its_own_subject_tag(self):
        response = self.client.get(reverse('journal:article_detail', args=[self.article.slug]))
        body = response.content.decode()

        self.assertIn('<meta name="DC.subject" content="reading">', body)
        self.assertIn('<meta name="DC.subject" content="multilingual">', body)

    def test_pages_advertise_the_feed(self):
        response = self.client.get(reverse('journal:home'))
        self.assertIn('application/rss+xml', response.content.decode())


class OaiResumptionTests(DiscoveryTestCase):
    """Paging a harvest across several requests.

    Exercised with a page size of one, because a journal small enough to fit in
    a single page never tests the branch a large one depends on.
    """

    def _oai(self, **params):
        return ET.fromstring(self.client.get(reverse('journal:oai'), params).content)

    def _find(self, root, path):
        return root.findall(path, {'oai': 'http://www.openarchives.org/OAI/2.0/'})

    def setUp(self):
        super().setUp()
        for index in range(2):
            article = Article.objects.create(
                title=f'Second study number {index}', abstract='x',
                section=self.section, issue=self.issue, is_published=True,
            )
            ArticleAuthor.objects.create(article=article, first_name='Ngozi', last_name='Eze')

    @patch('journal.oai.PAGE_SIZE', 1)
    def test_a_harvest_pages_through_every_article(self):
        harvested = []
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc')

        for _ in range(10):  # generous bound; the loop breaks when the token runs out
            harvested += [n.text for n in root.iter('{http://purl.org/dc/elements/1.1/}title')]
            tokens = self._find(root, 'oai:ListRecords/oai:resumptionToken')
            if not tokens or not tokens[0].text:
                break
            root = self._oai(verb='ListRecords', resumptionToken=tokens[0].text)

        self.assertEqual(len(harvested), 3)
        self.assertIn(self.article.title, harvested)
        self.assertEqual(len(set(harvested)), 3, 'an article was harvested twice')

    @patch('journal.oai.PAGE_SIZE', 1)
    def test_the_token_reports_the_total_and_the_cursor(self):
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc')
        token = self._find(root, 'oai:ListRecords/oai:resumptionToken')[0]

        self.assertEqual(token.get('completeListSize'), '3')
        self.assertEqual(token.get('cursor'), '0')

    @patch('journal.oai.PAGE_SIZE', 1)
    def test_a_token_carries_the_original_filters(self):
        root = self._oai(verb='ListRecords', metadataPrefix='oai_dc', set=self.section.slug)
        token = self._find(root, 'oai:ListRecords/oai:resumptionToken')[0].text

        # Resuming must stay inside the set the harvest started with.
        resumed = self._oai(verb='ListRecords', resumptionToken=token)
        self.assertEqual(len(self._find(resumed, 'oai:error')), 0)
        self.assertEqual(len(self._find(resumed, 'oai:ListRecords/oai:record')), 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PortalTests(JournalTestCase):
    """The editorial portal: the cross-manuscript view of decisions and work."""

    def url(self, **params):
        base = reverse('journal:editor_portal')
        if not params:
            return base
        return base + '?' + '&'.join(f'{key}={value}' for key, value in params.items())

    def test_an_author_cannot_reach_the_portal(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_an_editor_reaches_the_portal(self):
        self.client.force_login(self.editor_user)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_a_site_administrator_reaches_the_portal_without_a_journal_role(self):
        """Admins hold the journal's records whether or not anyone gave them a role."""
        admin_user = CustomUser.objects.create_user(
            email='admin@example.com', password='pw-for-tests-only',
            first_name='Ngozi', last_name='Adaora',
        )
        admin_user.is_staff = True
        admin_user.save()

        self.assertFalse(JournalRole.objects.filter(user=admin_user).exists())
        self.client.force_login(admin_user)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_the_portal_lists_work_waiting_on_the_editorial_office(self):
        self.make_submission()  # awaiting screening
        self.make_submission(status=Submission.EDITORIAL_SCREENING)
        self.client.force_login(self.editor_user)

        lanes = {lane['key']: lane for lane in self.client.get(self.url()).context['lanes']}

        self.assertEqual(lanes['screening']['count'], 1)
        self.assertEqual(lanes['decision']['count'], 1)

    def test_a_manuscript_with_the_author_is_not_queued_for_a_decision(self):
        # Chasing an author is a different job from clearing the office queue,
        # and mixing them in is how a queue stops meaning anything. Ownership is
        # the exception: an open paper nobody owns is the office's problem
        # whoever happens to be holding it.
        submission = self.make_submission(status=Submission.MAJOR_REVISION)
        self.client.force_login(self.editor_user)

        lanes = {lane['key']: lane for lane in self.client.get(self.url()).context['lanes']}
        self.assertEqual(lanes['screening']['count'], 0)
        self.assertEqual(lanes['decision']['count'], 0)
        self.assertEqual(lanes['overdue']['count'], 0)
        self.assertEqual(lanes['unassigned']['count'], 1)

        submission.handling_editor = self.editor_user
        submission.save(update_fields=['handling_editor'])
        lanes = {lane['key']: lane for lane in self.client.get(self.url()).context['lanes']}
        self.assertEqual(sum(lane['count'] for lane in lanes.values()), 0)

    def test_the_decision_log_can_be_filtered(self):
        first = self.make_submission(status=Submission.UNDER_REVIEW)
        second = self.make_submission(status=Submission.UNDER_REVIEW)
        EditorialDecision.objects.create(
            submission=first, decision=EditorialDecision.ACCEPT, editor=self.editor_user,
        )
        EditorialDecision.objects.create(
            submission=second, decision=EditorialDecision.REJECT, editor=self.editor_user,
        )
        self.client.force_login(self.editor_user)

        response = self.client.get(self.url(decision=EditorialDecision.ACCEPT))
        rows = list(response.context['decisions'])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].submission_id, first.pk)

    def test_the_acceptance_rate_counts_only_settled_papers(self):
        accepted = self.make_submission(status=Submission.UNDER_REVIEW)
        rejected = self.make_submission(status=Submission.UNDER_REVIEW)
        revising = self.make_submission(status=Submission.UNDER_REVIEW)
        EditorialDecision.objects.create(submission=accepted, decision=EditorialDecision.ACCEPT)
        EditorialDecision.objects.create(submission=rejected, decision=EditorialDecision.REJECT)
        # Still live, so it must not be read as a rejection.
        EditorialDecision.objects.create(
            submission=revising, decision=EditorialDecision.MAJOR_REVISION,
        )
        self.client.force_login(self.editor_user)

        statistics = self.client.get(self.url()).context['statistics']

        self.assertEqual(statistics['settled'], 2)
        self.assertEqual(statistics['acceptance_rate'], 50)

    def test_the_portal_survives_an_empty_journal(self):
        self.client.force_login(self.editor_user)
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['statistics']['acceptance_rate'])
        self.assertIsNone(response.context['statistics']['median_days'])


class AdminAccessTests(TestCase):
    """The Django admin's way into the editorial portal.

    Administrators hold the journal's records and are the people who fix them,
    so the admin has to point at the workflow rather than quietly duplicating it.
    """

    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            email='root@example.com', password='pw-for-tests-only',
            first_name='Root', last_name='User', gender='female',
        )
        self.client.force_login(self.admin)

    def test_the_settings_page_links_to_the_portal(self):
        settings_row = JournalSettings.load()
        response = self.client.get(
            reverse('admin:journal_journalsettings_change', args=[settings_row.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('journal:editor_portal'))

    def test_decisions_are_browsable_but_not_creatable_in_the_admin(self):
        # Recording a decision here would move no manuscript and send no letter,
        # so the author would never learn of it.
        self.assertEqual(
            self.client.get(reverse('admin:journal_editorialdecision_changelist')).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('admin:journal_editorialdecision_add')).status_code,
            403,
        )


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DirectPublicationTests(JournalTestCase):
    """Loading an article that was already reviewed, without a manuscript."""

    def setUp(self):
        super().setUp()
        self.section_editor = CustomUser.objects.create_user(
            email='section@example.com', password='pw-for-tests-only',
            first_name='Tunde', last_name='Adeyemi',
        )
        JournalRole.objects.create(user=self.section_editor, role=JournalRole.EDITOR)

    def payload(self, **overrides):
        fields = {
            'section': self.section.pk,
            'title': 'Task repetition and oral fluency in Nigerian secondary schools',
            'abstract': 'An abstract of the already-reviewed paper.',
            'keywords': 'fluency, task repetition',
            'source_file': SimpleUploadedFile(
                'article.docx', a_docx(PAPER_LINES),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ),
            'first_page': '44',
            'last_page': '61',
            'doi': '10.1234/jeltan.2024.7',
            'licence': 'CC BY 4.0',
            'is_published': 'on',
            'notify_authors': 'on',
            'authors-TOTAL_FORMS': '1',
            'authors-INITIAL_FORMS': '0',
            'authors-MIN_NUM_FORMS': '1',
            'authors-MAX_NUM_FORMS': '1000',
            'authors-0-first_name': 'Ada',
            'authors-0-last_name': 'Obi',
            'authors-0-affiliation': 'University of Lagos',
            'authors-0-email': 'author@example.com',
        }
        fields.update(overrides)
        return {key: value for key, value in fields.items() if value is not None}

    def test_an_article_can_be_published_without_a_manuscript(self):
        self.client.force_login(self.editor_user)

        response = self.client.post(reverse('journal:article_create'), self.payload())

        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(doi='10.1234/jeltan.2024.7')
        self.assertTrue(article.is_published)
        self.assertIsNone(article.submission)
        self.assertFalse(article.was_reviewed_here)
        self.assertEqual(article.authors.count(), 1)
        self.assertEqual(article.page_range, '44–61')

    def test_the_person_who_loaded_it_is_recorded(self):
        # Nothing else in the record can show who vouched for an article that
        # skipped review.
        self.client.force_login(self.editor_user)
        self.client.post(reverse('journal:article_create'), self.payload())

        self.assertEqual(Article.objects.get().added_by, self.editor_user)

    def test_a_directly_published_article_is_publicly_readable(self):
        self.client.force_login(self.editor_user)
        self.client.post(reverse('journal:article_create'), self.payload())
        article = Article.objects.get()

        self.client.logout()
        response = self.client.get(reverse('journal:article_detail', args=[article.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Task repetition')

    def test_a_back_issue_keeps_the_date_it_was_actually_published(self):
        # An article from 2019 dated today would misstate the record and sort
        # to the top of every list of recent work.
        self.client.force_login(self.editor_user)
        self.client.post(reverse('journal:article_create'), self.payload(
            publication_date='2019-06-14', notify_authors=None,
        ))

        article = Article.objects.get()
        self.assertEqual(article.published_at.date().isoformat(), '2019-06-14')

    def test_a_back_issue_does_not_email_authors_years_later(self):
        self.client.force_login(self.editor_user)
        self.client.post(reverse('journal:article_create'), self.payload(
            publication_date='2019-06-14', notify_authors=None,
        ))

        self.assertEqual(mail.outbox, [])

    def test_publishing_now_tells_the_authors(self):
        self.client.force_login(self.editor_user)
        self.client.post(reverse('journal:article_create'), self.payload())

        self.assertTrue(any('Published' in m.subject for m in mail.outbox))
        self.assertIn('author@example.com', mail.outbox[0].to)

    def test_an_article_can_be_staged_without_going_public(self):
        self.client.force_login(self.editor_user)
        self.client.post(reverse('journal:article_create'), self.payload(is_published=None))

        article = Article.objects.get()
        self.assertFalse(article.is_published)
        self.assertIsNone(article.published_at)
        self.assertEqual(mail.outbox, [])

    def test_a_section_is_required_so_the_article_is_harvestable(self):
        self.client.force_login(self.editor_user)
        response = self.client.post(reverse('journal:article_create'), self.payload(section=None))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.exists())

    def test_an_article_cannot_go_public_without_a_file(self):
        self.client.force_login(self.editor_user)
        response = self.client.post(reverse('journal:article_create'), self.payload(source_file=None))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.exists())

    def test_save_and_add_another_carries_the_issue_over(self):
        # Loading an issue is loading a run of articles.
        issue = Issue.objects.create(volume=2, number=1, year=2026)
        self.client.force_login(self.editor_user)

        response = self.client.post(
            reverse('journal:article_create'),
            self.payload(issue=issue.pk, save_and_add='1'),
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f'issue={issue.pk}', response.url)
        self.assertIn(f'section={self.section.pk}', response.url)

    def test_a_section_editor_cannot_publish_without_review(self):
        # Skipping peer review is not a section editor's call.
        self.client.force_login(self.section_editor)

        self.assertEqual(self.client.get(reverse('journal:article_create')).status_code, 404)
        self.assertEqual(self.client.post(reverse('journal:article_create'), self.payload()).status_code, 404)
        self.assertFalse(Article.objects.exists())

    def test_an_author_cannot_reach_the_article_pages(self):
        self.client.force_login(self.author)

        self.assertEqual(self.client.get(reverse('journal:editor_articles')).status_code, 404)
        self.assertEqual(self.client.get(reverse('journal:article_create')).status_code, 404)

    def test_a_site_administrator_can_publish_without_a_journal_role(self):
        admin_user = CustomUser.objects.create_user(
            email='admin2@example.com', password='pw-for-tests-only',
            first_name='Ngozi', last_name='Adaora',
        )
        admin_user.is_staff = True
        admin_user.save()
        self.client.force_login(admin_user)

        self.client.post(reverse('journal:article_create'), self.payload())

        self.assertEqual(Article.objects.get().added_by, admin_user)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ArticleEditingTests(JournalTestCase):
    """Correcting the published record after the fact."""

    def edit_payload(self, article, **overrides):
        fields = {
            'section': article.section_id,
            'title': article.title,
            'abstract': article.abstract,
            'keywords': article.keywords,
            'licence': article.licence,
            'is_published': 'on' if article.is_published else None,
            # A human editing in the browser sees this ticked, so the tests post
            # it ticked: what stops a second email must be the transition guard,
            # not an editor remembering to untick a box.
            'notify_authors': 'on',
            'first_page': article.first_page or '',
            'last_page': article.last_page or '',
            'doi': article.doi,
            'authors-TOTAL_FORMS': '1',
            'authors-INITIAL_FORMS': '0',
            'authors-MIN_NUM_FORMS': '1',
            'authors-MAX_NUM_FORMS': '1000',
            'authors-0-first_name': 'Ada',
            'authors-0-last_name': 'Obi',
            'authors-0-email': 'author@example.com',
        }
        fields.update(overrides)
        return {key: value for key, value in fields.items() if value is not None}

    def make_article(self, **overrides):
        fields = {
            'title': 'Talk in the classroom', 'abstract': 'An abstract.',
            'section': self.section, 'is_published': True, 'licence': 'CC BY 4.0',
            'pdf': SimpleUploadedFile('a.pdf', b'%PDF-1.4', content_type='application/pdf'),
        }
        fields.update(overrides)
        return Article.objects.create(**fields)

    def test_metadata_can_be_corrected_without_re_emailing_the_authors(self):
        article = self.make_article()
        self.client.force_login(self.editor_user)
        mail.outbox = []

        self.client.post(
            reverse('journal:article_edit', args=[article.pk]),
            self.edit_payload(article, first_page='7', last_page='24'),
        )

        article.refresh_from_db()
        self.assertEqual(article.page_range, '7–24')
        # The authors were told when it went live; a page-number fix is not news.
        self.assertEqual(mail.outbox, [])

    def test_taking_a_staged_article_live_closes_its_manuscript(self):
        submission = self.make_submission(status=Submission.IN_PRODUCTION)
        article = self.make_article(is_published=False, submission=submission)
        self.client.force_login(self.editor_user)

        self.client.post(
            reverse('journal:article_edit', args=[article.pk]),
            self.edit_payload(article, is_published='on'),
        )

        article.refresh_from_db()
        submission.refresh_from_db()
        self.assertTrue(article.is_published)
        # Otherwise the author's own page still says "in production".
        self.assertEqual(submission.status, Submission.PUBLISHED)
        self.assertTrue(any('Published' in m.subject for m in mail.outbox))

    def test_the_article_list_separates_the_two_routes_in(self):
        submission = self.make_submission(status=Submission.PUBLISHED)
        self.make_article(submission=submission)
        self.make_article(title='Loaded by hand', added_by=self.editor_user)
        self.client.force_login(self.editor_user)

        response = self.client.get(reverse('journal:editor_articles') + '?show=direct')

        self.assertEqual(len(response.context['articles']), 1)
        self.assertEqual(response.context['counts']['direct'], 1)

    def test_editing_one_author_does_not_scramble_the_byline(self):
        """The byline is the article's credit — a page-number fix must not reorder it."""
        article = self.make_article()
        first = ArticleAuthor.objects.create(
            article=article, first_name='Ada', last_name='Obi', order=0,
        )
        second = ArticleAuthor.objects.create(
            article=article, first_name='Chidi', last_name='Eze', order=1,
        )
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:article_edit', args=[article.pk]), self.edit_payload(
            article,
            **{
                'authors-TOTAL_FORMS': '2',
                'authors-INITIAL_FORMS': '2',
                # Author one is posted back exactly as it stands, so the
                # formset reports only author two as changed — which is the case
                # that used to renumber the changed author to position one.
                'authors-0-id': first.pk,
                'authors-0-article': article.pk,
                'authors-0-first_name': 'Ada',
                'authors-0-last_name': 'Obi',
                'authors-0-email': '',
                'authors-1-id': second.pk,
                'authors-1-article': article.pk,
                'authors-1-first_name': 'Chidi',
                'authors-1-last_name': 'Eze',
                'authors-1-email': '',
                'authors-1-affiliation': 'Bayero University',
            },
        ))

        self.assertEqual(article.author_list, 'Ada Obi, Chidi Eze')
        second.refresh_from_db()
        self.assertEqual(second.affiliation, 'Bayero University')
        self.assertEqual(second.order, 1)

    def test_an_author_can_be_removed_from_the_byline(self):
        article = self.make_article()
        first = ArticleAuthor.objects.create(
            article=article, first_name='Ada', last_name='Obi', order=0,
        )
        second = ArticleAuthor.objects.create(
            article=article, first_name='Chidi', last_name='Eze', order=1,
        )
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:article_edit', args=[article.pk]), self.edit_payload(
            article,
            **{
                'authors-TOTAL_FORMS': '2',
                'authors-INITIAL_FORMS': '2',
                'authors-0-id': first.pk,
                'authors-0-article': article.pk,
                'authors-0-first_name': 'Ada',
                'authors-0-last_name': 'Obi',
                'authors-0-DELETE': 'on',
                'authors-1-id': second.pk,
                'authors-1-article': article.pk,
                'authors-1-first_name': 'Chidi',
                'authors-1-last_name': 'Eze',
            },
        ))

        # The remaining author moves up rather than keeping a gap at position 0.
        self.assertEqual(article.author_list, 'Chidi Eze')
        second.refresh_from_db()
        self.assertEqual(second.order, 0)


def a_docx(paragraphs, title=''):
    """A real .docx — a zip of the XML Word writes — built without a library."""
    import io
    import zipfile

    body = ''.join(
        '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % line.replace('&', '&amp;')
        for line in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}</w:body></w:document>'
    )
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title>{title}</dc:title></cp:coreProperties>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('word/document.xml', document)
        archive.writestr('docProps/core.xml', core)
    return buffer.getvalue()


def a_pdf(lines):
    """A minimal single-page PDF whose text pypdf can actually extract."""
    import io

    from pypdf import PdfWriter

    try:
        from reportlab.pdfgen import canvas
    except ImportError:                      # pragma: no cover - optional
        return None

    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    y = 800
    for line in lines:
        page.drawString(60, y, line)
        y -= 20
    page.save()
    buffer.seek(0)
    writer = PdfWriter(clone_from=buffer)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


PAPER_LINES = [
    'Task repetition and oral fluency in Nigerian secondary schools',
    'Ada Obi, Chidi Eze',
    'University of Lagos',
    'Abstract',
    'This study examines whether repeating a speaking task improves the oral '
    'fluency of senior secondary students in Lagos. Sixty learners took part '
    'over one term, and the results point to a modest but consistent gain.',
    'Keywords: task repetition, oral fluency, secondary school',
    'Introduction',
    'Fluency has long been treated as a by-product of practice.',
]


class IngestTests(TestCase):
    """Reading a paper's front matter. Every result is a guess, so it must be a
    careful one: a wrong author in the record is worse than a blank field."""

    def extract_docx(self, lines, title=''):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from journal import ingest
        return ingest.extract(SimpleUploadedFile(
            'paper.docx', a_docx(lines, title=title),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ))

    def test_a_word_file_gives_up_its_front_matter(self):
        found = self.extract_docx(PAPER_LINES)

        self.assertEqual(found.title, PAPER_LINES[0])
        self.assertIn('oral fluency of senior secondary students', found.abstract)
        self.assertEqual(found.keywords, 'task repetition, oral fluency, secondary school')
        self.assertEqual(found.authors, [('Ada', 'Obi'), ('Chidi', 'Eze')])

    def test_the_abstract_stops_where_the_paper_does(self):
        found = self.extract_docx(PAPER_LINES)

        # Running on into the introduction would put the paper's opening line
        # into the abstract on the public page.
        self.assertNotIn('by-product of practice', found.abstract)
        self.assertNotIn('Keywords', found.abstract)

    def test_an_affiliation_is_never_read_as_a_byline(self):
        found = self.extract_docx([
            'A study of classroom talk',
            'Department of English, University of Lagos',
            'Abstract',
            'A long enough abstract to be believed by the reader of this test suite.',
        ])

        self.assertEqual(found.authors, [])

    def test_a_word_title_property_of_a_filename_is_ignored(self):
        # Word stamps "Microsoft Word - draft.doc" into the title of anything
        # printed from it, which is not the paper's title.
        found = self.extract_docx(PAPER_LINES, title='Microsoft Word - paper draft 3.doc')

        self.assertEqual(found.title, PAPER_LINES[0])

    def test_the_document_title_property_is_used_when_it_is_real(self):
        found = self.extract_docx(PAPER_LINES, title='A Better Title From The Properties')

        self.assertEqual(found.title, 'A Better Title From The Properties')

    def test_an_unreadable_file_still_yields_a_title_from_its_name(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from journal import ingest
        found = ingest.extract(SimpleUploadedFile(
            'Task_repetition-and-oral-fluency_final.docx', b'this is not a zip',
        ))

        self.assertEqual(found.title, 'Task repetition and oral fluency')
        self.assertTrue(found.error)

    def test_the_file_can_still_be_saved_after_being_read(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from journal import ingest
        uploaded = SimpleUploadedFile('paper.docx', a_docx(PAPER_LINES))
        ingest.extract(uploaded)

        # Reading for metadata must not consume the upload — the same file is
        # about to become the galley.
        self.assertEqual(uploaded.tell(), 0)
        self.assertTrue(uploaded.read())

    def test_a_pdf_gives_up_its_front_matter(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from journal import ingest
        content = a_pdf(PAPER_LINES)
        if content is None:
            self.skipTest('reportlab is not installed')

        found = ingest.extract(SimpleUploadedFile(
            'paper.pdf', content, content_type='application/pdf',
        ))

        self.assertEqual(found.title, PAPER_LINES[0])
        self.assertIn('oral fluency', found.abstract)
        self.assertEqual(found.authors, [('Ada', 'Obi'), ('Chidi', 'Eze')])


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ArticleImportTests(JournalTestCase):
    """Uploading a folder of ready papers and publishing them as a batch."""

    def setUp(self):
        super().setUp()
        self.section_editor = CustomUser.objects.create_user(
            email='section2@example.com', password='pw-for-tests-only',
            first_name='Tunde', last_name='Adeyemi',
        )
        JournalRole.objects.create(user=self.section_editor, role=JournalRole.EDITOR)
        self.issue = Issue.objects.create(volume=3, number=1, year=2026)

    def docx(self, name, lines=None, title=''):
        return SimpleUploadedFile(
            name, a_docx(lines or PAPER_LINES, title=title),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )

    def upload(self, files, **overrides):
        data = {
            'section': self.section.pk,
            'issue': self.issue.pk,
            'licence': 'CC BY 4.0',
            'files': files,
        }
        data.update(overrides)
        self.client.force_login(self.editor_user)
        return self.client.post(reverse('journal:article_import'), data)

    def review_payload(self, articles, per_row=None):
        """The review formset, posted back unchanged unless a row says otherwise."""
        per_row = per_row or {}
        data = {
            'rows-TOTAL_FORMS': str(len(articles)),
            'rows-INITIAL_FORMS': str(len(articles)),
            'rows-MIN_NUM_FORMS': '0',
            'rows-MAX_NUM_FORMS': '1000',
        }
        for index, article in enumerate(articles):
            data.update({
                f'rows-{index}-id': article.pk,
                f'rows-{index}-title': article.title,
                f'rows-{index}-authors': article.author_list,
                f'rows-{index}-abstract': article.abstract,
                f'rows-{index}-keywords': article.keywords,
                f'rows-{index}-section': article.section_id or '',
                f'rows-{index}-issue': article.issue_id or '',
                f'rows-{index}-first_page': article.first_page or '',
                f'rows-{index}-last_page': article.last_page or '',
                f'rows-{index}-doi': article.doi,
            })
            data.update({f'rows-{index}-{key}': value for key, value in per_row.get(index, {}).items()})
        return {key: value for key, value in data.items() if value is not None}

    # --- step one ---------------------------------------------------------

    def test_several_files_become_one_staged_article_each(self):
        response = self.upload([
            self.docx('first-paper.docx'),
            self.docx('second-paper.docx'),
            self.docx('third-paper.docx'),
        ])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Article.objects.count(), 3)
        # Nothing is public until an editor has looked at the review screen.
        self.assertEqual(Article.objects.filter(is_published=True).count(), 0)
        self.assertEqual(len(set(Article.objects.values_list('import_batch', flat=True))), 1)

    def test_the_batch_carries_the_common_details_to_every_article(self):
        self.upload([self.docx('a.docx'), self.docx('b.docx')])

        for article in Article.objects.all():
            self.assertEqual(article.section, self.section)
            self.assertEqual(article.issue, self.issue)
            self.assertEqual(article.licence, 'CC BY 4.0')
            self.assertEqual(article.added_by, self.editor_user)

    def test_what_was_read_out_of_the_file_is_filled_in(self):
        self.upload([self.docx('a-paper.docx')])
        article = Article.objects.get()

        self.assertEqual(article.title, PAPER_LINES[0])
        self.assertIn('oral fluency', article.abstract)
        self.assertEqual(article.author_list, 'Ada Obi, Chidi Eze')

    def test_the_uploaded_file_is_kept_as_the_source(self):
        self.upload([self.docx('a-paper.docx')])
        article = Article.objects.get()

        # The manuscript is kept so the article can always be typeset again;
        # the galley is generated later, once the metadata has been confirmed.
        self.assertTrue(article.source_file)
        self.assertEqual(article.source_extension, '.docx')

    def test_an_unreadable_file_still_imports_under_its_filename(self):
        # A scanned PDF with no text layer must not lose the whole batch.
        response = self.upload([
            SimpleUploadedFile('Silent_reading_strategies.docx', b'not really a docx'),
        ])

        article = Article.objects.get()
        self.assertEqual(article.title, 'Silent reading strategies')
        self.assertContains(
            self.client.get(response.url), 'type the rest in', status_code=200,
        )

    def test_a_file_the_journal_cannot_open_is_refused(self):
        response = self.upload([SimpleUploadedFile('notes.txt', b'plain text')])

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.exists())

    def test_a_section_editor_cannot_import(self):
        self.client.force_login(self.section_editor)
        self.assertEqual(self.client.get(reverse('journal:article_import')).status_code, 404)

    # --- step two ---------------------------------------------------------

    def test_only_the_ticked_articles_go_public(self):
        self.upload([self.docx('a.docx'), self.docx('b.docx'), self.docx('c.docx')])
        articles = list(Article.objects.order_by('pk'))
        batch = articles[0].import_batch

        self.client.post(
            reverse('journal:article_import_review', args=[batch]),
            self.review_payload(articles, {0: {'publish': 'on'}, 2: {'publish': 'on'}}),
        )

        published = set(Article.objects.filter(is_published=True).values_list('pk', flat=True))
        self.assertEqual(published, {articles[0].pk, articles[2].pk})

    def test_corrections_on_the_review_screen_are_kept(self):
        self.upload([self.docx('a.docx')])
        article = Article.objects.get()

        self.client.post(
            reverse('journal:article_import_review', args=[article.import_batch]),
            self.review_payload([article], {0: {
                'title': 'The title the reader will actually see',
                'authors': 'Ngozi Adaora, Kunle Bello',
                'first_page': '12', 'last_page': '30',
                'publish': 'on',
            }}),
        )

        article.refresh_from_db()
        self.assertEqual(article.title, 'The title the reader will actually see')
        self.assertEqual(article.author_list, 'Ngozi Adaora, Kunle Bello')
        self.assertEqual(article.page_range, '12–30')
        self.assertTrue(article.is_published)

    def test_an_article_with_no_byline_cannot_be_published(self):
        # Publishing a paper with nobody credited is worse than leaving it staged.
        self.upload([self.docx('a.docx')])
        article = Article.objects.get()

        response = self.client.post(
            reverse('journal:article_import_review', args=[article.import_batch]),
            self.review_payload([article], {0: {'authors': '', 'publish': 'on'}}),
        )

        article.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(article.is_published)

    def test_an_unwanted_file_can_be_discarded(self):
        self.upload([self.docx('wanted.docx'), self.docx('unwanted.docx')])
        articles = list(Article.objects.order_by('pk'))
        batch = articles[0].import_batch

        self.client.post(
            reverse('journal:article_import_review', args=[batch]),
            self.review_payload(articles, {1: {'DELETE': 'on'}}),
        )

        self.assertEqual(Article.objects.count(), 1)
        self.assertEqual(Article.objects.get().pk, articles[0].pk)

    def test_a_discarded_row_is_not_held_up_by_its_own_blank_fields(self):
        self.upload([self.docx('unwanted.docx')])
        article = Article.objects.get()

        self.client.post(
            reverse('journal:article_import_review', args=[article.import_batch]),
            self.review_payload([article], {0: {'title': '', 'DELETE': 'on'}}),
        )

        self.assertFalse(Article.objects.exists())

    def test_a_published_batch_is_readable_by_the_public(self):
        self.upload([self.docx('a.docx')])
        article = Article.objects.get()
        self.client.post(
            reverse('journal:article_import_review', args=[article.import_batch]),
            self.review_payload([article], {0: {'publish': 'on'}}),
        )

        self.client.logout()
        article.refresh_from_db()
        response = self.client.get(reverse('journal:article_detail', args=[article.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ada Obi')

    def test_publishing_a_batch_typesets_every_article(self):
        self.upload([self.docx('a.docx')])
        article = Article.objects.get()
        self.client.post(
            reverse('journal:article_import_review', args=[article.import_batch]),
            self.review_payload([article], {0: {'publish': 'on'}}),
        )
        article.refresh_from_db()

        self.assertTrue(article.is_typeset)
        self.assertEqual(article.galley_extension, '.pdf')
        response = self.client.get(reverse('journal:article_pdf', args=[article.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('.pdf', response['Content-Disposition'])

    def test_a_missing_batch_says_so_rather_than_erroring(self):
        self.client.force_login(self.editor_user)
        response = self.client.get(
            reverse('journal:article_import_review', args=['00000000-0000-0000-0000-000000000000'])
        )

        self.assertEqual(response.status_code, 302)


def a_structured_docx(paragraphs):
    """A .docx with real Word styles — paragraphs are (text, style, bold)."""
    import io
    import zipfile

    body = ''
    for text, style, bold in paragraphs:
        properties = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
        run_properties = '<w:rPr><w:b/></w:rPr>' if bold else ''
        safe = text.replace('&', '&amp;').replace('<', '&lt;')
        body += (
            f'<w:p>{properties}<w:r>{run_properties}'
            f'<w:t xml:space="preserve">{safe}</w:t></w:r></w:p>'
        )
    document = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}</w:body></w:document>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('word/document.xml', document)
    return buffer.getvalue()


def a_real_pdf(lines):
    from pypdf import PdfWriter
    from reportlab.pdfgen import canvas
    import io

    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    y = 800
    for line in lines:
        page.drawString(60, y, line)
        y -= 20
    page.save()
    buffer.seek(0)
    writer = PdfWriter(clone_from=buffer)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


MANUSCRIPT = [
    ('Task repetition and oral fluency in Nigerian secondary schools', 'Title', False),
    ('Ada Obi, Chidi Eze', None, False),
    ('Abstract', None, True),
    ('This study examines whether repeating a speaking task improves oral fluency.', None, False),
    ('Introduction', 'Heading1', False),
    ('Fluency has long been treated as a by-product of practice rather than something '
     'that a teacher plans for directly, and this study asks whether that holds.', None, False),
    ('Method', None, True),
    ('Sixty senior secondary students in three Lagos schools took part over one term.', None, False),
    ('References', 'Heading1', False),
    ('Bygate, M. (2001). Effects of task repetition. Longman.', None, False),
]


class TypesettingTests(JournalTestCase):
    """Turning what an author supplied into the article the journal publishes."""

    def make_article(self, source, **overrides):
        fields = {
            'title': 'Task repetition and oral fluency in Nigerian secondary schools',
            'abstract': 'This study examines whether repeating a speaking task improves oral fluency.',
            'keywords': 'task repetition, oral fluency',
            'section': self.section, 'licence': 'CC BY 4.0', 'is_published': True,
            'source_file': source,
        }
        fields.update(overrides)
        article = Article.objects.create(**fields)
        ArticleAuthor.objects.create(
            article=article, first_name='Ada', last_name='Obi',
            affiliation='University of Lagos', order=0,
        )
        ArticleAuthor.objects.create(
            article=article, first_name='Chidi', last_name='Eze', order=1,
        )
        return article

    def a_manuscript(self, paragraphs=None, name='paper.docx'):
        return SimpleUploadedFile(
            name, a_structured_docx(paragraphs or MANUSCRIPT),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )

    # --- from a Word manuscript ------------------------------------------

    def test_a_manuscript_becomes_a_jeltan_galley(self):
        from journal import typeset

        article = self.make_article(self.a_manuscript())
        self.assertTrue(typeset.typeset(article))

        article.refresh_from_db()
        self.assertTrue(article.is_typeset)
        self.assertEqual(article.galley_extension, '.pdf')
        article.pdf.open('rb')
        try:
            self.assertTrue(article.pdf.read().startswith(b'%PDF'))
        finally:
            article.pdf.close()

    def test_the_structure_of_the_manuscript_survives(self):
        from journal import typeset

        article = self.make_article(self.a_manuscript())
        typeset.typeset(article)

        article.refresh_from_db()
        self.assertIn('<h2>Introduction</h2>', article.body_html)
        # A bold one-line paragraph is a heading in nearly every manuscript that
        # never learned to use Word's heading styles.
        self.assertIn('<h2>Method</h2>', article.body_html)
        self.assertIn('<p>Fluency has long been treated', article.body_html)

    def test_a_reference_list_is_marked_as_one(self):
        from journal import typeset

        article = self.make_article(self.a_manuscript())
        typeset.typeset(article)

        article.refresh_from_db()
        self.assertIn('<p class="reference">Bygate, M.', article.body_html)

    def test_the_manuscripts_own_title_page_is_not_printed_twice(self):
        from journal import typeset

        article = self.make_article(self.a_manuscript())
        typeset.typeset(article)

        article.refresh_from_db()
        # The template sets the title, byline and abstract itself.
        self.assertNotIn('Task repetition and oral fluency', article.body_html)
        self.assertNotIn('Ada Obi, Chidi Eze', article.body_html)

    def test_markup_in_a_manuscript_cannot_reach_the_page(self):
        from journal import typeset

        article = self.make_article(self.a_manuscript([
            ('Introduction', 'Heading1', False),
            ('An author pasted <script>alert(1)</script> in from a web page.', None, False),
        ]))
        typeset.typeset(article)

        article.refresh_from_db()
        self.assertNotIn('<script>', article.body_html)
        self.assertIn('&lt;script&gt;', article.body_html)

    def test_the_full_text_appears_on_the_article_page(self):
        from journal import typeset

        article = self.make_article(self.a_manuscript())
        typeset.typeset(article)
        article.refresh_from_db()

        response = self.client.get(reverse('journal:article_detail', args=[article.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Full text')
        self.assertContains(response, 'Fluency has long been treated')

    # --- from somebody else's PDF ----------------------------------------

    def test_a_supplied_pdf_keeps_its_pages_behind_a_jeltan_cover(self):
        import io

        from pypdf import PdfReader

        from journal import typeset

        source = SimpleUploadedFile(
            'paper.pdf', a_real_pdf(['Page one of the original', 'x' * 40]),
            content_type='application/pdf',
        )
        article = self.make_article(source)
        self.assertTrue(typeset.typeset(article))

        article.refresh_from_db()
        article.pdf.open('rb')
        try:
            # Read it out in full: pypdf seeks lazily, and the file is about to
            # be closed underneath it.
            content = io.BytesIO(article.pdf.read())
        finally:
            article.pdf.close()
        pages = PdfReader(content).pages

        # One cover page, then the author's own page, untouched.
        self.assertEqual(len(pages), 2)
        self.assertIn('Journal of ELTAN', pages[0].extract_text())
        self.assertIn('Page one of the original', pages[1].extract_text())

    def test_a_supplied_pdf_is_not_re_flowed_into_full_text(self):
        from journal import typeset

        article = self.make_article(SimpleUploadedFile(
            'paper.pdf', a_real_pdf(['Original typesetting']), content_type='application/pdf',
        ))
        typeset.typeset(article)

        article.refresh_from_db()
        # Text scraped out of a designed page makes a worse article than the
        # page it came from, so it is not offered as the full text.
        self.assertEqual(article.body_html, '')
        self.assertFalse(article.has_full_text)

    # --- when it cannot be done -------------------------------------------

    def test_a_broken_file_still_leaves_a_downloadable_article(self):
        from journal import typeset

        article = self.make_article(SimpleUploadedFile('paper.docx', b'not a zip at all'))

        self.assertFalse(typeset.typeset(article))
        article.refresh_from_db()
        self.assertTrue(article.pdf)
        self.assertFalse(article.is_typeset)
        self.assertIn('Could not typeset', article.typeset_note)

    # --- keeping the galley in step ---------------------------------------

    def test_correcting_the_title_regenerates_the_galley(self):
        import io

        from pypdf import PdfReader

        article = self.make_article(self.a_manuscript())
        self.client.force_login(self.editor_user)

        self.client.post(reverse('journal:article_edit', args=[article.pk]), {
            'section': self.section.pk,
            'title': 'A corrected title for the record',
            'abstract': article.abstract,
            'keywords': article.keywords,
            'licence': 'CC BY 4.0',
            'is_published': 'on',
            'authors-TOTAL_FORMS': '1', 'authors-INITIAL_FORMS': '0',
            'authors-MIN_NUM_FORMS': '1', 'authors-MAX_NUM_FORMS': '1000',
            'authors-0-first_name': 'Ada', 'authors-0-last_name': 'Obi',
        })

        article.refresh_from_db()
        article.pdf.open('rb')
        try:
            content = io.BytesIO(article.pdf.read())
        finally:
            article.pdf.close()
        printed = PdfReader(content).pages[0].extract_text()

        # A galley still carrying the old title is the version readers cite.
        self.assertIn('A corrected title', printed)

    def test_an_editor_can_generate_the_galley_again(self):
        article = self.make_article(self.a_manuscript())
        self.client.force_login(self.editor_user)

        response = self.client.post(reverse('journal:article_retypeset', args=[article.pk]))

        article.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(article.is_typeset)

    def test_a_section_editor_cannot_regenerate_a_galley(self):
        article = self.make_article(self.a_manuscript())
        editor = CustomUser.objects.create_user(
            email='section3@example.com', password='pw-for-tests-only',
            first_name='Tunde', last_name='Adeyemi',
        )
        JournalRole.objects.create(user=editor, role=JournalRole.EDITOR)
        self.client.force_login(editor)

        response = self.client.post(reverse('journal:article_retypeset', args=[article.pk]))
        self.assertEqual(response.status_code, 404)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GenerateFromDocumentTests(JournalTestCase):
    """One document in, one whole article out, checked before it goes public."""

    def setUp(self):
        super().setUp()
        self.issue = Issue.objects.create(volume=4, number=1, year=2026)

    def upload(self, paragraphs=None, name='paper.docx', **overrides):
        data = {
            'section': self.section.pk,
            'issue': self.issue.pk,
            'licence': 'CC BY 4.0',
            'document': SimpleUploadedFile(
                name, a_structured_docx(paragraphs or MANUSCRIPT),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ),
        }
        data.update(overrides)
        self.client.force_login(self.editor_user)
        return self.client.post(reverse('journal:article_from_document'), data)

    def test_a_document_becomes_a_whole_article(self):
        response = self.upload()

        article = Article.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(article.title, MANUSCRIPT[0][0])
        self.assertIn('repeating a speaking task', article.abstract)
        self.assertEqual(article.author_list, 'Ada Obi, Chidi Eze')
        self.assertEqual(article.section, self.section)
        self.assertEqual(article.issue, self.issue)
        self.assertEqual(article.added_by, self.editor_user)

    def test_the_sections_come_through_and_are_typeset(self):
        self.upload()
        article = Article.objects.get()

        self.assertTrue(article.is_typeset)
        self.assertTrue(article.has_full_text)
        self.assertIn('<h2>Introduction</h2>', article.body_html)
        self.assertIn('<h2>Method</h2>', article.body_html)

    def test_nothing_is_public_until_it_has_been_checked(self):
        self.upload()
        article = Article.objects.get()

        self.assertFalse(article.is_published)
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse('journal:article_detail', args=[article.slug])).status_code,
            404,
        )

    def test_the_check_page_lists_the_sections_that_were_found(self):
        self.upload()
        article = Article.objects.get()

        response = self.client.get(reverse('journal:article_generated', args=[article.pk]))

        outline = [heading['text'] for heading in response.context['outline']]
        self.assertEqual(response.status_code, 200)
        self.assertIn('Introduction', outline)
        self.assertIn('Method', outline)
        self.assertIn('References', outline)

    def test_a_document_with_no_headings_says_so_rather_than_inventing_them(self):
        self.upload([
            ('A study of classroom talk in three schools', 'Title', False),
            ('Ada Obi', None, False),
            ('This paper runs on without a single heading in it, as some do, and the '
             'reader of the check page needs to be told that rather than shown an '
             'outline that was guessed at.', None, False),
        ])
        article = Article.objects.get()

        response = self.client.get(reverse('journal:article_generated', args=[article.pk]))

        self.assertEqual(response.context['outline'], [])
        self.assertContains(response, 'No headings were detected')

    def test_corrections_reach_both_the_record_and_the_galley(self):
        import io

        from pypdf import PdfReader

        self.upload()
        article = Article.objects.get()

        self.client.post(reverse('journal:article_generated', args=[article.pk]), {
            'title': 'The title as it should have been read',
            'authors': 'Ngozi Adaora',
            'abstract': article.abstract,
            'keywords': article.keywords,
            'section': self.section.pk,
            'issue': self.issue.pk,
            'first_page': '5', 'last_page': '19', 'doi': '10.1234/jeltan.4.1',
            'publish': 'on',
        })

        article.refresh_from_db()
        self.assertEqual(article.title, 'The title as it should have been read')
        self.assertEqual(article.author_list, 'Ngozi Adaora')
        self.assertTrue(article.is_published)

        article.pdf.open('rb')
        try:
            content = io.BytesIO(article.pdf.read())
        finally:
            article.pdf.close()
        printed = PdfReader(content).pages[0].extract_text()
        self.assertIn('The title as it should have been read', printed)
        self.assertIn('Ngozi Adaora', printed)

    def test_publishing_needs_a_byline(self):
        self.upload([
            ('A paper with no byline anywhere in it', 'Title', False),
            ('Introduction', 'Heading1', False),
            ('The opening paragraph of a paper that never names its authors.', None, False),
        ])
        article = Article.objects.get()

        response = self.client.post(reverse('journal:article_generated', args=[article.pk]), {
            'title': article.title, 'authors': '', 'abstract': 'An abstract.',
            'keywords': '', 'section': self.section.pk, 'issue': '',
            'first_page': '', 'last_page': '', 'doi': '', 'publish': 'on',
        })

        article.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(article.is_published)

    def test_a_generated_article_can_be_discarded_with_its_file(self):
        # Posted with a blank title on purpose: a document whose details could
        # not be read is exactly the one an editor wants to throw away, and
        # having to type a title in first would be a trap.
        self.upload()
        article = Article.objects.get()

        self.client.post(reverse('journal:article_generated', args=[article.pk]), {
            'title': '', 'authors': '', 'abstract': '', 'keywords': '',
            'section': self.section.pk, 'issue': '',
            'first_page': '', 'last_page': '', 'doi': '', 'discard': '1',
        })

        self.assertFalse(Article.objects.exists())

    def test_a_pdf_gives_front_matter_but_no_invented_sections(self):
        self.client.force_login(self.editor_user)
        self.client.post(reverse('journal:article_from_document'), {
            'section': self.section.pk, 'licence': 'CC BY 4.0',
            'document': SimpleUploadedFile(
                'paper.pdf', a_real_pdf(['A paper someone else typeset']),
                content_type='application/pdf',
            ),
        })

        article = Article.objects.get()
        response = self.client.get(reverse('journal:article_generated', args=[article.pk]))

        self.assertFalse(article.has_full_text)
        self.assertContains(response, 'No full text was read')
        self.assertContains(response, 'own pages are kept as they are')

    def test_a_file_the_journal_cannot_open_is_refused(self):
        self.client.force_login(self.editor_user)
        response = self.client.post(reverse('journal:article_from_document'), {
            'section': self.section.pk, 'licence': 'CC BY 4.0',
            'document': SimpleUploadedFile('notes.txt', b'plain text'),
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.exists())

    def test_a_section_editor_cannot_generate_articles(self):
        editor = CustomUser.objects.create_user(
            email='section4@example.com', password='pw-for-tests-only',
            first_name='Tunde', last_name='Adeyemi',
        )
        JournalRole.objects.create(user=editor, role=JournalRole.EDITOR)
        self.client.force_login(editor)

        self.assertEqual(
            self.client.get(reverse('journal:article_from_document')).status_code, 404,
        )


class TypesetStorageTests(JournalTestCase):
    """What happens when the database will not take what was generated.

    The live database was built with latin1 as its default charset, which cannot
    store a curly apostrophe or a name spelled with a character English does not
    use. journal/migrations/0007_utf8mb4.py fixes that; these cover the case
    where a write fails anyway, because a 500 halfway through publishing is the
    worst of the outcomes available.
    """

    def make_article(self):
        article = Article.objects.create(
            title='Task repetition and oral fluency',
            abstract='An abstract.', section=self.section, licence='CC BY 4.0',
            source_file=SimpleUploadedFile(
                'paper.docx', a_structured_docx(MANUSCRIPT),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ),
        )
        ArticleAuthor.objects.create(article=article, first_name='Ada', last_name='Obi', order=0)
        return article

    def failing_save(self, times=1):
        """Patch Article.save so the first `times` calls fail as MySQL would."""
        from django.db import DataError

        real_save = Article.save
        calls = []

        def save(instance, *args, **kwargs):
            calls.append(1)
            if len(calls) <= times:
                raise DataError('(1366, "Incorrect string value: \'\\\\xC5\\\\x82\'")')
            return real_save(instance, *args, **kwargs)

        return save

    def test_a_body_the_database_refuses_does_not_lose_the_galley(self):
        from journal import typeset

        article = self.make_article()
        with patch.object(Article, 'save', self.failing_save(times=1)):
            result = typeset.typeset(article)

        article.refresh_from_db()
        self.assertFalse(result)
        # The PDF was written to storage before the database was touched, and it
        # is still what readers download.
        self.assertTrue(article.pdf)
        self.assertEqual(article.body_html, '')
        self.assertIn('full text could not be stored', article.typeset_note)

    def test_a_database_that_refuses_everything_does_not_raise(self):
        from journal import typeset

        article = self.make_article()
        with patch.object(Article, 'save', self.failing_save(times=99)):
            # A request must not die on the way out. The caller is told it
            # failed and decides what to say about it.
            self.assertFalse(typeset.typeset(article))

    def test_the_check_page_says_why_the_full_text_is_missing(self):
        from journal import typeset

        article = self.make_article()
        with patch.object(Article, 'save', self.failing_save(times=1)):
            typeset.typeset(article)

        self.client.force_login(self.editor_user)
        response = self.client.get(reverse('journal:article_generated', args=[article.pk]))

        self.assertContains(response, 'full text could not be stored')


# Polish, Igbo, Yorùbá and Hausa — every one of them outside Latin-1, and all of
# them ordinary in this journal's reference lists.
EXTENDED_LATIN = [
    ('Deconstructing colonial pedagogy and indigenous knowledge', 'Title', False),
    ('Introduction', 'Heading1', False),
    ('The epistemology of the formerly colonised nations (Jabłoński, 2021) is read '
     'here alongside Igbo and Yorùbá scholarship, with attention to Ndịigbo usage.', None, False),
    ('Yorùbá: ẹ ọ ṣ Ẹ Ọ Ṣ. Igbo: ị ọ ụ ṅ Ị Ọ Ụ Ṅ. Hausa: ɓ ɗ ƙ.', None, False),
    ('References', 'Heading1', False),
    ('Igboanụsị, H. S. (2002). A dictionary of Nigerian English usage. Enicrownfit.', None, False),
    ('Ụbahakwe, E. (ed.) (1979). The teaching of English studies.', None, False),
]


class GalleyGlyphTests(JournalTestCase):
    """Every character in the manuscript has to reach the page.

    PDF's built-in fonts carry WinAnsiEncoding, which stops at Latin-1, and
    reportlab draws a filled black box for anything it cannot set. A galley
    printing "Igboan■s■" for Igboanụsị misspells the author of a cited work, in
    the permanent record, in a journal published in Nigeria. The fix is the
    embedded fonts in journal/typeset.py; these keep them there.
    """

    def galley_text(self, article):
        import io

        from pypdf import PdfReader

        article.pdf.open('rb')
        try:
            content = io.BytesIO(article.pdf.read())
        finally:
            article.pdf.close()
        reader = PdfReader(content)
        return '\n'.join((page.extract_text() or '') for page in reader.pages), reader

    def make_article(self):
        article = Article.objects.create(
            title='Deconstructing colonial pedagogy: Ndịigbo and Jabłoński',
            abstract='A study of ìmọ̀ ìbílẹ̀ — indigenous knowledge — citing Igboanụsị.',
            keywords='ìmọ̀ ìbílẹ̀, Ndịigbo',
            section=self.section, licence='CC BY 4.0',
            source_file=SimpleUploadedFile(
                'paper.docx', a_structured_docx(EXTENDED_LATIN),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ),
        )
        ArticleAuthor.objects.create(
            article=article, first_name='Adéọlá', last_name='Ọbáfẹ́mi',
            affiliation='Yunifásítì ti Ìbàdàn', order=0,
        )
        return article

    def test_no_character_is_replaced_by_a_black_box(self):
        from journal import typeset

        article = self.make_article()
        self.assertTrue(typeset.typeset(article))

        text, _reader = self.galley_text(article)
        self.assertNotIn('■', text)

    def test_the_names_survive_into_the_galley(self):
        from journal import typeset

        article = self.make_article()
        typeset.typeset(article)
        text, _reader = self.galley_text(article)

        for name in ('Jabłoński', 'Igboanụsị', 'Ụbahakwe', 'Ọbáfẹ́mi', 'Ndịigbo'):
            self.assertIn(name, text, f'{name} did not reach the galley')

    def test_the_fonts_are_embedded_rather_than_assumed(self):
        from journal import typeset

        article = self.make_article()
        typeset.typeset(article)
        _text, reader = self.galley_text(article)

        embedded = set()
        for page in reader.pages:
            for _name, font in (page.get('/Resources', {}).get('/Font') or {}).items():
                embedded.add(str(font.get_object().get('/BaseFont')))

        # A reader on another machine has no copy of these, so the file has to
        # carry them.
        self.assertTrue(
            any('Charis' in name for name in embedded),
            f'no Charis face embedded, only {embedded}',
        )
        self.assertTrue(
            any('NotoSans' in name for name in embedded),
            f'no Noto Sans face embedded, only {embedded}',
        )

    def test_every_font_file_the_galley_asks_for_is_present(self):
        from journal import typeset

        # A missing file falls back silently to a font that cannot spell half
        # this journal's authors, so it is worth failing loudly here instead.
        self.assertEqual(len(typeset.font_faces()), len(typeset.FONT_FACES))
