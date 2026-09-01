"""Generate every article's galley again.

For when what a galley says changes without any article changing: a new journal
name or ISSN, an edit to the template, or — the reason this command exists — a
fix to the fonts. Galleys built before the embedded fonts went in print a black
box wherever a name needed a character outside Latin-1, and nothing in the
article record marks them as wrong, so they have to be rebuilt in bulk.

    manage.py retypeset_articles --dry-run       # what would be done
    manage.py retypeset_articles --published     # only what readers can see
    manage.py retypeset_articles                 # everything with a source file
"""

from django.core.management.base import BaseCommand

from journal.models import Article
from journal.typeset import typeset


class Command(BaseCommand):
    help = "Generate the JELTAN galley again for articles that have a source file."

    def add_arguments(self, parser):
        parser.add_argument(
            '--published', action='store_true',
            help='Only articles that are public. Staged ones are rebuilt when they are published.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List what would be done and change nothing.',
        )

    def handle(self, *args, **options):
        articles = Article.objects.order_by('pk')
        if options['published']:
            articles = articles.filter(is_published=True)

        # An article with no source file has nothing to typeset from: its galley
        # is whatever was uploaded, and regenerating would only overwrite that
        # with a cover page nobody asked for.
        candidates = [a for a in articles if a.source_file]
        skipped = articles.count() - len(candidates)

        self.stdout.write(
            f'{len(candidates)} article{"" if len(candidates) == 1 else "s"} to typeset'
            + (f'; {skipped} skipped for having no source file.' if skipped else '.')
        )
        if options['dry_run']:
            for article in candidates:
                self.stdout.write(f'  would typeset  {article.pk}  {article.title[:70]}')
            return

        done, failed = 0, []
        for article in candidates:
            if typeset(article):
                done += 1
                self.stdout.write(self.style.SUCCESS(f'  ok      {article.pk}  {article.title[:60]}'))
            else:
                failed.append(article)
                self.stdout.write(self.style.ERROR(
                    f'  failed  {article.pk}  {article.title[:60]} — {article.typeset_note}'
                ))

        self.stdout.write('')
        self.stdout.write(f'{done} generated.')
        if failed:
            self.stdout.write(self.style.ERROR(
                f'{len(failed)} could not be, and kept the galley they had. '
                'Each one says why on its edit page.'
            ))
