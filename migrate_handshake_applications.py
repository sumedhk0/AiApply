"""
Database migration script to add handshake_applications_history column to User table.

Run this script once to update existing databases with the new column for tracking
Handshake job applications.
"""

from app import app, db
from sqlalchemy import text

def migrate_database():
    """Add handshake_applications_history column if it doesn't exist."""
    with app.app_context():
        with db.engine.connect() as conn:
            # Check if column already exists
            result = conn.execute(text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result]

            if 'handshake_applications_history' not in columns:
                print("Adding handshake_applications_history column to user table...")
                conn.execute(text(
                    "ALTER TABLE user ADD COLUMN handshake_applications_history TEXT DEFAULT '[]'"
                ))
                conn.commit()
                print("Successfully added handshake_applications_history column!")
            else:
                print("Column handshake_applications_history already exists. No migration needed.")

if __name__ == "__main__":
    print("="*60)
    print("Database Migration: Add Handshake Applications History")
    print("="*60)
    migrate_database()
    print("="*60)
    print("Migration complete!")
    print("="*60)
