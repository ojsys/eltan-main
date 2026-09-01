"""Converting MySQL tables to utf8mb4.

The site's database was created with latin1 as its default charset, so every
table inherited it and so does every column any migration adds. latin1 cannot
store a curly apostrophe, an en dash, or a name spelled with a character English
does not use, and MySQL rejects those outright rather than mangling them:

    (1366, "Incorrect string value: '\\xC5\\x82o\\xC5\\x84s...'")

Each app fixes its own tables in its own migration, and they all call this. It
lives in the project package rather than in an app because a migration in
``account`` importing from ``membership`` — or either from ``journal`` — would
invent a dependency between apps that does not otherwise exist.

Nothing here imports models, so it is safe for migrations to import: it is a
fixed piece of database plumbing, not application code that will move under
them later.
"""

import logging

logger = logging.getLogger(__name__)

TARGET_CHARSET = 'utf8mb4'
TARGET_COLLATION = 'utf8mb4_unicode_ci'


def tables_with_prefix(cursor, prefix):
    """Every table in the current database whose name starts with ``prefix``.

    Read from information_schema rather than from the app registry so that
    many-to-many tables, and anything left behind by a removed model, are
    included — they hold text too.
    """
    cursor.execute(
        """
        SELECT TABLE_NAME, TABLE_COLLATION, ROW_FORMAT
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_TYPE = 'BASE TABLE'
          AND TABLE_NAME LIKE %s
        ORDER BY TABLE_NAME
        """,
        [f'{prefix}%'],
    )
    return cursor.fetchall()


def needs_conversion(collation):
    return not (collation or '').startswith(TARGET_CHARSET)


def convert_table(cursor, table):
    """Convert one table, row format first.

    A utf8mb4 character is four bytes, so a unique index on a 255-character
    column needs 1020 of them — past InnoDB's old 767-byte limit and inside the
    3072 that DYNAMIC row format allows. The two statements stay separate
    because a single ALTER gives no guarantee the row format is applied before
    the index is rebuilt, and on an older server that ordering is the whole
    difference between working and failing.
    """
    cursor.execute(f'ALTER TABLE `{table}` ROW_FORMAT=DYNAMIC')
    cursor.execute(
        f'ALTER TABLE `{table}` CONVERT TO CHARACTER SET '
        f'{TARGET_CHARSET} COLLATE {TARGET_COLLATION}'
    )


def convert_prefix(connection, prefix, on_result=None):
    """Convert every table under ``prefix`` that is not already utf8mb4.

    Returns ``(converted, skipped, failures)``. Tables already converted are
    skipped, so a run that fails partway can simply be run again — which
    matters, because MySQL commits each ALTER as it goes and no transaction
    will roll this back.

    Every failure is collected rather than raising at the first: whoever is
    fixing this wants the whole list, not one table at a time.
    """
    converted, skipped, failures = [], [], []

    with connection.cursor() as cursor:
        for table, collation, _row_format in tables_with_prefix(cursor, prefix):
            if not needs_conversion(collation):
                skipped.append(table)
                if on_result:
                    on_result('skipped', table, None)
                continue
            try:
                convert_table(cursor, table)
            except Exception as exc:                      # noqa: BLE001
                logger.error('Could not convert %s to utf8mb4: %s', table, exc)
                failures.append((table, exc))
                if on_result:
                    on_result('failed', table, exc)
            else:
                converted.append(table)
                if on_result:
                    on_result('converted', table, None)

    return converted, skipped, failures


def failure_report(prefix, failures):
    """The message a migration raises with, naming every table that resisted."""
    listed = '\n  '.join(f'{table}: {exc}' for table, exc in failures)
    return (
        f'These "{prefix}" tables could not be converted to utf8mb4:\n  {listed}\n\n'
        'The migration is safe to run again — tables already converted are '
        'skipped. If the failure mentions an index being too long, the database '
        'server is old enough to need innodb_large_prefix=ON and '
        'innodb_file_format=Barracuda, which the host has to set.'
    )


def migration_operation(prefix):
    """A RunPython function that converts one app's tables. MySQL only."""
    def to_utf8mb4(apps, schema_editor):
        connection = schema_editor.connection
        if connection.vendor != 'mysql':
            # SQLite stores text as UTF-8 and has no per-table charset, so the
            # development database and the test runner have nothing to do here.
            return
        _converted, _skipped, failures = convert_prefix(connection, prefix)
        if failures:
            raise RuntimeError(failure_report(prefix, failures))

    return to_utf8mb4


def irreversible(apps, schema_editor):
    """Going back to latin1 would not restore anything.

    It would drop every character that made the conversion necessary, so the
    migration refuses rather than quietly destroying text.
    """
    from django.db.migrations.exceptions import IrreversibleError

    raise IrreversibleError(
        'Converting back to latin1 would drop characters that cannot be stored in it.'
    )
