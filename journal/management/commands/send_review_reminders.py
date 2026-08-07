"""Chase reviewers whose reports are due or late.

Reviews slip. A journal that does not chase them quietly turns a six-week review
into a six-month one, and the author hears nothing the whole time. Run this daily
from cron:

    python manage.py send_review_reminders

Each reviewer is reminded at most once every ``--every`` days, so a long-overdue
review does not generate a daily nag that gets filtered as spam.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from journal.emails import send_review_reminder
from journal.models import ReviewAssignment, Submission


class Command(BaseCommand):
    help = 'Email reminders to reviewers whose reports are due soon or overdue.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--before', type=int, default=3,
            help='Remind this many days before the due date (default: 3).',
        )
        parser.add_argument(
            '--every', type=int, default=7,
            help='Do not remind the same reviewer more often than this many days (default: 7).',
        )
        parser.add_argument('--dry-run', action='store_true', help='Report without sending.')

    def handle(self, *args, **options):
        today = timezone.now().date()
        horizon = today + timedelta(days=options['before'])
        quiet_until = timezone.now() - timedelta(days=options['every'])

        due = ReviewAssignment.objects.filter(
            status=ReviewAssignment.ACCEPTED,
            due_date__lte=horizon,
        ).exclude(
            submission__status__in=Submission.CLOSED_STATUSES,
        ).select_related('submission')

        sent = skipped = failed = 0
        for assignment in due:
            if assignment.reminder_sent_at and assignment.reminder_sent_at > quiet_until:
                skipped += 1
                continue

            state = 'overdue' if assignment.is_overdue else f'due {assignment.due_date}'
            self.stdout.write(
                f'{assignment.submission.manuscript_id}: {assignment.reviewer_email} ({state})'
            )
            if options['dry_run']:
                continue

            ok, error = send_review_reminder(assignment)
            if ok:
                assignment.reminder_sent_at = timezone.now()
                assignment.save(update_fields=['reminder_sent_at'])
                sent += 1
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(f'  failed: {error}'))

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f'Dry run — {due.count()} reviewer(s) matched, {skipped} recently reminded.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{sent} reminder(s) sent, {skipped} skipped as recently reminded, {failed} failed.'
            ))
