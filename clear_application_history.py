"""
Script to clear all application history for fresh job applications.

This clears:
1. User database: emails_sent_history, contact_history, handshake_dm_history, handshake_applications_history
2. Global tracking: workflow_company_log.json, handshake_dm_log.json, handshake_applications_log.json
"""

from app import app, db
from models import User
import json
import os

def clear_all_history():
    """Clear all application history from database and tracking files."""

    with app.app_context():
        # Get all users
        users = User.query.all()

        print(f"Found {len(users)} user(s) in database")

        for user in users:
            print(f"\nClearing history for user: {user.username}")

            # Clear email campaign history
            user.emails_sent_history = '[]'
            user.contact_history = '[]'
            print(f"  - Cleared email campaign history")

            # Clear Handshake DM history
            user.handshake_dm_history = '[]'
            print(f"  - Cleared Handshake DM history")

            # Clear Handshake job applications history
            user.handshake_applications_history = '[]'
            print(f"  - Cleared Handshake applications history")

        # Commit database changes
        db.session.commit()
        print("\n[OK] Database changes committed")

    # Clear global tracking files
    print("\nClearing global tracking files...")

    tracking_files = [
        'workflow_company_log.json',
        'handshake_dm_log.json',
        'handshake_applications_log.json'
    ]

    for filename in tracking_files:
        filepath = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(filepath):
            # Clear the file by writing empty array
            with open(filepath, 'w') as f:
                json.dump([], f)
            print(f"  - Cleared {filename}")
        else:
            print(f"  - {filename} does not exist (skipping)")

    print("\n" + "="*60)
    print("All application history has been cleared!")
    print("You can now apply to companies again.")
    print("="*60)

if __name__ == '__main__':
    print("="*60)
    print("Clear All Application History")
    print("="*60)
    print("\nWARNING: This will delete all records of:")
    print("  - Email campaigns sent")
    print("  - Companies contacted via email")
    print("  - Handshake DMs sent")
    print("  - Handshake job applications")
    print("\n" + "="*60)

    response = input("Are you sure you want to continue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        clear_all_history()
    else:
        print("\nOperation cancelled.")
