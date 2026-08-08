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

    def test_before_screening_the_only_decision_is_to_reject(self):
        from journal.forms import DecisionForm

        submission = self.make_submission()  # awaiting administrative screening
        choices = [value for value, _ in DecisionForm(submission=submission).fields['decision'].choices]

        # A rejected paper never reaches a reviewer, so rejecting early is safe;
        # sending for review before the anonymity check is not.
        self.assertEqual(choices, [EditorialDecision.DESK_REJECT])

    def test_after_screening_the_paper_can_be_sent_for_review(self):
        from journal.forms import DecisionForm

        submission = self.make_submission(status=Submission.EDITORIAL_SCREENING)
        choices = [value for value, _ in DecisionForm(submission=submission).fields['decision'].choices]

        self.assertEqual(sorted(choices), sorted([
            EditorialDecision.SEND_FOR_REVIEW, EditorialDecision.DESK_REJECT,
        ]))

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
