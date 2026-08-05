"""Make ELTAN years consistent and admin-managed.

Three things happen here:

1. Every ``eltan_year`` value is rewritten to the canonical ``YYYY-YYYY`` form.
   Historic rows mix ``2024/2025`` and ``2024-2025``, so the same year behaved
   like two different years in filters, dropdowns and `update_or_create` lookups.

2. ELTANYearSetting rows get sane start/end dates. A year whose stored end date
   does not land in the year the label names (e.g. 2025-2026 ending 2025-09-30)
   is reset to the standard 1 Sep -> 31 Aug span.

3. The set of years is filled in so it is continuous from the earliest year in
   use up to two years ahead of today — which is what makes 2026-2027 (and the
   year after) selectable without anyone editing code.
"""

import re
from datetime import date

from django.db import migrations

YEAR_RE = re.compile(r'^(\d{4})\s*[-/]\s*(\d{4})$')


def _normalize(value):
    if not value:
        return ''
    match = YEAR_RE.match(str(value).strip())
    if not match:
        return str(value).strip()
    return f"{match.group(1)}-{match.group(2)}"


def _start_year(label):
    match = YEAR_RE.match(label or '')
    return int(match.group(1)) if match else None


def forwards(apps, schema_editor):
    Subscription = apps.get_model('membership', 'Subscription')
    YearSetting = apps.get_model('membership', 'ELTANYearSetting')

    # --- 1. Canonicalise subscription year labels -------------------------
    seen = {}
    collisions = []
    for sub in Subscription.objects.all().order_by('id'):
        label = _normalize(sub.eltan_year)
        if not label:
            continue
        key = (sub.user_id, label)
        if key in seen:
            collisions.append((sub.user_id, label, seen[key], sub.id))
        else:
            seen[key] = sub.id
        if label != sub.eltan_year:
            sub.eltan_year = label
            sub.save(update_fields=['eltan_year'])

    if collisions:
        # Left in place on purpose — merging paid/pending subscriptions is a
        # judgement call for an admin, not something a migration should guess.
        print(
            "\n  NOTE: duplicate subscriptions exist for the same user+year after "
            "normalisation (review them in the admin):"
        )
        for user_id, label, kept, dupe in collisions:
            print(f"    user {user_id} year {label}: subscription #{kept} and #{dupe}")

    # --- 2. Canonicalise + repair the configured years --------------------
    for setting in YearSetting.objects.all():
        label = _normalize(setting.eltan_year)
        start_year = _start_year(label)
        changed = label != setting.eltan_year
        setting.eltan_year = label

        if start_year is not None:
            expected_start = date(start_year, 9, 1)
            expected_end = date(start_year + 1, 8, 31)
            # Only replace a date that cannot be right for this label; a
            # deliberately customised span within the correct years is kept.
            if not setting.start_date or setting.start_date.year != start_year:
                setting.start_date = expected_start
                changed = True
            if not setting.end_date or setting.end_date.year != start_year + 1:
                setting.end_date = expected_end
                changed = True

        if changed:
            setting.save()

    # --- 3. Fill in the year list -----------------------------------------
    used_years = {
        _start_year(label)
        for label in Subscription.objects.values_list('eltan_year', flat=True).distinct()
    }
    used_years |= {_start_year(s.eltan_year) for s in YearSetting.objects.all()}
    used_years.discard(None)

    today = date.today()
    current_start = today.year if today.month >= 9 else today.year - 1
    # Two years ahead so the next ELTAN year is always available to pick early.
    latest = current_start + 2
    earliest = min(used_years) if used_years else current_start

    for start_year in range(earliest, latest + 1):
        label = f"{start_year}-{start_year + 1}"
        YearSetting.objects.get_or_create(
            eltan_year=label,
            defaults={
                'start_date': date(start_year, 9, 1),
                'end_date': date(start_year + 1, 8, 31),
                'is_active': False,
                'is_selectable': True,
            },
        )

    # --- 4. Exactly one current year --------------------------------------
    current_label = f"{current_start}-{current_start + 1}"
    YearSetting.objects.update(is_active=False)
    YearSetting.objects.filter(eltan_year=current_label).update(is_active=True)
    if not YearSetting.objects.filter(is_active=True).exists():
        newest = YearSetting.objects.order_by('-eltan_year').first()
        if newest:
            newest.is_active = True
            newest.save(update_fields=['is_active'])


def backwards(apps, schema_editor):
    # Normalisation is not meaningfully reversible, and re-introducing the mixed
    # '/' spelling would only recreate the bug.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('membership', '0061_alter_eltanyearsetting_options_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
