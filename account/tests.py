from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .impersonation import (
    MAX_DURATION_SECONDS,
    SESSION_KEY,
    SESSION_STARTED_AT,
    ImpersonationDenied,
    check_permission,
)
from .models import ImpersonationLog

User = get_user_model()


class ImpersonationPermissionTests(TestCase):
    """The rules that stop impersonation becoming a privilege-escalation route."""

    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user(
            email='member@example.com', password='pw12345!',
            first_name='Ngozi', last_name='Okonkwo')
        cls.other_member = User.objects.create_user(
            email='member2@example.com', password='pw12345!',
            first_name='Chidi', last_name='Nwosu')
        cls.staff = User.objects.create_user(
            email='staff@example.com', password='pw12345!',
            first_name='Amara', last_name='Eze', is_staff=True)
        cls.other_staff = User.objects.create_user(
            email='staff2@example.com', password='pw12345!',
            first_name='Tunde', last_name='Bello', is_staff=True)
        cls.superuser = User.objects.create_superuser(
            email='admin@example.com', password='pw12345!',
            first_name='Root', last_name='Admin', gender='M')

    def assertDenied(self, actor, target):
        with self.assertRaises(ImpersonationDenied):
            check_permission(actor, target)

    def test_staff_may_impersonate_an_ordinary_member(self):
        self.assertTrue(check_permission(self.staff, self.member))

    def test_a_member_may_never_impersonate(self):
        self.assertDenied(self.member, self.other_member)

    def test_a_superuser_can_never_be_impersonated(self):
        """Otherwise any staff account is one click from full control."""
        self.assertDenied(self.staff, self.superuser)
        self.assertDenied(self.superuser, self.superuser)

    def test_only_a_superuser_may_impersonate_staff(self):
        self.assertDenied(self.staff, self.other_staff)
        self.assertTrue(check_permission(self.superuser, self.other_staff))

    def test_cannot_impersonate_yourself(self):
        self.assertDenied(self.staff, self.staff)

    def test_cannot_impersonate_a_deactivated_account(self):
        self.member.is_active = False
        self.member.save()
        self.assertDenied(self.staff, self.member)

    def test_a_deactivated_staff_account_may_not_impersonate(self):
        self.staff.is_active = False
        self.assertDenied(self.staff, self.member)


