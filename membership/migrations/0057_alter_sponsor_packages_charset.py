from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('membership', '0056_seed_default_sponsorship_packages'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE `membership_eltanconference` MODIFY `sponsor_packages` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
