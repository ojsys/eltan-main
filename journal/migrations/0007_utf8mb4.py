"""Store real prose: convert the journal's tables to utf8mb4.

The production database was created with latin1 as its default charset, so every
table — and every column any migration has added since — inherited it. Nothing
noticed while the journal held only ASCII, but an article read out of a Word
manuscript is full of things latin1 cannot store: curly quotes and apostrophes,
en dashes, and any author whose name is spelled with a character English does
not use. MySQL rejects those outright rather than mangling them, which is how a
Polish surname turned into

    (1366, "Incorrect string value: '\\xC5\\x82o\\xC5\\x84s...'")

on the way into ``journal_article.body_html``.

A note on the existing rows. ``CONVERT TO CHARACTER SET`` reads what is stored
as latin1 and re-encodes it, which is lossless for data that really is latin1 —
and it is here, because the column has been rejecting anything else, which is
the whole bug. The one case it would damage is a column that had UTF-8 bytes
smuggled into it by a latin1 *connection*; this site's connection has been
utf8mb4 throughout (see settings/production.py), so that has not happened. Take
a dump first regardless, and spot-check a record with punctuation in it after.

Each app converts its own tables. ``manage.py db_charset`` reports on the rest
of the database and converts whatever is left.
"""

from django.db import migrations

from eltanweb import dbcharset


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('journal', '0006_article_body_html_article_source_file_and_more'),
    ]

    operations = [
        migrations.RunPython(
            dbcharset.migration_operation('journal_'),
            dbcharset.irreversible,
        ),
    ]
