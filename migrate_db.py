"""
Database migration script to add contact_history column to User table.
Run this once to update your existing database.
"""
import sqlite3
import os

DB_PATH = os.path.join('instance', 'users.db')

def migrate():
    """Add contact_history column if it doesn't exist."""
    if not os.path.exists(DB_PATH):
        print("No database found. Run app.py first to create the database.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'contact_history' not in columns:
            print("Adding contact_history column to user table...")
            cursor.execute("ALTER TABLE user ADD COLUMN contact_history TEXT DEFAULT '[]'")
            conn.commit()
            print("[SUCCESS] Migration completed successfully!")
        else:
            print("[OK] contact_history column already exists. No migration needed.")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
