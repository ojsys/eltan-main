"""Put JELTAN into a usable state on a fresh install.

Creates the journal settings row and the sections a journal in this field needs
to start taking submissions. Safe to run more than once: nothing is overwritten,
so it can be re-run after an upgrade to pick up anything new.
"""

from django.core.management.base import BaseCommand

from journal.models import JournalSettings, Section

DEFAULT_SECTIONS = [
    ('Research Articles', 'Reports of original empirical or theoretical research.', True, 1),
    ('Practice Papers', 'Classroom practice, materials and teacher development, grounded in evidence.', True, 2),
    ('Review Articles', 'Critical reviews of the literature on a topic in English language teaching.', True, 3),
    ('Book Reviews', 'Reviews of recent books relevant to the field.', False, 4),
    ('Editorial', 'Editorials and invited commentary.', False, 5),
]


class Command(BaseCommand):
    help = 'Create the JELTAN settings row and default sections.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apc', type=str, default=None,
            help='Set the article processing charge, e.g. --apc 25000.',
        )

    def handle(self, *args, **options):
        settings_row = JournalSettings.load()
        created_settings = not JournalSettings.objects.exclude(pk=settings_row.pk).exists()

        if options['apc'] is not None:
            settings_row.apc_amount = options['apc']
            settings_row.save(update_fields=['apc_amount'])
            self.stdout.write(f'Article processing charge set to {settings_row.apc_currency} {settings_row.apc_amount}.')

        self.stdout.write(
            self.style.SUCCESS(f'Journal settings ready: {settings_row.name}')
            if created_settings else f'Journal settings already exist: {settings_row.name}'
        )

        for name, description, peer_reviewed, order in DEFAULT_SECTIONS:
            section, created = Section.objects.get_or_create(
                name=name,
                defaults={'description': description, 'peer_reviewed': peer_reviewed, 'order': order},
            )
            self.stdout.write(
                self.style.SUCCESS(f'  + {name}') if created else f'    {name} (already present)'
            )

        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('  1. Admin → JELTAN → Journal Settings: aims and scope, guidelines, policies, ISSN, APC.')
        self.stdout.write('  2. Admin → JELTAN → Journal Editors: give at least one account an editor role.')
        self.stdout.write('  3. Admin → JELTAN → Editorial Board: the board as it should appear publicly.')
        self.stdout.write('  4. The journal is then live at /jeltan/ and the editor queue at /jeltan/editor/.')
