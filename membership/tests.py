import re
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import (
    ConferenceCertificate,
    EltanConference,
    EltanConferenceRegistration,
)

User = get_user_model()


class ConferenceCertificateTests(TestCase):
    """Certificates of Participation: who can get one, and when.

    The rules that matter here are the ones an attendee will notice going wrong:
    a certificate must not be downloadable before the committee releases it or
    before the money is confirmed, a non-member with no account must still be
    able to reach theirs, and nobody may fetch somebody else's.
    """

    @classmethod
    def setUpTestData(cls):
        cls.conference = EltanConference.objects.create(
            title='15th Annual National Conference',
            theme='Expanding Frontiers',
            description='Annual conference.',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 4),
            venue='Chrisland University, Abeokuta',
            registration_start=date(2026, 1, 1),
            registration_end=date(2026, 8, 25),
            member_fee=Decimal('30000'),
            member_early_bird_fee=Decimal('25000'),
            non_member_fee=Decimal('40000'),
            non_member_early_bird_fee=Decimal('35000'),
            international_delegate_fee=Decimal('100000'),
            certificates_released=True,
        )
        cls.member = User.objects.create_user(
            email='member@example.com', password='pw12345!',
            first_name='Ngozi', last_name='Okonkwo',
        )
        cls.member_registration = EltanConferenceRegistration.objects.create(
            conference=cls.conference, user=cls.member, registration_type='member',
            amount_paid=Decimal('30000'), payment_status='completed',
            ticket_id='ELTAN-2026-MEM001',
        )
        cls.guest_registration = EltanConferenceRegistration.objects.create(
            conference=cls.conference, registration_type='non_member',
            amount_paid=Decimal('40000'), payment_status='completed',
            ticket_id='ELTAN-2026-GST001',
            email='guest@example.com', first_name='Samuel', last_name='Adeyemi',
        )

    def member_certificate_url(self, registration=None):
        registration = registration or self.member_registration
        return reverse('conference_certificate', args=[registration.pk])

    # -- Member downloads ---------------------------------------------------

    def test_member_downloads_a_pdf(self):
        self.client.force_login(self.member)
        response = self.client.get(self.member_certificate_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('Ngozi_Okonkwo', response['Content-Disposition'])

    def test_certificate_is_issued_on_first_download_and_reused_after(self):
        self.client.force_login(self.member)
        self.assertEqual(ConferenceCertificate.objects.count(), 0)

        self.client.get(self.member_certificate_url())
        certificate = ConferenceCertificate.objects.get(registration=self.member_registration)
        self.assertTrue(certificate.certificate_id.startswith('ELTAN-CERT-2026-'))
        self.assertEqual(certificate.participant_name, 'Ngozi Okonkwo')
        self.assertEqual(certificate.download_count, 1)

        # A second download must not mint a new id — people quote the one they have.
        self.client.get(self.member_certificate_url())
        certificate.refresh_from_db()
        self.assertEqual(ConferenceCertificate.objects.count(), 1)
        self.assertEqual(certificate.download_count, 2)

    def test_name_is_snapshotted_at_issue_time(self):
        """A later profile edit must not change a certificate already in the wild."""
        self.client.force_login(self.member)
        self.client.get(self.member_certificate_url())

        self.member.first_name = 'Ngozichukwu'
        self.member.save()

        certificate = ConferenceCertificate.objects.get(registration=self.member_registration)
        self.assertEqual(certificate.participant_name, 'Ngozi Okonkwo')

    def test_no_download_before_certificates_are_released(self):
        self.conference.certificates_released = False
        self.conference.save()

        self.client.force_login(self.member)
        response = self.client.get(self.member_certificate_url())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ConferenceCertificate.objects.count(), 0)

    def test_no_download_before_payment_is_confirmed(self):
        self.member_registration.payment_status = 'pending'
        self.member_registration.save()

        self.client.force_login(self.member)
        response = self.client.get(self.member_certificate_url())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ConferenceCertificate.objects.count(), 0)

    def test_cannot_download_another_attendees_certificate(self):
        other = User.objects.create_user(
            email='other@example.com', password='pw12345!',
            first_name='Chidi', last_name='Nwosu',
        )
        self.client.force_login(other)
        response = self.client.get(self.member_certificate_url())

        self.assertEqual(response.status_code, 404)

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(self.member_certificate_url())
        self.assertEqual(response.status_code, 302)

    def test_revoked_certificate_cannot_be_downloaded(self):
        self.client.force_login(self.member)
        self.client.get(self.member_certificate_url())

        certificate = ConferenceCertificate.objects.get(registration=self.member_registration)
        certificate.is_revoked = True
        certificate.save()

        response = self.client.get(self.member_certificate_url())
        self.assertEqual(response.status_code, 302)

    # -- Non-member lookup --------------------------------------------------

    def test_guest_downloads_with_email_and_ticket_id(self):
        response = self.client.post(reverse('certificate_lookup'), {
            'email': 'guest@example.com',
            'ticket_id': 'ELTAN-2026-GST001',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        certificate = ConferenceCertificate.objects.get(registration=self.guest_registration)
        self.assertEqual(certificate.participant_name, 'Samuel Adeyemi')

    def test_guest_lookup_ignores_case(self):
        response = self.client.post(reverse('certificate_lookup'), {
            'email': 'GUEST@Example.COM',
            'ticket_id': 'eltan-2026-gst001',
        })
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_ticket_id_must_belong_to_the_email(self):
        """Knowing a ticket id alone must not hand over someone else's certificate."""
        response = self.client.post(reverse('certificate_lookup'), {
            'email': 'stranger@example.com',
            'ticket_id': 'ELTAN-2026-GST001',
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Content-Type'), 'application/pdf')
        self.assertEqual(ConferenceCertificate.objects.count(), 0)

    def test_email_only_lookup_sends_a_working_link(self):
        response = self.client.post(reverse('certificate_lookup'), {
            'email': 'guest@example.com', 'ticket_id': '',
        }, follow=True)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        body = sent.body + ''.join(part for part, _ in getattr(sent, 'alternatives', []))
        match = re.search(r'/conference-certificate/download/([^/\s"\']+)/', body)
        self.assertIsNotNone(match, 'the email should contain a signed download link')

        download = self.client.get(
            reverse('conference_certificate_link', args=[match.group(1)])
        )
        self.assertEqual(download['Content-Type'], 'application/pdf')

    def test_unknown_email_gets_the_same_answer_and_no_mail(self):
        """The form must not reveal who did and did not attend."""
        known = self.client.post(reverse('certificate_lookup'), {
            'email': 'guest@example.com', 'ticket_id': '',
        }, follow=True)
        mail.outbox = []
        unknown = self.client.post(reverse('certificate_lookup'), {
            'email': 'nobody@example.com', 'ticket_id': '',
        }, follow=True)

        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(known, 'we have just emailed')
        self.assertContains(unknown, 'we have just emailed')

    def test_tampered_download_token_is_refused(self):
        response = self.client.get(
            reverse('conference_certificate_link', args=['not-a-real-token'])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ConferenceCertificate.objects.count(), 0)

    # -- Verification -------------------------------------------------------

    def test_verification_confirms_a_genuine_certificate(self):
        certificate = self.member_registration.issue_certificate()
        response = self.client.get(
            reverse('verify_conference_certificate', args=[certificate.certificate_id])
        )

        self.assertContains(response, 'Genuine certificate')
        self.assertContains(response, 'Ngozi Okonkwo')

    def test_verification_reports_an_unknown_id(self):
        response = self.client.get(
            reverse('verify_conference_certificate', args=['ELTAN-CERT-2026-FAKE01'])
        )
        self.assertContains(response, 'No such certificate')

    def test_verification_reports_a_revoked_certificate(self):
        certificate = self.member_registration.issue_certificate()
        certificate.is_revoked = True
        certificate.save()

        response = self.client.get(
            reverse('verify_conference_certificate', args=[certificate.certificate_id])
        )
        self.assertContains(response, 'Certificate withdrawn')

    # -- Rendering ----------------------------------------------------------

    def test_long_names_are_shrunk_rather_than_overflowing(self):
        from .conference_certificates import _fit_font_size, MIN_NAME_FONT_SIZE

        long_name = 'Dr. Oluwafunmilayo Adebisi-Oyelaran Ogundimu-Akintayo'
        max_width = 440
        size = _fit_font_size(long_name, 30, max_width)

        self.assertLess(size, 30)
        self.assertGreaterEqual(size, MIN_NAME_FONT_SIZE)

    def test_short_names_keep_the_full_size(self):
        from .conference_certificates import _fit_font_size

        self.assertEqual(_fit_font_size('Ada Eze', 30, 440), 30)

    def test_participant_name_falls_back_through_the_sources(self):
        walk_in = EltanConferenceRegistration.objects.create(
            conference=self.conference, registration_type='non_member',
            amount_paid=Decimal('40000'), payment_status='completed',
            email='initials.only@example.com',
        )
        self.assertEqual(walk_in.participant_name, 'initials.only')

    # -- Abuse throttling ---------------------------------------------------

    def test_repeated_misses_are_throttled_but_real_lookups_are_not(self):
        """Probing gets cut off; a genuine attendee is never locked out by it."""
        from django.core.cache import cache
        from .views import CERTIFICATE_LOOKUP_MAX_MISSES

        cache.clear()
        url = reverse('certificate_lookup')

        # A long run of successful downloads must not count against anyone.
        for _ in range(CERTIFICATE_LOOKUP_MAX_MISSES + 5):
            response = self.client.post(url, {
                'email': 'guest@example.com', 'ticket_id': 'ELTAN-2026-GST001',
            })
            self.assertEqual(response['Content-Type'], 'application/pdf')

        # Misses do count, and eventually stop being answered.
        for _ in range(CERTIFICATE_LOOKUP_MAX_MISSES):
            self.client.post(url, {'email': 'probe@example.com', 'ticket_id': 'ELTAN-2026-NOPE'})

        blocked = self.client.post(url, {'email': 'probe@example.com', 'ticket_id': 'ELTAN-2026-NOPE'})
        self.assertContains(blocked, 'Too many attempts')
        cache.clear()


class CertificateLookupMessagingTests(TestCase):
    """What the lookup page says when nothing can be emailed.

    Staying neutral about *this person* is right; staying neutral about whether
    the conference has released certificates at all is just confusing, and was
    the reason a staff member could ask for a link, be told one was sent, and
    watch nothing arrive.
    """

    @classmethod
    def setUpTestData(cls):
        cls.conference = EltanConference.objects.create(
            title='15th Annual National Conference', theme='T', description='d',
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 4), venue='Abeokuta',
            registration_start=date(2026, 1, 1), registration_end=date(2026, 8, 25),
            member_fee=Decimal('30000'), member_early_bird_fee=Decimal('25000'),
            non_member_fee=Decimal('40000'), non_member_early_bird_fee=Decimal('35000'),
            international_delegate_fee=Decimal('100000'),
            certificates_released=False,
        )
        cls.registration = EltanConferenceRegistration.objects.create(
            conference=cls.conference, registration_type='non_member',
            amount_paid=Decimal('40000'), payment_status='completed',
            ticket_id='ELTAN-2026-GST001',
            email='guest@example.com', first_name='Samuel', last_name='Adeyemi',
        )

    def test_says_so_plainly_when_nothing_has_been_released(self):
        response = self.client.post(reverse('certificate_lookup'), {
            'email': 'guest@example.com', 'ticket_id': '',
        }, follow=True)

        self.assertContains(response, 'have not been released')
        self.assertNotContains(response, 'we have just emailed')
        self.assertEqual(len(mail.outbox), 0)

    def test_message_does_not_depend_on_the_address_being_real(self):
        """The unreleased notice is about the conference, so it cannot leak."""
        known = self.client.post(reverse('certificate_lookup'), {
            'email': 'guest@example.com', 'ticket_id': '',
        }, follow=True)
        unknown = self.client.post(reverse('certificate_lookup'), {
            'email': 'nobody@example.com', 'ticket_id': '',
        }, follow=True)

        self.assertContains(known, 'have not been released')
        self.assertContains(unknown, 'have not been released')

    def test_normal_neutral_message_returns_once_released(self):
        self.conference.certificates_released = True
        self.conference.save()

        response = self.client.post(reverse('certificate_lookup'), {
            'email': 'guest@example.com', 'ticket_id': '',
        }, follow=True)

        self.assertContains(response, 'we have just emailed')
        self.assertEqual(len(mail.outbox), 1)


class DashboardCertificateTests(TestCase):
    """The dashboard must never just go quiet about a certificate."""

    @classmethod
    def setUpTestData(cls):
        cls.conference = EltanConference.objects.create(
            title='15th Annual National Conference', theme='T', description='d',
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 4), venue='Abeokuta',
            registration_start=date(2026, 1, 1), registration_end=date(2026, 8, 25),
            member_fee=Decimal('30000'), member_early_bird_fee=Decimal('25000'),
            non_member_fee=Decimal('40000'), non_member_early_bird_fee=Decimal('35000'),
            international_delegate_fee=Decimal('100000'),
            certificates_released=False,
        )
        cls.member = User.objects.create_user(
            email='member@example.com', password='pw12345!',
            first_name='Ngozi', last_name='Okonkwo')
        cls.registration = EltanConferenceRegistration.objects.create(
            conference=cls.conference, user=cls.member, registration_type='member',
            amount_paid=Decimal('30000'), payment_status='completed')

    def test_download_button_appears_once_released(self):
        self.conference.certificates_released = True
        self.conference.save()
        self.client.force_login(self.member)

        response = self.client.get(reverse('dash'))
        self.assertContains(response, reverse('conference_certificate', args=[self.registration.pk]))
        self.assertContains(response, 'is ready')

    def test_an_unreleased_certificate_is_explained_not_hidden(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('dash'))

        self.assertContains(response, 'not ready yet')
        self.assertContains(response, 'not yet released')
        self.assertNotContains(
            response, reverse('conference_certificate', args=[self.registration.pk]))

    def test_nothing_is_shown_when_the_member_never_attended(self):
        stranger = User.objects.create_user(
            email='stranger@example.com', password='pw12345!',
            first_name='Chidi', last_name='Nwosu')
        self.client.force_login(stranger)

        response = self.client.get(reverse('dash'))
        # Neither the "ready" nor the "not ready yet" notice should appear at all
        # (the markup carries a static HTML comment naming the section, so assert
        # on the visible copy rather than the phrase itself).
        self.assertNotContains(response, 'is not ready yet')
        self.assertNotContains(response, 'not yet released')
        self.assertNotContains(response, '/certificate/')

    def test_an_unpaid_registration_is_not_promised_a_certificate(self):
        self.registration.payment_status = 'pending'
        self.registration.save()
        self.client.force_login(self.member)

        response = self.client.get(reverse('dash'))
        self.assertNotContains(response, 'not ready yet')


class RegistrationDetailPageTests(TestCase):
    """The detail page shares the public site's theme, not raw Bootstrap."""

    @classmethod
    def setUpTestData(cls):
        cls.conference = EltanConference.objects.create(
            title='15th Annual National Conference', theme='T', description='d',
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 4), venue='Abeokuta',
            registration_start=date(2026, 1, 1), registration_end=date(2026, 8, 25),
            member_fee=Decimal('30000'), member_early_bird_fee=Decimal('25000'),
            non_member_fee=Decimal('40000'), non_member_early_bird_fee=Decimal('35000'),
            international_delegate_fee=Decimal('100000'),
            certificates_released=True)
        cls.member = User.objects.create_user(
            email='member@example.com', password='pw12345!',
            first_name='Ngozi', last_name='Okonkwo')
        cls.registration = EltanConferenceRegistration.objects.create(
            conference=cls.conference, user=cls.member, registration_type='member',
            amount_paid=Decimal('30000'), payment_status='completed',
            ticket_id='ELTAN-2026-MEM001')

    def test_it_uses_the_site_theme(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse('conference_registration_detail', args=[self.registration.pk]))

        self.assertContains(response, 'page-header')
        self.assertContains(response, 'card-modern')
        self.assertContains(response, 'public-modern.css')

    def test_it_shows_the_ticket_and_certificate(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse('conference_registration_detail', args=[self.registration.pk]))

        self.assertContains(response, 'ELTAN-2026-MEM001')
        self.assertContains(response, 'Download Certificate')
        self.assertContains(response, reverse('conference_certificate', args=[self.registration.pk]))
