"""Send the ticket/receipt to everyone whose payment is confirmed but who never
got an email.

This is the catch-up for registrations paid while mail was broken. Safe to run
repeatedly: a registration is skipped once its receipt has been delivered.

    python manage.py send_pending_tickets --dry-run
    python manage.py send_pending_tickets
    python manage.py send_pending_tickets --conference 3
"""

import time

from django.core.management.base import BaseCommand

from membership.models import EltanConferenceRegistration


class Command(BaseCommand):
    help = "Email tickets/receipts to confirmed registrations that never received one."

    def add_arguments(self, parser):
        parser.add_argument('--conference', type=int, help="Limit to one conference id.")
        parser.add_argument('--dry-run', action='store_true', help="List who would be emailed, send nothing.")
        parser.add_argument('--limit', type=int, help="Stop after this many sends.")
        parser.add_argument(
            '--throttle', type=float, default=1.0,
            help="Seconds to wait between sends (default 1.0), to stay under provider rate limits.",
        )

    def handle(self, *args, **options):
        # Import here so the module is importable without a configured mail backend.
        from membership.views import send_registration_receipt

        queryset = EltanConferenceRegistration.objects.filter(
            payment_status='completed',
            receipt_sent_at__isnull=True,
        ).select_related('conference', 'user').order_by('registered_at')

        if options['conference']:
            queryset = queryset.filter(conference_id=options['conference'])
        if options['limit']:
            queryset = queryset[:options['limit']]

        registrations = list(queryset)
        if not registrations:
            self.stdout.write(self.style.SUCCESS("No outstanding tickets — everyone confirmed has been emailed."))
            return

        self.stdout.write(f"{len(registrations)} confirmed registration(s) without a delivered ticket.")

        if options['dry_run']:
            for registration in registrations:
                self.stdout.write(
                    f"  would email {registration.contact_email or '<no address>'} "
                    f"(#{registration.pk}, ticket {registration.ticket_id or 'not issued'})"
                )
            self.stdout.write(self.style.WARNING("Dry run — nothing was sent."))
            return

        sent = failed = 0
        for registration in registrations:
            ok, error = send_registration_receipt(registration)
            if ok:
                sent += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  sent {registration.ticket_id} to {registration.contact_email}"
                ))
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(
                    f"  FAILED #{registration.pk} ({registration.contact_email}): {error}"
                ))
            if options['throttle']:
                time.sleep(options['throttle'])

        style = self.style.SUCCESS if not failed else self.style.WARNING
        self.stdout.write(style(f"Done: {sent} sent, {failed} failed."))
