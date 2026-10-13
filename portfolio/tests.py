import io
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from account.models import CustomUser
from events import services as event_services
from events.models import EventRegistration, EventSetup
from journal.models import Article, ArticleAuthor
from membership.models import Events

from . import sources
from .models import Achievement, PortfolioProfile, PortfolioSettings, PremiumGrant, has_premium


def pdf_text(data):
    from pypdf import PdfReader
    return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PortfolioTestCase(TestCase):
    def setUp(self):
        for setting in ('MEDIA_ROOT', 'PORTFOLIO_PRIVATE_ROOT'):
            folder = tempfile.mkdtemp(prefix='eltan-portfolio-tests-')
            self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
            override = override_settings(**{setting: folder})
            override.enable()
            self.addCleanup(override.disable)

        self.member = CustomUser.objects.create_user(
            email='ngozi@example.com', password='pw-for-tests-only', first_name='Ngọzị', last_name='Okafor',
        )
        self.client.force_login(self.member)

    def add_achievement(self, user=None, **fields):
        values = {
            'title': 'British Council: Teaching for Success', 'category': Achievement.COURSE,
            'provider': 'British Council', 'completed_on': timezone.localdate() - timedelta(days=10),
            'cpd_hours': Decimal('6'),
        }
        values.update(fields)
        return Achievement.objects.create(user=user or self.member, **values)

    def earn_event_certificate(self, hours=Decimal('2')):
        event = Events.objects.create(
            event_title='Teaching Reading Webinar', event_date=timezone.localdate() - timedelta(days=3),
            event_location='Online', event_desc='x',
        )
        EventSetup.objects.create(event=event, accepts_registrations=True, cpd_hours=hours, activity_is_open=True)
        registration = EventRegistration.objects.create(
            event=event, user=self.member, first_name='Ngọzị', last_name='Okafor', email=self.member.email,
        )
        registration.confirm()
        registration = EventRegistration.objects.get(pk=registration.pk)
        return event_services.complete_activity(
            registration, '', [(q, 'answer') for q in event.questions.all()],
        )


class RecordTests(PortfolioTestCase):
    def test_eltan_certificates_appear_verified_with_their_hours(self):
        certificate = self.earn_event_certificate()
        entries = sources.entries_for(self.member)

        event_entry = next(entry for entry in entries if entry.source == 'event')
        self.assertTrue(event_entry.verified)
        self.assertEqual(event_entry.cpd_hours, Decimal('2'))
        self.assertEqual(event_entry.link, certificate.get_verify_url())

    def test_a_revoked_certificate_drops_out(self):
        certificate = self.earn_event_certificate()
        type(certificate).objects.filter(pk=certificate.pk).update(is_revoked=True)
        self.assertFalse([e for e in sources.entries_for(self.member) if e.source == 'event'])

    def test_jeltan_articles_count_as_verified_publications(self):
        article = Article.objects.create(
            title='Code-switching in primary classrooms', abstract='x', is_published=True,
        )
        ArticleAuthor.objects.create(article=article, first_name='Ngọzị', last_name='Okafor', email='NGOZI@example.com')
        entry = next(e for e in sources.entries_for(self.member) if e.source == 'article')
        self.assertTrue(entry.verified)
        self.assertEqual(entry.category, Achievement.PUBLICATION)

    def test_uploads_are_self_reported(self):
        self.add_achievement()
        entry = next(e for e in sources.entries_for(self.member) if e.source == 'self')
        self.assertFalse(entry.verified)

    def test_another_members_records_never_appear(self):
        other = CustomUser.objects.create_user(
            email='other@example.com', password='pw-for-tests-only', first_name='A', last_name='B',
        )
        self.add_achievement(user=other, title='Not mine')
        self.assertFalse([e for e in sources.entries_for(self.member) if e.title == 'Not mine'])

    def test_the_overview_shows_both_kinds(self):
        self.earn_event_certificate()
        self.add_achievement()
        page = self.client.get(reverse('portfolio:overview'))
        self.assertContains(page, 'Verified by ELTAN')
        self.assertContains(page, 'Self-reported')
        self.assertEqual(page.context['summary'].total_hours, Decimal('8'))
        self.assertEqual(page.context['summary'].verified_hours, Decimal('2'))


class SummaryTests(PortfolioTestCase):
    def test_a_custom_period_keeps_only_its_entries(self):
        self.add_achievement(title='Old course', completed_on=date(2020, 5, 1))
        self.add_achievement(title='Recent course')
        today = timezone.localdate()
        page = self.client.get(reverse('portfolio:overview'), {
            'period': 'custom', 'from': (today - timedelta(days=30)).isoformat(), 'to': today.isoformat(),
        })
        titles = [entry.title for entry in page.context['entries']]
        self.assertIn('Recent course', titles)
        self.assertNotIn('Old course', titles)

    def test_goal_progress_is_shown_for_the_eltan_year(self):
        PortfolioProfile.objects.create(user=self.member, cpd_goal_hours=Decimal('24'))
        _, start, end = sources.eltan_year_bounds()
        self.add_achievement(completed_on=start, cpd_hours=Decimal('6'))
        page = self.client.get(reverse('portfolio:overview'))
        self.assertEqual(page.context['summary'].goal_percent, 25)

    def test_the_report_is_a_pdf_listing_the_period(self):
        self.earn_event_certificate()
        self.add_achievement()
        response = self.client.get(reverse('portfolio:report'), {'period': 'all'})
        self.assertEqual(response['Content-Type'], 'application/pdf')
        text = pdf_text(response.content)
        self.assertIn('Ngọzị Okafor', text)
        self.assertIn('Teaching Reading Webinar', text)
        self.assertIn('VERIFIED', text)
        self.assertIn('SELF-REPORTED', text)


