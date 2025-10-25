from django.core.management.base import BaseCommand
from django.utils import timezone
from membership.models import Subscription
from datetime import datetime, date

class Command(BaseCommand):
    help = 'Update all subscription end dates to August 31st'

    def handle(self, *args, **kwargs):
        subscriptions = Subscription.objects.all()
        updated_count = 0
        errors_count = 0

        for subscription in subscriptions:
            try:
                if not subscription.eltan_year:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Subscription ID {subscription.id} for user {subscription.user.email} has no ELTAN year. '
                            f'Setting to 2024/2025 as default.'
                        )
                    )
                    subscription.eltan_year = '2024/2025'
                
                # Get the year from the eltan_year field
                end_year = int(subscription.eltan_year.split('/')[1])
                
                # Set end date to August 31st of that year
                new_end_date = date(end_year, 8, 31)
                
                # Update the subscription
                subscription.end_date = new_end_date
                subscription.save()
                
                updated_count += 1
                self.stdout.write(
                    f'Updated subscription ID {subscription.id} for {subscription.user.email}'
                )
                
            except Exception as e:
                errors_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Error updating subscription ID {subscription.id}: {str(e)}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Process completed: {updated_count} subscriptions updated, {errors_count} errors encountered'
            )
        )