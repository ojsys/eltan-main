from datetime import date, timedelta
from io import StringIO

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from account.models import CustomUser
from membership.admin import SubscriptionAdminForm
from membership.models import CertificateSignatory, ELTANYearSetting, Subscription
from membership.views import create_subscription, renew_subscription, send_subscription_receipt


class EltanYearExpiryTests(TestCase):
    """When a membership expires: a first membership ends with the ELTAN year it
    was taken out in, a renewal runs 365 days from the day it is renewed."""

    def setUp(self):
        self.year, _ = ELTANYearSetting.objects.get_or_create(eltan_year='2025-2026')
        self.year.is_active = True
        self.year.save()
        self.user = CustomUser.objects.create(email='new@example.com')

    def test_first_time_subscription_expires_with_eltan_year(self):
        sub = create_subscription(
            self.user, None, 5500, 'LAGOS',
            membership_type='New Membership', eltan_year='2025-2026',
        )
        self.assertEqual(sub.end_date, date(2026, 8, 31))
        self.assertFalse(sub.is_renewal())

    def test_first_timer_cannot_buy_365_days_by_picking_renew(self):
        sub = create_subscription(
            self.user, None, 3000, 'LAGOS',
            membership_type='Renew Membership', eltan_year='2025-2026',
        )
        self.assertEqual(sub.end_date, date(2026, 8, 31))

    def test_renewal_runs_365_days_from_subscription_day(self):
        first = create_subscription(
            self.user, None, 5500, 'LAGOS',
            membership_type='New Membership', eltan_year='2025-2026',
        )
        first.payment_status = 'paid'
        first.end_date = date(2026, 8, 31)
        first.save()

        renewed = renew_subscription(
            first, None, 3000, 'LAGOS',
            membership_type='Renew Membership', eltan_year='2025-2026',
        )
        today = timezone.now().date()
        self.assertEqual(renewed.end_date, today + timedelta(days=365))
        self.assertEqual(renewed.start_date, today)

    def test_new_row_for_member_with_paid_history_is_treated_as_renewal(self):
        # The Paystack flow creates a fresh row rather than reusing the old one.
        self._paid_membership_last_year()
        sub = Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', payment_status='pending',
            membership_type='Renew Membership',
        )
        self.assertTrue(sub.is_renewal())
        self.assertEqual(sub.end_date, timezone.now().date() + timedelta(days=365))

    def test_a_later_year_does_not_turn_an_earlier_one_into_a_renewal(self):
        # Recomputing a member's history must not read the years that came after
        # a subscription as evidence that it was itself a renewal.
        first = self._paid_membership_last_year()
        Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', payment_status='paid',
            membership_type='Renew Membership',
        )
        self.assertFalse(first.is_renewal())
        self.assertEqual(first.calculate_eltan_dates()['end_date'], date(2025, 8, 31))

    def _paid_membership_last_year(self):
        """A paid subscription that started a year ago (start_date is auto_now_add,
        so it has to be pushed back after the insert)."""
        sub = Subscription.objects.create(
            user=self.user, eltan_year='2024-2025', payment_status='paid',
            membership_type='New Membership', end_date=date(2025, 8, 31),
        )
        Subscription.objects.filter(pk=sub.pk).update(start_date=date(2024, 9, 15))
        sub.refresh_from_db()
        return sub

    def test_unpaid_abandoned_attempt_does_not_count_as_history(self):
        Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', payment_status='pending',
            membership_type='New Membership',
        )
        sub = Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', payment_status='pending',
            membership_type='New Membership',
        )
        self.assertFalse(sub.is_renewal())
        self.assertEqual(sub.end_date, date(2026, 8, 31))

    def test_subscribing_on_the_eve_of_year_end_still_expires_with_the_year(self):
        sub = Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', payment_status='pending',
            membership_type='New Membership',
        )
        # start_date is auto_now_add; the rule is about the selected year, not today.
        self.assertEqual(sub.end_date, date(2026, 8, 31))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SubscriptionReceiptTests(TestCase):
    """Members get an emailed receipt as evidence of their subscription."""

    def setUp(self):
        ELTANYearSetting.objects.get_or_create(eltan_year='2025-2026')
        self.user = CustomUser.objects.create(
            email='member@example.com', first_name='Ada', last_name='Obi',
        )
        mail.outbox = []

    def test_receipt_is_sent_when_a_subscription_is_created(self):
        subscription = create_subscription(
            self.user, None, 5500, 'LAGOS',
            membership_type='New Membership', eltan_year='2025-2026',
        )
        ok, error = send_subscription_receipt(subscription)

        self.assertTrue(ok, error)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['member@example.com'])
        self.assertIn('2025-2026', message.subject)
        # Both parts: HTML alone gets marked down by spam filters.
        self.assertIn('Ada', message.body)
        self.assertEqual(message.alternatives[0][1], 'text/html')

    def test_a_pending_receipt_says_the_payment_is_being_verified(self):
        subscription = create_subscription(
            self.user, None, 5500, 'LAGOS',
            membership_type='New Membership', eltan_year='2025-2026',
        )
        send_subscription_receipt(subscription)

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Awaiting Verification', html)
        self.assertIn('We received your ELTAN subscription', mail.outbox[0].subject)

    def test_a_paid_receipt_confirms_the_membership(self):
        subscription = create_subscription(
            self.user, None, 5500, 'LAGOS',
            membership_type='New Membership', eltan_year='2025-2026',
        )
        subscription.payment_status = 'paid'
        subscription.save()
        send_subscription_receipt(subscription)

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Payment Confirmed', html)
        self.assertIn('Membership Receipt', mail.outbox[0].subject)

    def test_a_successful_send_is_recorded_on_the_subscription(self):
        subscription = create_subscription(
            self.user, None, 5500, 'LAGOS',
            membership_type='New Membership', eltan_year='2025-2026',
        )
        send_subscription_receipt(subscription)
        subscription.refresh_from_db()

        self.assertIsNotNone(subscription.receipt_sent_at)
        self.assertEqual(subscription.receipt_error, '')

    def test_a_member_with_no_email_is_flagged_rather_than_silently_skipped(self):
        self.user.email = ''
        self.user.save()
        subscription = Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', membership_type='New Membership',
        )

        ok, error = send_subscription_receipt(subscription)
        subscription.refresh_from_db()

        self.assertFalse(ok)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('No email address', subscription.receipt_error)


