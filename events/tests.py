import hashlib
import hmac
import io
import json
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from account.models import CustomUser
from membership.models import Events, Subscription

from . import services
from .models import (
    MAX_CODE_ATTEMPTS,
    EventCertificate,
    EventQuestion,
    EventRegistration,
    EventSetup,
)

SECRET = 'sk_test_events'


def pdf_text(data):
    from pypdf import PdfReader
    return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PAYSTACK_SECRET_KEY=SECRET,
    SITE_URL='https://eltan.test',
)
class EventTestCase(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp(prefix='eltan-events-tests-')
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)

        self.event = Events.objects.create(
            event_title='Teaching Reading in Multilingual Classrooms',
            event_date=timezone.now().date() + timedelta(days=7),
            event_location='Online (Zoom)', event_desc='<p>A webinar.</p>',
        )
        self.setup = EventSetup.objects.create(
            event=self.event, accepts_registrations=True,
            join_link='https://zoom.example/j/123', attendance_code='Fluency',
            cpd_hours=Decimal('2'),
        )
        mail.outbox = []

    def make_member(self, email='member@example.com'):
        user = CustomUser.objects.create_user(
            email=email, password='pw-for-tests-only', first_name='Ngozi', last_name='Okafor',
        )
        subscription = Subscription.objects.create(
            user=user, eltan_year='2026-2027', payment_status='paid',
            membership_type='New Membership', end_date=timezone.now().date() + timedelta(days=200),
        )
        Subscription.objects.filter(pk=subscription.pk).update(start_date=timezone.now().date() - timedelta(days=10))
        return user

    def register_guest(self, email='guest@example.com', **extra):
        return services.register(
            self.event, first_name='Ụzọ', last_name='Nwankwọ', email=email, **extra,
        )[0]

    def open_activity(self):
        self.setup.activity_is_open = True
        self.setup.save()

    def answers_post(self, code='fluency'):
        data = {'attendance_code': code}
        for question in self.event.questions.all():
            data[f'q{question.pk}'] = '4' if question.kind == EventQuestion.RATING else 'Pair reading.'
        return data


class SetupTests(EventTestCase):
    def test_new_setup_gets_default_activity_questions(self):
        self.assertEqual(self.event.questions.count(), 3)
        self.assertTrue(self.event.questions.filter(kind=EventQuestion.RATING).exists())

    def test_registration_closes_after_the_deadline(self):
        self.setup.registration_closes_at = timezone.now() - timedelta(hours=1)
        self.setup.save()
        with self.assertRaises(services.RegistrationError):
            self.register_guest()

    def test_registration_closes_when_full(self):
        self.event.capacity = 1
        self.event.save()
        self.register_guest('one@example.com')
        with self.assertRaisesMessage(services.RegistrationError, 'fully booked'):
            self.register_guest('two@example.com')

    def test_an_event_not_registering_here_refuses(self):
        self.setup.accepts_registrations = False
        self.setup.save()
        with self.assertRaises(services.RegistrationError):
            self.register_guest()


