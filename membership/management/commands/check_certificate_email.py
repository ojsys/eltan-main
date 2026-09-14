"""Trace what happens when someone asks for their certificate download link.

The public lookup page deliberately answers the same way whether or not an
address is on file, so that it cannot be used to discover who attended. That is
right for visitors and useless for staff: when somebody reports "I asked for my
certificate and nothing arrived", the page cannot tell you which link in the
chain broke.

This command walks the same chain with the answers switched on::

    python manage.py check_certificate_email --email someone@example.com

Add ``--send`` to actually deliver the email and report the SMTP result.
"""

from django.core.management.base import BaseCommand
from django.urls import reverse

from membership.email_utils import check_email_configuration
from membership.models import EltanConference, EltanConferenceRegistration


class Command(BaseCommand):
    help = "Diagnose why a certificate download-link email was or was not sent."

    def add_arguments(self, parser):
        parser.add_argument(
            '--email', required=True,
            help="The address the attendee typed into the certificate page.",
        )
        parser.add_argument(
            '--send', action='store_true',
            help="Actually send the email and report the result.",
        )

    # -- small output helpers ----------------------------------------------

    def ok(self, message):
        self.stdout.write(self.style.SUCCESS(f"  PASS  {message}"))

    def bad(self, message):
        self.stdout.write(self.style.ERROR(f"  FAIL  {message}"))

    def note(self, message):
        self.stdout.write(f"        {message}")

    def section(self, title):
        self.stdout.write(f"\n{title}")

    def handle(self, *args, **options):
        email = options['email'].strip()
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Certificate email check for {email}"
        ))

        # 1. Is any conference releasing certificates at all?
        self.section("1. Conferences with certificates released")
        released = list(EltanConference.objects.filter(certificates_released=True))
        if released:
            self.ok(f"{len(released)} conference(s) released:")
            for conference in released:
                self.note(f"- {conference.title} ({conference.start_date:%Y})")
        else:
            self.bad("No conference has 'Certificates released' ticked.")
            self.note("Nothing will ever be emailed until one does. Fix this in:")
            self.note("Admin -> ELTAN Conferences -> <conference> -> Certificates of Participation")
            total = EltanConference.objects.count()
            self.note(f"({total} conference(s) exist in total.)")

        # 2. Does this address match any registration at all?
        self.section("2. Registrations matching this address")
        from django.db.models import Q
        all_matches = list(
            EltanConferenceRegistration.objects
            .select_related('conference', 'user')
            .filter(Q(email__iexact=email) | Q(user__email__iexact=email))
        )
        if not all_matches:
            self.bad("No registration uses this email address.")
            self.note("Check for a typo, or search the admin for the attendee's ticket ID.")
            return
        self.ok(f"{len(all_matches)} registration(s) found:")
        for registration in all_matches:
            self.note(
                f"- #{registration.pk} {registration.conference.title} | "
                f"payment={registration.payment_status} | "
                f"ticket={registration.ticket_id or '—'} | "
                f"released={registration.conference.certificates_released} | "
                f"name={registration.participant_name or '(none)'}"
            )

        # 3. Which of those actually qualify for an email?
        self.section("3. Eligible for a download link")
        eligible = [
            registration for registration in all_matches
            if registration.payment_status == 'completed'
            and registration.conference.certificates_released
        ]
        if eligible:
            self.ok(f"{len(eligible)} registration(s) would be emailed.")
        else:
            self.bad("None qualify, so no email is sent.")
            for registration in all_matches:
                reasons = []
                if registration.payment_status != 'completed':
                    reasons.append(f"payment is '{registration.payment_status}', not 'completed'")
                if not registration.conference.certificates_released:
                    reasons.append("the conference has not released certificates")
                self.note(f"- #{registration.pk}: " + "; ".join(reasons))
            return

        # 4. Is the mail system able to send anything?
        self.section("4. Email configuration")
        config_ok, problems = check_email_configuration()
        if config_ok:
            self.ok("Email settings look usable.")
        else:
            self.bad("Email is misconfigured — nothing will be delivered:")
            for problem in problems:
                self.note(f"- {problem}")

        # 5. Optionally send it for real.
        self.section("5. Delivery")
        if not options['send']:
            self.note("Dry run. Re-run with --send to actually deliver the email.")
            lookup_path = reverse('certificate_lookup')
            self.note(f"The attendee can also self-serve at {lookup_path} using their ticket ID.")
            return

        from django.test import RequestFactory
        from django.conf import settings
        from membership.views import _send_certificate_link_email

        # _send_certificate_link_email builds absolute URLs from the request, so
        # give it one pointing at the real site rather than 'testserver'.
        site_url = getattr(settings, 'SITE_URL', 'https://web.eltanigeria.org')
        host = site_url.split('://', 1)[-1].rstrip('/')
        request = RequestFactory().get('/', secure=site_url.startswith('https'))
        request.META['HTTP_HOST'] = host

        sent, error = _send_certificate_link_email(request, eligible, email)
        if sent:
            self.ok(f"Email delivered to {email}.")
        else:
            self.bad(f"Send failed: {error}")
