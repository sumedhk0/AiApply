"""
Database Migration Script for Handshake DM Feature

This script adds the new Handshake-related columns to the User table.
Run this script to update your existing database schema.
"""

from app import app, db
from models import User
import sqlite3

def migrate_database():
    """Add new Handshake columns to the User table."""

    print("Starting database migration for Handshake DM feature...")

    # Get database file path
    db_path = 'instance/users.db'

    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # List of new columns to add
        new_columns = [
            ("handshake_email", "VARCHAR(120)", "''"),
            ("handshake_password", "VARCHAR(200)", "''"),
            ("handshake_city", "VARCHAR(100)", "''"),
            ("handshake_job_type", "VARCHAR(200)", "''"),
            ("handshake_num_dms", "INTEGER", "10"),
            ("handshake_dm_history", "TEXT", "'[]'")
        ]

        # Check which columns already exist
        cursor.execute("PRAGMA table_info(user)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        # Add each column if it doesn't exist
        for col_name, col_type, default_value in new_columns:
            if col_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE user ADD COLUMN {col_name} {col_type} DEFAULT {default_value}"
                    cursor.execute(sql)
                    print(f"[OK] Added column: {col_name}")
                except sqlite3.OperationalError as e:
                    print(f"[ERROR] Error adding column {col_name}: {e}")
            else:
                print(f"[SKIP] Column {col_name} already exists, skipping")

        # Commit changes
        conn.commit()
        print("\n[SUCCESS] Database migration completed successfully!")

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        return False

    finally:
        if conn:
            conn.close()

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Handshake DM Feature - Database Migration")
    print("=" * 60)

    with app.app_context():
        success = migrate_database()

        if success:
            print("\nYou can now use the Handshake DM automation feature!")
        else:
            print("\nMigration failed. Please check the errors above.")