class FreeRegistrationTests(EventTestCase):
    def test_a_guest_is_confirmed_at_once_and_sent_a_ticket(self):
        registration = self.register_guest()

        self.assertTrue(registration.is_confirmed)
        self.assertTrue(registration.ticket_id.startswith('EVT-'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(registration.ticket_id, mail.outbox[0].body)
        self.assertIn('https://zoom.example/j/123', mail.outbox[0].body)
        self.assertIn(registration.get_absolute_url(), mail.outbox[0].body)

    def test_registering_twice_returns_the_same_place(self):
        first = self.register_guest()
        second, created = services.register(
            self.event, first_name='Ụzọ', last_name='Nwankwọ', email='GUEST@example.com',
        )
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_the_register_view_sends_a_guest_to_their_page(self):
        response = self.client.post(reverse('events:register', args=[self.event.pk]), {
            'first_name': 'Bola', 'last_name': 'Ade', 'email': 'bola@example.com',
        })
        registration = EventRegistration.objects.get(email='bola@example.com')
        self.assertRedirects(response, registration.get_absolute_url())

        page = self.client.get(registration.get_absolute_url())
        self.assertContains(page, registration.ticket_id)
        self.assertContains(page, 'Join the session')

    def test_a_forged_link_is_refused(self):
        registration = self.register_guest()
        response = self.client.get(reverse('events:registration', args=[f'{registration.pk}:forged']))
        self.assertEqual(response.status_code, 404)

    def test_the_detail_page_shows_the_form(self):
        response = self.client.get(reverse('events:detail', args=[self.event.pk]))
        self.assertContains(response, 'Register')
        self.assertContains(response, '2 CPD hours')

    def test_resend_link_answers_the_same_for_unknown_addresses(self):
        self.register_guest()
        mail.outbox = []
        for email in ('guest@example.com', 'nobody@example.com'):
            response = self.client.post(
                reverse('events:resend_link', args=[self.event.pk]), {'email': email}, follow=True,
            )
            self.assertContains(response, 'If that address is registered')
        self.assertEqual(len(mail.outbox), 1)


class PaidRegistrationTests(EventTestCase):
    def setUp(self):
        super().setUp()
        self.setup.member_fee = Decimal('2000')
        self.setup.guest_fee = Decimal('5000')
        self.setup.save()

    def paystack_initialise(self):
        response = MagicMock()
        response.json.return_value = {
            'status': True, 'data': {'authorization_url': 'https://checkout.paystack.test/abc'},
        }
        return patch('events.services.requests.post', return_value=response)

    def webhook(self, registration, amount=None):
        payload = json.dumps({
            'event': 'charge.success',
            'data': {
                'reference': registration.payment_reference, 'status': 'success',
                'amount': amount if amount is not None else int(registration.amount * 100),
                'metadata': {'kind': 'event_registration', 'event_registration_id': registration.pk},
            },
        }).encode()
        signature = hmac.new(SECRET.encode(), payload, hashlib.sha512).hexdigest()
        return self.client.post(
            reverse('paystack_webhook'), payload, content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

    def test_a_guest_pays_the_guest_fee_through_paystack(self):
        with self.paystack_initialise() as post:
            response = self.client.post(reverse('events:register', args=[self.event.pk]), {
                'first_name': 'Bola', 'last_name': 'Ade', 'email': 'bola@example.com',
            })
        self.assertRedirects(response, 'https://checkout.paystack.test/abc', fetch_redirect_response=False)

        registration = EventRegistration.objects.get(email='bola@example.com')
        self.assertEqual(registration.status, EventRegistration.PENDING)
        self.assertEqual(registration.amount, Decimal('5000'))
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['amount'], 500000)
        self.assertEqual(payload['metadata']['kind'], 'event_registration')
        self.assertEqual(len(mail.outbox), 0)

    def test_a_member_pays_the_member_fee(self):
        member = self.make_member()
        self.client.force_login(member)
        with self.paystack_initialise():
            self.client.post(reverse('events:register', args=[self.event.pk]), {
                'first_name': 'Ngozi', 'last_name': 'Okafor', 'email': member.email,
            })
        registration = EventRegistration.objects.get(email=member.email)
        self.assertTrue(registration.is_member)
        self.assertEqual(registration.amount, Decimal('2000'))
        self.assertEqual(registration.user, member)

    def test_the_webhook_confirms_and_emails_once(self):
        with self.paystack_initialise():
            registration = self.register_guest()
        self.webhook(registration)
        self.webhook(registration)          # Paystack retries; so does the browser.

        registration.refresh_from_db()
        self.assertTrue(registration.is_confirmed)
        self.assertTrue(registration.ticket_id)
        self.assertEqual(len(mail.outbox), 1)

    def test_an_underpayment_is_not_confirmed(self):
        with self.paystack_initialise():
            registration = self.register_guest()
        self.webhook(registration, amount=100)
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.PENDING)

    def test_conference_payments_still_reach_the_conference_handler(self):
        self.assertFalse(services.is_event_payment({'reference': 'a1b2-uuid', 'metadata': {'conference_id': 3}}))

    def test_the_return_page_verifies_with_paystack(self):
        with self.paystack_initialise():
            registration = self.register_guest()
        verified = MagicMock()
        verified.json.return_value = {'data': {
            'reference': registration.payment_reference, 'status': 'success', 'amount': 500000,
        }}
        with patch('events.services.requests.get', return_value=verified):
            response = self.client.get(
                reverse('events:payment_return') + f'?reference={registration.payment_reference}',
            )
        self.assertRedirects(response, registration.get_absolute_url())
        registration.refresh_from_db()
        self.assertTrue(registration.is_confirmed)


class ActivityTests(EventTestCase):
    def setUp(self):
        super().setUp()
        self.registration = self.register_guest()
        mail.outbox = []

    def submit(self, code='fluency'):
        return self.client.post(
            reverse('events:submit_activity', args=[self.registration.token]), self.answers_post(code),
        )

    def test_the_activity_is_not_offered_until_it_opens(self):
        page = self.client.get(self.registration.get_absolute_url())
        self.assertNotContains(page, 'Attendance code')
        self.submit()
        self.assertFalse(EventCertificate.objects.exists())

    def test_the_right_code_and_answers_earn_a_certificate(self):
        self.open_activity()
        response = self.submit('  FLUENCY ')
        self.assertRedirects(response, self.registration.get_absolute_url())

        certificate = EventCertificate.objects.get(registration=self.registration)
        self.assertEqual(certificate.participant_name, 'Ụzọ Nwankwọ')
        self.assertEqual(certificate.cpd_hours, Decimal('2'))
        self.assertEqual(self.registration.response.answers.count(), 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(certificate.certificate_id, mail.outbox[0].body)

        page = self.client.get(self.registration.get_absolute_url())
        self.assertContains(page, 'Download certificate')
        self.assertContains(page, 'linkedin.com/profile/add')

    def test_a_wrong_code_is_refused_and_counted(self):
        self.open_activity()
        response = self.submit('guess')
        self.assertContains(response, 'attendance code is not right')
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.failed_code_attempts, 1)
        self.assertFalse(EventCertificate.objects.exists())

    def test_guessing_is_capped(self):
        self.open_activity()
        EventRegistration.objects.filter(pk=self.registration.pk).update(failed_code_attempts=MAX_CODE_ATTEMPTS)
        response = self.submit('fluency')
        self.assertContains(response, 'Too many incorrect')
        self.assertFalse(EventCertificate.objects.exists())

    def test_required_answers_are_required(self):
        self.open_activity()
        response = self.client.post(
            reverse('events:submit_activity', args=[self.registration.token]), {'attendance_code': 'fluency'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventCertificate.objects.exists())

    def test_the_activity_cannot_be_submitted_twice(self):
        self.open_activity()
        self.submit()
        self.submit()
        self.assertEqual(EventCertificate.objects.count(), 1)

    def test_an_unpaid_registration_cannot_do_the_activity(self):
        self.open_activity()
        EventRegistration.objects.filter(pk=self.registration.pk).update(status=EventRegistration.PENDING)
        self.submit()
        self.assertFalse(EventCertificate.objects.exists())


class CertificateTests(EventTestCase):
    def setUp(self):
        super().setUp()
        self.registration = self.register_guest()
        self.open_activity()
        self.client.post(
            reverse('events:submit_activity', args=[self.registration.token]), self.answers_post(),
        )
        self.certificate = EventCertificate.objects.get()

    def test_the_certificate_downloads_with_the_name_and_id(self):
        response = self.client.get(reverse('events:download_certificate', args=[self.registration.token]))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        text = pdf_text(response.content)
        self.assertIn('Ụzọ Nwankwọ', text)
        self.assertIn(self.certificate.certificate_id, text)
        self.assertIn('2 CPD hours', text)
        self.certificate.refresh_from_db()
        self.assertEqual(self.certificate.download_count, 1)

    def test_uploaded_artwork_is_used_when_there_is_some(self):
        from reportlab.pdfgen import canvas
        buffer = io.BytesIO()
        sheet = canvas.Canvas(buffer, pagesize=(842, 595))
        sheet.drawString(100, 500, 'DESIGNED ARTWORK')
        sheet.save()
        self.setup.certificate_template = SimpleUploadedFile('art.pdf', buffer.getvalue())
        self.setup.save()

        response = self.client.get(reverse('events:download_certificate', args=[self.registration.token]))
        text = pdf_text(response.content)
        self.assertIn('DESIGNED ARTWORK', text)
        self.assertIn('Ụzọ Nwankwọ', text)

    def test_verification_confirms_a_genuine_certificate(self):
        response = self.client.get(reverse('events:verify_certificate', args=[self.certificate.certificate_id]))
        self.assertContains(response, 'Genuine certificate')
        self.assertContains(response, 'Ụzọ Nwankwọ')

    def test_a_revoked_certificate_is_reported_and_not_served(self):
        EventCertificate.objects.filter(pk=self.certificate.pk).update(is_revoked=True)
        response = self.client.get(reverse('events:verify_certificate', args=[self.certificate.certificate_id]))
        self.assertContains(response, 'withdrawn')
        download = self.client.get(reverse('events:download_certificate', args=[self.registration.token]))
        self.assertEqual(download.status_code, 404)

    def test_an_unknown_id_is_not_found(self):
        response = self.client.get(reverse('events:verify_certificate', args=['ELTAN-EVT-2026-NOPE00']))
        self.assertContains(response, 'No certificate found')

    def test_the_linkedin_link_carries_the_certificate(self):
        from urllib.parse import parse_qs, urlparse
        from . import certificates

        url = certificates.linkedin_url(self.certificate, 'https://eltan.test/verify')
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query['certId'], [self.certificate.certificate_id])
        self.assertEqual(query['certUrl'], ['https://eltan.test/verify'])
        self.assertIn('ELTAN', query['organizationName'][0])


class DashboardTests(EventTestCase):
    def test_a_member_sees_their_badge_and_open_activities(self):
        member = self.make_member()
        registration = services.register(self.event, user=member)[0]
        self.open_activity()
        self.client.force_login(member)

        page = self.client.get(reverse('dash'))
        self.assertContains(page, 'Complete the activity')

        services.complete_activity(
            EventRegistration.objects.get(pk=registration.pk), 'fluency',
            [(question, 'answer') for question in self.event.questions.all()],
        )
        page = self.client.get(reverse('dash'))
        self.assertContains(page, 'My Events &amp; Badges')
        self.assertContains(page, 'linkedin.com/profile/add')
        self.assertEqual(page.context['stats']['certificates_earned'], 1)


class AdminTests(EventTestCase):
    def test_responses_export_as_csv(self):
        registration = self.register_guest()
        self.open_activity()
        services.complete_activity(
            EventRegistration.objects.get(pk=registration.pk), 'fluency',
            [(question, 'Pair reading.') for question in self.event.questions.all()],
        )
        staff = CustomUser.objects.create_superuser(email='admin@example.com', password='pw-for-tests-only')
        self.client.force_login(staff)
        response = self.client.post(reverse('admin:events_eventregistration_changelist'), {
            'action': 'export_responses', '_selected_action': [registration.pk],
        })
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('Pair reading.', response.content.decode())

    def test_the_events_admin_page_has_the_inlines(self):
        staff = CustomUser.objects.create_superuser(email='admin@example.com', password='pw-for-tests-only')
        self.client.force_login(staff)
        response = self.client.get(reverse('admin:membership_events_change', args=[self.event.pk]))
        self.assertContains(response, 'Post-event activity')
        self.assertContains(response, 'Activity questions')