class UploadTests(PortfolioTestCase):
    def test_a_member_adds_an_achievement_with_evidence(self):
        response = self.client.post(reverse('portfolio:add'), {
            'title': 'TESOL Certificate', 'category': Achievement.QUALIFICATION,
            'completed_on': '2026-03-01', 'cpd_hours': '120', 'is_public': 'on',
            'evidence': SimpleUploadedFile('tesol.pdf', b'%PDF-1.4 evidence', content_type='application/pdf'),
        })
        self.assertRedirects(response, reverse('portfolio:overview'))
        achievement = Achievement.objects.get(title='TESOL Certificate')
        self.assertEqual(achievement.user, self.member)

        download = self.client.get(reverse('portfolio:evidence', args=[achievement.pk]))
        self.assertEqual(b''.join(download.streaming_content), b'%PDF-1.4 evidence')

    def test_evidence_is_not_kept_in_public_media(self):
        from django.conf import settings
        achievement = self.add_achievement(
            evidence=SimpleUploadedFile('cert.pdf', b'%PDF-1.4 x', content_type='application/pdf'),
        )
        self.assertFalse(achievement.evidence.path.startswith(str(settings.MEDIA_ROOT)))

    def test_another_member_cannot_open_the_evidence_or_edit(self):
        achievement = self.add_achievement(
            evidence=SimpleUploadedFile('cert.pdf', b'%PDF-1.4 x', content_type='application/pdf'),
        )
        other = CustomUser.objects.create_user(
            email='other@example.com', password='pw-for-tests-only', first_name='A', last_name='B',
        )
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('portfolio:evidence', args=[achievement.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('portfolio:edit', args=[achievement.pk])).status_code, 404)
        self.client.post(reverse('portfolio:delete', args=[achievement.pk]))
        self.assertTrue(Achievement.objects.filter(pk=achievement.pk).exists())

    def test_disallowed_file_types_are_refused(self):
        response = self.client.post(reverse('portfolio:add'), {
            'title': 'X', 'category': Achievement.OTHER, 'completed_on': '2026-03-01',
            'evidence': SimpleUploadedFile('run.exe', b'MZ', content_type='application/octet-stream'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Achievement.objects.exists())

    def test_the_portfolio_needs_a_login(self):
        self.client.logout()
        response = self.client.get(reverse('portfolio:overview'))
        self.assertEqual(response.status_code, 302)


class SharingTests(PortfolioTestCase):
    def test_a_shared_portfolio_shows_public_entries_only(self):
        self.add_achievement(title='Shown course')
        self.add_achievement(title='Private course', is_public=False)
        self.client.post(reverse('portfolio:sharing'), {'action': 'enable'})
        profile = PortfolioProfile.objects.get(user=self.member)

        self.client.logout()
        page = self.client.get(profile.get_share_url())
        self.assertContains(page, 'Shown course')
        self.assertNotContains(page, 'Private course')
        self.assertNotContains(page, 'Evidence')

    def test_turning_sharing_off_closes_the_link(self):
        self.client.post(reverse('portfolio:sharing'), {'action': 'enable'})
        url = PortfolioProfile.objects.get(user=self.member).get_share_url()
        self.client.post(reverse('portfolio:sharing'), {'action': 'disable'})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_a_new_link_retires_the_old_one(self):
        self.client.post(reverse('portfolio:sharing'), {'action': 'enable'})
        old = PortfolioProfile.objects.get(user=self.member).get_share_url()
        self.client.post(reverse('portfolio:sharing'), {'action': 'regenerate'})
        self.assertEqual(self.client.get(old).status_code, 404)


class PremiumTests(PortfolioTestCase):
    def switch_on(self, limit=2):
        settings_row = PortfolioSettings.load()
        settings_row.premium_enabled = True
        settings_row.free_upload_limit = limit
        settings_row.save()

    def test_everything_is_free_while_the_switch_is_off(self):
        self.assertTrue(has_premium(self.member))

    def test_with_premium_on_records_stay_free_but_insight_needs_premium(self):
        self.switch_on()
        self.assertFalse(has_premium(self.member))

        page = self.client.get(reverse('portfolio:overview'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Portfolio Premium')
        self.assertRedirects(self.client.get(reverse('portfolio:report')), reverse('portfolio:overview'))
        self.client.post(reverse('portfolio:sharing'), {'action': 'enable'})
        self.assertFalse(PortfolioProfile.objects.get(user=self.member).share_enabled)

    def test_the_free_upload_limit_applies(self):
        self.switch_on(limit=1)
        self.add_achievement()
        response = self.client.get(reverse('portfolio:add'))
        self.assertRedirects(response, reverse('portfolio:overview'))

    def test_a_grant_gives_premium_for_its_dates(self):
        self.switch_on()
        PremiumGrant.objects.create(
            user=self.member, starts_on=timezone.localdate(), ends_on=timezone.localdate() + timedelta(days=30),
        )
        self.assertTrue(has_premium(self.member))
        response = self.client.get(reverse('portfolio:report'))
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_a_shared_link_stops_when_premium_lapses(self):
        self.client.post(reverse('portfolio:sharing'), {'action': 'enable'})
        url = PortfolioProfile.objects.get(user=self.member).get_share_url()
        self.switch_on()
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)


class DashboardLinkTests(PortfolioTestCase):
    def test_the_dashboard_links_to_the_portfolio(self):
        page = self.client.get(reverse('dash'))
        self.assertContains(page, reverse('portfolio:overview'))
