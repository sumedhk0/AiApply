"""
Database migration script to remove Handshake credential fields.

This script removes the handshake_email and handshake_password columns from the User table
since users now log in manually to Handshake instead of storing credentials.
"""

import sqlite3
import os
import shutil
from datetime import datetime

def migrate_database():
    """Remove handshake_email and handshake_password columns from User table."""

    db_path = os.path.join('instance', 'users.db')

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("No migration needed - database will be created with new schema")
        return

    # Create backup
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Created backup at: {backup_path}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(user)")
        columns = [row[1] for row in cursor.fetchall()]

        columns_to_remove = ['handshake_email', 'handshake_password']
        existing_columns_to_remove = [col for col in columns_to_remove if col in columns]

        if not existing_columns_to_remove:
            print("✓ Columns already removed - no migration needed")
            conn.close()
            return

        print(f"Found columns to remove: {existing_columns_to_remove}")

        # SQLite doesn't support DROP COLUMN directly, so we need to:
        # 1. Create a new table without those columns
        # 2. Copy data from old table to new table
        # 3. Drop old table
        # 4. Rename new table

        # Get all columns except the ones we want to remove
        keep_columns = [col for col in columns if col not in columns_to_remove]

        print(f"Keeping columns: {keep_columns}")

        # Get the full schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user'")
        old_schema = cursor.fetchone()[0]

        # Create new table with updated schema (without handshake credentials)
        new_schema = """
        CREATE TABLE user_new (
            id INTEGER PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(200) NOT NULL,
            location VARCHAR(100) DEFAULT '',
            industry VARCHAR(100) DEFAULT '',
            num_emails INTEGER DEFAULT 5,
            custom_message TEXT DEFAULT '',
            sender_email VARCHAR(120) DEFAULT '',
            sender_password VARCHAR(200) DEFAULT '',
            resume_filename VARCHAR(200) DEFAULT '',
            emails_sent_history TEXT DEFAULT '[]',
            contact_history TEXT DEFAULT '[]',
            handshake_city VARCHAR(100) DEFAULT '',
            handshake_job_type VARCHAR(200) DEFAULT '',
            handshake_num_dms INTEGER DEFAULT 10,
            handshake_dm_history TEXT DEFAULT '[]'
        )
        """

        cursor.execute(new_schema)
        print("✓ Created new table schema")

        # Copy data from old table to new table
        columns_to_copy = ', '.join(keep_columns)
        cursor.execute(f"INSERT INTO user_new ({columns_to_copy}) SELECT {columns_to_copy} FROM user")
        print(f"✓ Copied {cursor.rowcount} rows to new table")

        # Drop old table
        cursor.execute("DROP TABLE user")
        print("✓ Dropped old table")

        # Rename new table
        cursor.execute("ALTER TABLE user_new RENAME TO user")
        print("✓ Renamed new table to 'user'")

        # Commit changes
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print(f"Removed columns: {existing_columns_to_remove}")

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        print(f"Database backup available at: {backup_path}")
        conn.rollback()
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: Remove Handshake Credentials")
    print("=" * 60)
    print("\nThis migration will remove the following columns:")
    print("  - handshake_email")
    print("  - handshake_password")
    print("\nUsers will now log into Handshake manually instead.")
    print("=" * 60)

    response = input("\nProceed with migration? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        print("\nStarting migration...\n")
        migrate_database()
    else:
        print("\nMigration cancelled.")
