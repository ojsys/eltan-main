"""
Script to clean up orphaned foreign key references before migration.
This addresses IntegrityError issues in the database.
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eltanweb.settings.development')
os.environ.setdefault('ELTAN_ENV', 'development')
django.setup()

from django.db import connection

def cleanup_orphaned_data():
    """Clean up all orphaned foreign key references"""
    with connection.cursor() as cursor:
        print("🧹 Cleaning up orphaned data...")

        # Get list of valid user IDs
        print("\n1. Checking valid user IDs...")
        cursor.execute("SELECT id FROM account_customuser")
        valid_user_ids = [row[0] for row in cursor.fetchall()]
        print(f"   Found {len(valid_user_ids)} valid users")

        # Clean up user-related tables
        tables_to_clean = [
            ('django_admin_log', 'user_id'),
            ('account_customuser_groups', 'customuser_id'),
            ('account_customuser_user_permissions', 'customuser_id'),
            ('membership_subscription', 'user_id'),
            ('membership_sigsregistration', 'user_id'),
            ('membership_conferenceregistration', 'user_id'),
        ]

        total_deleted = 0
        for table, column in tables_to_clean:
            try:
                cursor.execute(f"""
                    DELETE FROM {table}
                    WHERE {column} NOT IN (SELECT id FROM account_customuser)
                """)
                deleted = cursor.rowcount
                if deleted > 0:
                    print(f"   ✓ Deleted {deleted} orphaned rows from {table}")
                    total_deleted += deleted
            except Exception as e:
                print(f"   ⚠ Skipped {table}: {str(e)}")

        # Clean up content type references
        print("\n2. Cleaning orphaned content type references...")
        try:
            cursor.execute("""
                DELETE FROM django_admin_log
                WHERE content_type_id NOT IN (SELECT id FROM django_content_type)
            """)
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"   ✓ Deleted {deleted} orphaned content type rows")
                total_deleted += deleted
        except Exception as e:
            print(f"   ⚠ Error: {str(e)}")

        # Clean up conference schedule speaker references
        print("\n3. Cleaning orphaned conference speaker references...")
        try:
            cursor.execute("""
                DELETE FROM membership_conferenceschedule
                WHERE speaker_id NOT IN (SELECT id FROM membership_conferencespeaker)
            """)
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"   ✓ Deleted {deleted} orphaned schedule rows")
                total_deleted += deleted
        except Exception as e:
            print(f"   ⚠ Error: {str(e)}")

        # List all tables with foreign keys for manual check
        print("\n4. Checking for other potential orphaned data...")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'django_migrations'
            ORDER BY name
        """)
        all_tables = [row[0] for row in cursor.fetchall()]

        # Check each table's schema for REFERENCES
        for table in all_tables:
            try:
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                schema = cursor.fetchone()[0]
                if 'REFERENCES' in schema and table not in [t[0] for t in tables_to_clean]:
                    # Try to find and clean any orphaned references
                    if 'user_id' in schema and 'account_customuser' in schema:
                        cursor.execute(f"""
                            DELETE FROM {table}
                            WHERE user_id NOT IN (SELECT id FROM account_customuser)
                        """)
                        deleted = cursor.rowcount
                        if deleted > 0:
                            print(f"   ✓ Deleted {deleted} orphaned rows from {table}")
                            total_deleted += deleted
            except Exception as e:
                pass  # Skip tables that don't match pattern

        print(f"\n✅ Cleanup complete! Total rows deleted: {total_deleted}")

        if total_deleted == 0:
            print("   No orphaned data found - database is clean!")

if __name__ == '__main__':
    try:
        cleanup_orphaned_data()
        print("\n✅ You can now run: python manage.py migrate")
    except Exception as e:
        print(f"\n❌ Error during cleanup: {str(e)}")
        sys.exit(1)
