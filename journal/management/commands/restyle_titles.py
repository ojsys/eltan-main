"""Put every existing article title into the journal's house style.

New and edited articles are styled when they are saved. The back catalogue was
loaded before that rule existed, so it still carries whatever each author typed
— some shouted in capitals, some in sentence case — which is exactly what makes
a contents page look untended.

    manage.py restyle_titles --dry-run     # show every change, alter nothing
    manage.py restyle_titles               # apply them
    manage.py restyle_titles --retypeset   # and rebuild the galleys that print them

Titles are printed on the galley's front page too, so an article whose title
changes here has a PDF that no longer matches until it is typeset again. Use
--retypeset, or run `manage.py retypeset_articles` afterwards.
"""

from django.core.management.base import BaseCommand

from journal.models import Article, Issue, JournalSettings
from journal.titles import to_title_case


class Command(BaseCommand):
    help = "Restyle existing article titles into the journal's house style (Title Case)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would change and alter nothing.',
        )
        parser.add_argument(
            '--retypeset', action='store_true',
            help='Rebuild the galley of every article whose title changed.',
        )
        parser.add_argument(
            '--issues', action='store_true',
            help='Restyle issue titles as well as article titles.',
        )

    def handle(self, *args, **options):
        try:
            acronyms = JournalSettings.load().acronym_list
        except Exception:                                # noqa: BLE001
            acronyms = []
        if acronyms:
            self.stdout.write(f"Also keeping these capitalised: {', '.join(acronyms)}")

        changed = self._restyle(
            Article.objects.order_by('pk'), 'article', acronyms, options['dry_run'],
        )
        if options['issues']:
            self._restyle(
                Issue.objects.exclude(title='').order_by('pk'), 'issue',
                acronyms, options['dry_run'],
            )

        if options['dry_run']:
            self.stdout.write('')
            self.stdout.write('Nothing was changed. Run without --dry-run to apply.')
            return

        if changed and options['retypeset']:
            self.stdout.write('')
            self.stdout.write(f'Rebuilding {len(changed)} galley(s) so the PDFs match…')
            from journal.typeset import typeset

            rebuilt = sum(1 for article in changed if article.source_file and typeset(article))
            self.stdout.write(self.style.SUCCESS(f'{rebuilt} galley(s) rebuilt.'))
        elif changed:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'{len(changed)} galley PDF(s) still print the old title. '
                'Run "manage.py retypeset_articles" to rebuild them.'
            ))

    def _restyle(self, queryset, label, acronyms, dry_run):
        changed = []
        for row in queryset:
            styled = to_title_case(row.title, acronyms)
            if styled == row.title:
                continue
            self.stdout.write(f'  {row.pk}')
            self.stdout.write(f'    from  {row.title}')
            self.stdout.write(self.style.SUCCESS(f'    to    {styled}'))
            if not dry_run:
                # update() rather than save(): the title is already in house
                # style, and this must not re-run slug or publication-date rules
                # on a row that is only having its capitals corrected.
                type(row).objects.filter(pk=row.pk).update(title=styled)
                row.title = styled
            changed.append(row)

        total = queryset.count()
        if changed:
            self.stdout.write(
                f'{len(changed)} of {total} {label} title(s) '
                + ('would be restyled.' if dry_run else 'restyled.')
            )
        else:
            self.stdout.write(f'All {total} {label} title(s) are already in house style.')
        return changed
