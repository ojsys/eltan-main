from django.core.management.base import BaseCommand

from membership.models import Subscription, normalize_eltan_year


class Command(BaseCommand):
    """Recompute subscription end dates from the membership rules.

    Rewritten because the old version forced every subscription to 31 August: it
    split the year label on '/', which no longer matches the canonical
    ``YYYY-YYYY`` spelling, defaulted anything blank to 2024/2025, and — now that
    a renewal runs 365 days from the day it was taken out — flattened renewals
    onto a date they should not have.

    The rules live in ``Subscription.calculate_eltan_dates()``, so this command
    only applies them; it never encodes a date of its own.
    """

    help = 'Recompute subscription end dates (ELTAN year end for a first membership, 365 days for a renewal).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing anything.',
        )
        parser.add_argument(
            '--eltan-year',
            dest='eltan_year',
            help='Limit to one ELTAN year, e.g. 2025-2026.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        subscriptions = Subscription.objects.all().order_by('id')

        year_filter = normalize_eltan_year(options.get('eltan_year') or '')
        if year_filter:
            subscriptions = subscriptions.filter(eltan_year=year_filter)

        updated = skipped = unchanged = errors = 0

        for subscription in subscriptions:
            try:
                # A blank year is not guessable — it used to be defaulted to
                # 2024/2025, which quietly moved members into the wrong year.
                # Report it instead so someone can set it in the admin.
                if not normalize_eltan_year(subscription.eltan_year):
                    skipped += 1
                    self.stdout.write(self.style.WARNING(
                        f'Skipped #{subscription.id} ({subscription.user.email}): no ELTAN year set.'
                    ))
                    continue

                dates = subscription.calculate_eltan_dates()
                if not dates['end_date']:
                    skipped += 1
                    self.stdout.write(self.style.WARNING(
                        f"Skipped #{subscription.id} ({subscription.user.email}): "
                        f"ELTAN year '{subscription.eltan_year}' has no dates configured."
                    ))
                    continue

                if (subscription.end_date == dates['end_date']
                        and subscription.eltan_year == dates['eltan_year']):
                    unchanged += 1
                    continue

                kind = 'renewal' if subscription.is_renewal() else 'first membership'
                self.stdout.write(
                    f'#{subscription.id} {subscription.user.email} ({kind}): '
                    f'{subscription.end_date} -> {dates["end_date"]}'
                )

                if not dry_run:
                    subscription.end_date = dates['end_date']
                    subscription.eltan_year = dates['eltan_year']
                    subscription.save(update_fields=['end_date', 'eltan_year'])
                updated += 1

            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f'Error on subscription #{subscription.id}: {type(e).__name__}: {e}'
                ))

        verb = 'would be updated' if dry_run else 'updated'
        self.stdout.write(self.style.SUCCESS(
            f'Done: {updated} {verb}, {unchanged} already correct, '
            f'{skipped} skipped, {errors} errors.'
        ))
        if dry_run:
            self.stdout.write('Dry run — nothing was written.')
