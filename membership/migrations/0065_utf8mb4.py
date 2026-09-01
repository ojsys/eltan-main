"""Convert the membership tables to utf8mb4.

Same cause as everywhere else on this site: a database whose default charset is
latin1, so every table inherited it. Membership holds names, addresses, state
chapters and payment references — all of which can carry a character latin1
cannot store, and any one of which fails the write outright.

This is the largest set of tables in the project (twenty-five), and converting
rewrites every row while holding a lock on the table. Run it when the site is
quiet, and take a dump first. If it stops partway, run it again: tables already
converted are skipped.
"""

from django.db import migrations

from eltanweb import dbcharset


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('membership', '0064_certificatesignatory_subscription_receipt_error_and_more'),
    ]

    operations = [
        migrations.RunPython(
            dbcharset.migration_operation('membership_'),
            dbcharset.irreversible,
        ),
    ]