class SubscriptionAdminYearDropdownTests(TestCase):
    """An admin picks the ELTAN year from the configured years, never types it."""

    def setUp(self):
        ELTANYearSetting.objects.get_or_create(eltan_year='2025-2026')
        ELTANYearSetting.objects.get_or_create(eltan_year='2026-2027')
        self.user = CustomUser.objects.create(email='admin-edit@example.com')

    def test_year_field_offers_the_configured_years(self):
        form = SubscriptionAdminForm()
        values = [value for value, _ in form.fields['eltan_year'].choices if value]

        self.assertIn('2025-2026', values)
        self.assertIn('2026-2027', values)

    def test_a_legacy_year_on_an_existing_row_stays_selectable(self):
        subscription = Subscription.objects.create(
            user=self.user, eltan_year='2019-2020', membership_type='New Membership',
        )
        form = SubscriptionAdminForm(instance=subscription)
        values = [value for value, _ in form.fields['eltan_year'].choices if value]

        # Editing an old subscription must not be blocked by a year that has
        # since been removed from the ELTAN Years table.
        self.assertIn('2019-2020', values)

    def test_the_year_is_stored_canonically(self):
        form = SubscriptionAdminForm(
            data={
                'user': self.user.pk,
                'membership_type': 'New Membership',
                'eltan_year': '2025/2026',
                'certificate_status': 'pending',
                'payment_method': 'manual',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['eltan_year'], '2025-2026')


class CertificateSignatoryTests(TestCase):
    """The president's and secretary's names and signatures come from the admin."""

    def test_only_active_signatories_are_printed_in_order(self):
        secretary = CertificateSignatory.objects.create(
            name='Abel Ochika', title='National Secretary', order=2,
            signature=SimpleUploadedFile('sec.png', b'x', content_type='image/png'),
        )
        president = CertificateSignatory.objects.create(
            name='Dr. Kennedy Edegbe', title='National President', order=1,
            signature=SimpleUploadedFile('pres.png', b'x', content_type='image/png'),
        )
        CertificateSignatory.objects.create(
            name='Former Officer', title='Past President', order=3, is_active=False,
            signature=SimpleUploadedFile('old.png', b'x', content_type='image/png'),
        )

        self.assertEqual(
            CertificateSignatory.for_certificate(), [president, secretary],
        )

    def test_certificate_prints_the_configured_signatories(self):
        from django.template.loader import render_to_string

        CertificateSignatory.objects.create(
            name='Prof. New President', title='National President', order=1,
            signature=SimpleUploadedFile('new.png', b'x', content_type='image/png'),
        )
        html = render_to_string('membership/cert_template.html', {
            'member': CustomUser.objects.create(email='cert@example.com'),
            'eltan_year': '2025-2026',
            'qr_code_path': '',
            'signatories': CertificateSignatory.for_certificate(),
        })

        self.assertIn('Prof. New President', html)
        # The hardcoded officers are only a fallback for an unconfigured site.
        self.assertNotIn('Dr. Kennedy Edegbe', html)

    def test_certificate_falls_back_when_no_signatories_are_configured(self):
        from django.template.loader import render_to_string

        html = render_to_string('membership/cert_template.html', {
            'member': CustomUser.objects.create(email='cert2@example.com'),
            'eltan_year': '2025-2026',
            'qr_code_path': '',
            'signatories': CertificateSignatory.for_certificate(),
        })

        self.assertIn('Dr. Kennedy Edegbe', html)


class UpdateEndDatesCommandTests(TestCase):
    """The update_end_dates command applies the rules, it does not invent dates."""

    def setUp(self):
        ELTANYearSetting.objects.get_or_create(eltan_year='2025-2026')
        self.user = CustomUser.objects.create(email='cmd@example.com')

    def _run(self, *args):
        out = StringIO()
        call_command('update_end_dates', *args, stdout=out)
        return out.getvalue()

    def test_a_wrong_end_date_is_corrected_to_the_eltan_year_end(self):
        subscription = Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', membership_type='New Membership',
            end_date=date(2030, 1, 1),
        )
        self._run()
        subscription.refresh_from_db()

        self.assertEqual(subscription.end_date, date(2026, 8, 31))

    def test_a_renewal_is_not_flattened_onto_the_eltan_year_end(self):
        first = Subscription.objects.create(
            user=self.user, eltan_year='2024-2025', payment_status='paid',
            membership_type='New Membership', end_date=date(2025, 8, 31),
        )
        Subscription.objects.filter(pk=first.pk).update(start_date=date(2024, 9, 15))
        renewal = Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', payment_status='paid',
            membership_type='Renew Membership',
        )
        expected = renewal.start_date + timedelta(days=365)

        self._run()
        renewal.refresh_from_db()

        self.assertEqual(renewal.end_date, expected)

    def test_dry_run_writes_nothing(self):
        subscription = Subscription.objects.create(
            user=self.user, eltan_year='2025-2026', membership_type='New Membership',
            end_date=date(2030, 1, 1),
        )
        output = self._run('--dry-run')
        subscription.refresh_from_db()

        self.assertEqual(subscription.end_date, date(2030, 1, 1))
        self.assertIn('nothing was written', output)

    def test_a_subscription_with_no_eltan_year_is_skipped_not_guessed(self):
        subscription = Subscription.objects.create(
            user=self.user, membership_type='New Membership',
        )
        Subscription.objects.filter(pk=subscription.pk).update(eltan_year='', end_date=None)

        output = self._run()
        subscription.refresh_from_db()

        self.assertIsNone(subscription.end_date)
        self.assertIn('no ELTAN year set', output)


