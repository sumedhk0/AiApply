"""
Database Migration Script: Add Transcript Support

This script adds the transcript_filename field to the User model
to support transcript file uploads.
"""

from app import app, db
from sqlalchemy import text

def migrate_transcript_field():
    """Add transcript_filename column to user table if it doesn't exist."""

    with app.app_context():
        try:
            # Check if column already exists
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(user)"))
                columns = [row[1] for row in result]

                if 'transcript_filename' not in columns:
                    print("Adding transcript_filename column to user table...")
                    conn.execute(text(
                        "ALTER TABLE user ADD COLUMN transcript_filename VARCHAR(200) DEFAULT ''"
                    ))
                    conn.commit()
                    print("[OK] Successfully added transcript_filename column")
                else:
                    print("[OK] transcript_filename column already exists")

        except Exception as e:
            print(f"[ERROR] Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    print("="*60)
    print("Database Migration: Transcript Support")
    print("="*60)
    migrate_transcript_field()
    print("\n" + "="*60)
    print("Migration completed successfully!")
    print("="*60)
