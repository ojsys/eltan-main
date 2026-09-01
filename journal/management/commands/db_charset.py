"""Report — and optionally fix — the character set of the database's tables.

The site's MySQL database was created with latin1 as its default, so every table
inherited it. latin1 cannot store a curly apostrophe, an en dash, or a name
spelled with a character English does not use; MySQL rejects those rather than
mangling them, so the symptom is a 500 with

    (1366, "Incorrect string value: ...")

rather than quiet corruption.

The account, membership and journal tables are converted by their own
migrations. This command is for everything else — Django's own tables, the CMS —
and for checking afterwards that nothing was missed.

    manage.py db_charset                    # report every table
    manage.py db_charset --prefix core_     # report one app's
    manage.py db_charset --prefix core_ --fix
    manage.py db_charset --fix              # convert everything not yet utf8mb4
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from eltanweb import dbcharset


class Command(BaseCommand):
    help = 'Report or convert MySQL table character sets to utf8mb4.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix', default='',
            help='Only tables whose name starts with this, e.g. --prefix core_.',
        )
        parser.add_argument(
            '--fix', action='store_true',
            help='Convert the tables that need it. Without this the command only reports.',
        )

    def handle(self, *args, **options):
        if connection.vendor != 'mysql':
            raise CommandError(
                f'This database is {connection.vendor}, which has no per-table character '
                'set. Only MySQL and MariaDB need this.'
            )

        prefix = options['prefix']
        with connection.cursor() as cursor:
            tables = dbcharset.tables_with_prefix(cursor, prefix)

        if not tables:
            raise CommandError(f'No tables found matching "{prefix}%".')

        needing = [row for row in tables if dbcharset.needs_conversion(row[1])]

        self.stdout.write(f'{len(tables)} table{"" if len(tables) == 1 else "s"} checked.')
        for name, collation, row_format in tables:
            if dbcharset.needs_conversion(collation):
                self.stdout.write(self.style.WARNING(
                    f'  needs {name}  ({collation}, row format {row_format})'
                ))
            else:
                self.stdout.write(f'  ok    {name}  ({collation})')

        if not needing:
            self.stdout.write(self.style.SUCCESS('\nEverything is already utf8mb4.'))
            return

        if not options['fix']:
            self.stdout.write(
                f'\n{len(needing)} table{"" if len(needing) == 1 else "s"} would be converted. '
                'Re-run with --fix to do it.'
            )
            self.stdout.write(
                'Take a backup first: the conversion rewrites every row, and on a '
                'large table it holds a lock while it does.'
            )
            self.stdout.write(
                "It re-encodes what is stored, reading it as the column's current "
                'charset. That is lossless for data that really is latin1. Text that '
                'was smuggled in as raw UTF-8 through a latin1 connection would be '
                'mangled instead, so check a record with punctuation afterwards.'
            )
            return

        self.stdout.write('')
        styles = {
            'converted': lambda text: self.style.SUCCESS(f'  converted {text}'),
            'failed': lambda text: self.style.ERROR(f'  failed    {text}'),
        }

        def report(outcome, table, error):
            if outcome == 'skipped':
                return
            line = f'{table}: {error}' if error else table
            self.stdout.write(styles[outcome](line))

        _converted, _skipped, failures = dbcharset.convert_prefix(
            connection, prefix, on_result=report,
        )

        self.stdout.write('')
        if failures:
            self.stdout.write(self.style.ERROR(
                f'{len(failures)} table{"" if len(failures) == 1 else "s"} could not be '
                'converted. The command is safe to run again — converted tables are skipped.'
            ))
            return

        self.stdout.write(self.style.SUCCESS('All converted.'))
        self.stdout.write(
            'New tables still inherit the database default. Ask the host to run:\n'
            f'  ALTER DATABASE `{connection.settings_dict["NAME"]}` '
            f'CHARACTER SET {dbcharset.TARGET_CHARSET} '
            f'COLLATE {dbcharset.TARGET_COLLATION};'
        )
