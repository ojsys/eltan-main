from django.db import migrations


def set_utf8mb4_charset(apps, schema_editor):
    # MySQL-only: convert the column to utf8mb4 so emoji/extended chars are stored.
    # No-op on other backends (e.g. SQLite used in local development).
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return
    # A raw cursor rather than schema_editor.execute(): the schema editor refuses
    # to run DDL inside a transaction on a backend that cannot roll it back, and
    # MySQL cannot. Left as it was, this migration could only ever raise
    # TransactionManagementError on the database it exists for.
    with connection.cursor() as cursor:
        cursor.execute(
            'ALTER TABLE `membership_eltanconference` '
            'MODIFY `sponsor_packages` LONGTEXT CHARACTER SET utf8mb4 '
            'COLLATE utf8mb4_unicode_ci'
        )


class Migration(migrations.Migration):

    # MySQL commits each ALTER as it goes, so there is no transaction to wrap
    # this in; saying so is what lets the DDL run at all.
    atomic = False

    dependencies = [
        ('membership', '0056_seed_default_sponsorship_packages'),
    ]

    operations = [
        migrations.RunPython(set_utf8mb4_charset, migrations.RunPython.noop),
    ]
