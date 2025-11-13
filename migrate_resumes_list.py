"""
Database migration script to add resumes_list column to User table.
This allows users to manage multiple resumes with their original names.
"""

from app import app, db
from models import User
from sqlalchemy import text
import json

def migrate_resumes_list():
    """Add resumes_list column if it doesn't exist and migrate existing resume data."""
    with app.app_context():
        with db.engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result]

            if 'resumes_list' not in columns:
                print("Adding resumes_list column...")
                conn.execute(text("ALTER TABLE user ADD COLUMN resumes_list TEXT DEFAULT '[]'"))
                conn.commit()
                print("Column added successfully!")

                # Migrate existing resume data
                print("\nMigrating existing resume data...")
                users = db.session.query(User).all()

                for user in users:
                    if user.resume_filename and user.resume_filename.strip():
                        # Extract original filename from stored filename
                        # Format: user_{id}_{original_name}.pdf
                        stored_filename = user.resume_filename
                        parts = stored_filename.split('_', 2)  # Split into max 3 parts

                        if len(parts) >= 3:
                            original_name = parts[2]  # Get everything after user_{id}_
                        else:
                            original_name = stored_filename

                        print(f"  Migrating resume for user {user.username}: {original_name}")

                        # Add to resumes list
                        user.add_resume(original_name, stored_filename)

                db.session.commit()
                print(f"\nMigrated resume data for {len([u for u in users if u.resume_filename])} users")
            else:
                print("Column 'resumes_list' already exists. No migration needed.")

if __name__ == '__main__':
    migrate_resumes_list()
    print("\nMigration complete!")
