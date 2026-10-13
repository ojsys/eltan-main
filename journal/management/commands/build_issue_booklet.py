"""Build an issue's booklet from the command line.

The same job as the 'Build booklet' button on the issue's editorial page, for
an issue large enough that rendering it might outlast a web request, and for
building every issue's booklet at once after the template changes.

    manage.py build_issue_booklet vol-4-no-1-2026     # one issue, by slug
    manage.py build_issue_booklet 12                  # one issue, by id
    manage.py build_issue_booklet --all               # every published issue
"""

from django.core.management.base import BaseCommand, CommandError

from journal import booklet
from journal.models import Issue


class Command(BaseCommand):
    help = "Paginate an issue and build its booklet PDF."

    def add_arguments(self, parser):
        parser.add_argument('issue', nargs='?', help='The issue slug or id.')
        parser.add_argument('--all', action='store_true', help='Every published issue.')

    def handle(self, *args, **options):
        if options['all']:
            issues = list(Issue.objects.filter(is_published=True).order_by('year', 'volume', 'number'))
        elif options['issue']:
            key = options['issue']
            lookup = {'pk': int(key)} if key.isdigit() else {'slug': key}
            try:
                issues = [Issue.objects.get(**lookup)]
            except Issue.DoesNotExist as exc:
                raise CommandError(f'No issue matches "{key}".') from exc
        else:
            raise CommandError('Name an issue by slug or id, or pass --all.')

        failed = 0
        for issue in issues:
            try:
                note = booklet.build(issue)
            except booklet.BookletError as exc:
                failed += 1
                self.stderr.write(f'{issue.label}: {exc}')
            else:
                self.stdout.write(self.style.SUCCESS(f'{issue.label}: {note}'))
        if failed and len(issues) == 1:
            raise CommandError('The booklet was not built.')
