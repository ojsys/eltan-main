"""Check the SMTP configuration and optionally send a real test message.

Run this first whenever "emails aren't arriving" is reported — it separates a
broken configuration from a broken send, and prints the settings actually in
effect (never the password).

    python manage.py test_email
    python manage.py test_email --to someone@example.com
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from membership.email_utils import build_html_email, check_email_configuration, send_now


class Command(BaseCommand):
    help = "Verify the SMTP configuration and optionally send a test email."

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            dest='to',
            help="Send a test message to this address. Omit to only check the configuration.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Email configuration in effect"))
        for key in (
            'EMAIL_BACKEND', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_USE_TLS',
            'EMAIL_USE_SSL', 'EMAIL_HOST_USER', 'EMAIL_TIMEOUT',
            'DEFAULT_FROM_EMAIL', 'SERVER_EMAIL', 'CONTACT_EMAIL',
        ):
            self.stdout.write(f"  {key:<20} {getattr(settings, key, '<not set>')}")
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        self.stdout.write(f"  {'EMAIL_HOST_PASSWORD':<20} {'set (' + str(len(password)) + ' chars)' if password else 'EMPTY'}")

        self.stdout.write("")
        ok, problems = check_email_configuration()
        if ok:
            self.stdout.write(self.style.SUCCESS("Configuration looks good and the mail server accepted a connection."))
        else:
            self.stdout.write(self.style.ERROR("Problems found:"))
            for problem in problems:
                self.stdout.write(self.style.ERROR(f"  - {problem}"))

        recipient = options.get('to')
        if not recipient:
            self.stdout.write("")
            self.stdout.write("Pass --to someone@example.com to send a real test message.")
            return

        self.stdout.write("")
        self.stdout.write(f"Sending test message to {recipient} ...")
        message = build_html_email(
            subject="ELTAN mail server test",
            html_body=(
                "<p>This is a test message from the ELTAN website.</p>"
                f"<p>Sent at {timezone.now():%d %b %Y %H:%M %Z} via "
                f"<strong>{settings.EMAIL_HOST}</strong>.</p>"
                "<p>If you received this, conference tickets and receipts can be delivered.</p>"
            ),
            to=recipient,
        )
        sent, error = send_now(message)
        if sent:
            self.stdout.write(self.style.SUCCESS(f"Test email delivered to {recipient}."))
        else:
            self.stdout.write(self.style.ERROR(f"Test email FAILED: {error}"))
