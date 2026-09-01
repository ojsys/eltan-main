"""Store real names: convert the account tables to utf8mb4.

The database was created with latin1 as its default charset, which cannot hold a
name spelled with a character English does not use — MySQL rejects the whole
write rather than mangling it. Every member whose surname carries an accent has
been unable to have it stored correctly.

The tables are small (one model, plus its two permission join tables), so this
runs quickly. See eltanweb/dbcharset.py for what the conversion does and why the
row format is changed first.
"""

from django.db import migrations

from eltanweb import dbcharset


class Migration(migrations.Migration):

    # MySQL commits each ALTER as it goes; no transaction will roll this back,
    # and pretending otherwise only hides that from whoever reads it.
    atomic = False

    dependencies = [
        ('account', '0005_customuser_eltan_number'),
    ]

    operations = [
        migrations.RunPython(
            dbcharset.migration_operation('account_'),
            dbcharset.irreversible,
        ),
    ]
