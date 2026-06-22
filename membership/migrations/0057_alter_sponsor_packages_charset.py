from django.db import migrations


def set_utf8mb4_charset(apps, schema_editor):
    # MySQL-only: convert the column to utf8mb4 so emoji/extended chars are stored.
    # No-op on other backends (e.g. SQLite used in local development).
    if schema_editor.connection.vendor != 'mysql':
        return
    schema_editor.execute(
        "ALTER TABLE `membership_eltanconference` "
        "MODIFY `sponsor_packages` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('membership', '0056_seed_default_sponsorship_packages'),
    ]

    operations = [
        migrations.RunPython(set_utf8mb4_charset, migrations.RunPython.noop),
    ]