class SubscriptionPageTests(TestCase):
    """The member-facing subscription form offers the configured years."""

    def setUp(self):
        ELTANYearSetting.objects.get_or_create(eltan_year='2025-2026')
        ELTANYearSetting.objects.get_or_create(eltan_year='2026-2027')
        self.user = CustomUser.objects.create_user(
            email='page@example.com', password='pw-for-tests-only',
        )

    def test_eltan_year_renders_as_a_dropdown_of_configured_years(self):
        self.client.force_login(self.user)
        response = self.client.get('/subscribe/')

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('<select name="eltan_year"', html)
        self.assertIn('<option value="2025-2026"', html)
        self.assertIn('<option value="2026-2027"', html)

    def test_a_hidden_year_is_not_offered(self):
        ELTANYearSetting.objects.filter(eltan_year='2026-2027').update(is_selectable=False)
        self.client.force_login(self.user)

        html = self.client.get('/subscribe/').content.decode()

        self.assertIn('<option value="2025-2026"', html)
        self.assertNotIn('<option value="2026-2027"', html)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SubscriptionAdminReceiptTests(TestCase):
    """Marking a bank-transfer payment as paid sends the confirmed receipt."""

    def setUp(self):
        ELTANYearSetting.objects.get_or_create(eltan_year='2025-2026')
        self.staff = CustomUser.objects.create_superuser(
            email='staff@example.com', password='pw-for-tests-only',
        )
        self.member = CustomUser.objects.create(
            email='transfer@example.com', first_name='Ngozi', last_name='Eze',
        )
        self.client.force_login(self.staff)
        mail.outbox = []

    def _post_subscription(self, subscription, payment_status):
        return self.client.post(
            f'/admin/membership/subscription/{subscription.pk}/change/',
            {
                'user': self.member.pk,
                'membership_type': 'New Membership',
                'eltan_year': '2025-2026',
                'payment_status': payment_status,
                'payment_method': 'manual',
                'certificate_status': 'pending',
                'end_date': '2026-08-31',
                'payment_amount': '5500',
            },
            follow=True,
        )

    def test_marking_paid_emails_the_receipt(self):
        subscription = Subscription.objects.create(
            user=self.member, eltan_year='2025-2026',
            membership_type='New Membership', payment_status='pending',
            payment_amount=5500,
        )

        self._post_subscription(subscription, 'paid')
        subscription.refresh_from_db()

        self.assertEqual(subscription.payment_status, 'paid')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Membership Receipt', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['transfer@example.com'])

    def test_resaving_an_already_paid_subscription_does_not_resend(self):
        subscription = Subscription.objects.create(
            user=self.member, eltan_year='2025-2026',
            membership_type='New Membership', payment_status='paid',
            payment_amount=5500,
        )

        self._post_subscription(subscription, 'paid')

        self.assertEqual(len(mail.outbox), 0)