class ImpersonationFlowTests(TestCase):
    """Starting, using and ending a borrowed session."""

    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user(
            email='member@example.com', password='pw12345!',
            first_name='Ngozi', last_name='Okonkwo')
        cls.staff = User.objects.create_user(
            email='staff@example.com', password='pw12345!',
            first_name='Amara', last_name='Eze', is_staff=True)

    def start_url(self, target=None):
        return reverse('impersonate_user', args=[(target or self.member).pk])

    def test_confirmation_page_is_shown_before_anything_happens(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.start_url())

        self.assertContains(response, 'Sign in as this member')
        self.assertContains(response, 'member@example.com')
        # A GET must not switch anyone.
        self.assertEqual(ImpersonationLog.objects.count(), 0)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_posting_switches_the_session_to_the_member(self):
        self.client.force_login(self.staff)
        self.client.post(self.start_url())

        session = self.client.session
        self.assertEqual(session[SESSION_KEY], self.staff.pk)
        self.assertEqual(int(session['_auth_user_id']), self.member.pk)

    def test_the_session_really_acts_as_the_member(self):
        self.client.force_login(self.staff)
        self.client.post(self.start_url())

        response = self.client.get(reverse('dash'))
        self.assertEqual(response.context['user'].pk, self.member.pk)

    def test_every_page_carries_the_banner(self):
        self.client.force_login(self.staff)
        self.client.post(self.start_url())

        response = self.client.get(reverse('dash'))
        self.assertContains(response, 'eltan-impersonation-banner')
        self.assertContains(response, 'Stop viewing as this user')
        self.assertContains(response, 'staff@example.com')

    def test_no_banner_on_an_ordinary_session(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('dash'))
        self.assertNotContains(response, 'eltan-impersonation-banner')

    def test_stopping_returns_the_session_to_the_admin(self):
        self.client.force_login(self.staff)
        self.client.post(self.start_url())
        self.client.post(reverse('stop_impersonation'))

        session = self.client.session
        self.assertEqual(int(session['_auth_user_id']), self.staff.pk)
        self.assertNotIn(SESSION_KEY, session)

    def test_stopping_is_post_only(self):
        self.client.force_login(self.staff)
        self.client.post(self.start_url())

        response = self.client.get(reverse('stop_impersonation'))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)

    def test_starting_is_post_only(self):
        """A GET renders the confirmation page and changes nothing."""
        self.client.force_login(self.staff)
        self.client.get(self.start_url())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_a_member_cannot_reach_the_start_view(self):
        self.client.force_login(self.member)
        response = self.client.post(self.start_url(self.staff))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(ImpersonationLog.objects.count(), 0)

    def test_an_anonymous_visitor_cannot_reach_the_start_view(self):
        response = self.client.post(self.start_url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImpersonationLog.objects.count(), 0)

    def test_cannot_nest_impersonations(self):
        """Hopping member to member would lose track of who started it."""
        second = User.objects.create_user(
            email='third@example.com', password='pw12345!',
            first_name='Bola', last_name='Ade')
        self.client.force_login(self.staff)
        self.client.post(self.start_url())
        self.client.post(self.start_url(second))

        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)
        self.assertEqual(ImpersonationLog.objects.count(), 1)

    def test_stop_on_a_normal_session_is_harmless(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('stop_impersonation'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)

    def test_logging_out_while_impersonating_ends_everything(self):
        self.client.force_login(self.staff)
        self.client.post(self.start_url())
        self.client.get(reverse('logout'))

        self.assertNotIn('_auth_user_id', self.client.session)
        log = ImpersonationLog.objects.get()
        self.assertEqual(log.end_reason, 'logout')
        self.assertIsNotNone(log.ended_at)


class ImpersonationExpiryTests(TestCase):
    """A borrowed session must not stay usable indefinitely."""

    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user(
            email='member@example.com', password='pw12345!',
            first_name='Ngozi', last_name='Okonkwo')
        cls.staff = User.objects.create_user(
            email='staff@example.com', password='pw12345!',
            first_name='Amara', last_name='Eze', is_staff=True)

    def test_it_ends_itself_after_the_time_limit(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('impersonate_user', args=[self.member.pk]))

        session = self.client.session
        stale = timezone.now() - timezone.timedelta(seconds=MAX_DURATION_SECONDS + 60)
        session[SESSION_STARTED_AT] = stale.isoformat()
        session.save()

        self.client.get(reverse('dash'))

        self.assertEqual(int(self.client.session['_auth_user_id']), self.staff.pk)
        self.assertEqual(ImpersonationLog.objects.get().end_reason, 'expired')

    def test_losing_staff_rights_mid_session_ends_it(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('impersonate_user', args=[self.member.pk]))

        self.staff.is_staff = False
        self.staff.save()
        self.client.get(reverse('dash'))

        # Nobody accountable is left, so the session is ended rather than handed back.
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(ImpersonationLog.objects.get().end_reason, 'revoked')


class ImpersonationAuditTests(TestCase):
    """What the log records, and that it cannot be edited away."""

    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user(
            email='member@example.com', password='pw12345!',
            first_name='Ngozi', last_name='Okonkwo')
        cls.staff = User.objects.create_user(
            email='staff@example.com', password='pw12345!',
            first_name='Amara', last_name='Eze', is_staff=True)

    def test_a_session_is_logged_from_start_to_finish(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('impersonate_user', args=[self.member.pk]))

        log = ImpersonationLog.objects.get()
        self.assertEqual(log.impersonator, self.staff)
        self.assertEqual(log.target, self.member)
        self.assertEqual(log.impersonator_email, 'staff@example.com')
        self.assertEqual(log.target_email, 'member@example.com')
        self.assertTrue(log.is_open)

        self.client.post(reverse('stop_impersonation'))
        log.refresh_from_db()
        self.assertFalse(log.is_open)
        self.assertEqual(log.end_reason, 'manual')

    def test_emails_survive_the_users_being_deleted(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('impersonate_user', args=[self.member.pk]))
        self.client.post(reverse('stop_impersonation'))

        self.member.delete()
        log = ImpersonationLog.objects.get()
        self.assertIsNone(log.target)
        self.assertEqual(log.target_email, 'member@example.com')

    def test_the_log_is_read_only_in_the_admin(self):
        from django.contrib import admin as django_admin
        from .models import ImpersonationLog as Model

        model_admin = django_admin.site._registry[Model]
        request = type('R', (), {'user': self.staff})()

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))


class ImpersonationAdminGuardTests(TestCase):
    """The Django admin is closed while a session is borrowed."""

    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user(
            email='member@example.com', password='pw12345!',
            first_name='Ngozi', last_name='Okonkwo')
        cls.staff_target = User.objects.create_user(
            email='target@example.com', password='pw12345!',
            first_name='Tunde', last_name='Bello', is_staff=True)
        cls.superuser = User.objects.create_superuser(
            email='admin@example.com', password='pw12345!',
            first_name='Root', last_name='Admin', gender='M')

    def test_admin_is_closed_while_impersonating_a_member(self):
        self.client.force_login(self.superuser)
        self.client.post(reverse('impersonate_user', args=[self.member.pk]))

        response = self.client.get(reverse('admin:account_customuser_changelist'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dash'), response['Location'])

    def test_admin_is_closed_even_when_the_target_is_staff(self):
        """The case the guard exists for: acting in the admin as someone else."""
        self.client.force_login(self.superuser)
        self.client.post(reverse('impersonate_user', args=[self.staff_target.pk]))

        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dash'), response['Location'])

    def test_admin_works_again_once_impersonation_stops(self):
        self.client.force_login(self.superuser)
        self.client.post(reverse('impersonate_user', args=[self.member.pk]))
        self.client.post(reverse('stop_impersonation'))

        response = self.client.get(reverse('admin:account_customuser_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_the_sign_in_as_column_only_offers_permitted_targets(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin:account_customuser_changelist'))

        self.assertContains(response, reverse('impersonate_user', args=[self.member.pk]))
        # A superuser is never a target, not even for another superuser.
        self.assertNotContains(response, reverse('impersonate_user', args=[self.superuser.pk]))
