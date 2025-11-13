"""
Clear Contact History Migration Script

This script clears:
1. User email contact history (contact_history field)
2. User Handshake DM history (handshake_dm_history field)
3. Global workflow_company_log.json
4. Global handshake_dm_log.json

Run this to reset all contact tracking data and start fresh.
"""

from app import app, db
from models import User
from sqlalchemy import text
import json
import os

def clear_all_contact_data():
    """Clear all contact history data from database and JSON files."""

    with app.app_context():
        print("="*60)
        print("CLEARING ALL CONTACT HISTORY DATA")
        print("="*60)

        # Clear user database fields
        print("\n[1/4] Clearing user contact_history in database...")
        users = User.query.all()
        for user in users:
            old_contact_count = len(user.get_contact_history())
            user.contact_history = '[]'
            print(f"   User {user.id} ({user.username}): Cleared {old_contact_count} email contacts")

        print("\n[2/4] Clearing user handshake_dm_history in database...")
        for user in users:
            old_dm_count = len(user.get_handshake_dm_history())
            user.handshake_dm_history = '[]'
            print(f"   User {user.id} ({user.username}): Cleared {old_dm_count} Handshake DMs")

        db.session.commit()
        print("   [OK] Database changes committed")

        # Clear global JSON logs
        print("\n[3/4] Clearing global workflow_company_log.json...")
        workflow_log_path = os.path.join(os.path.dirname(__file__), 'workflow_company_log.json')
        if os.path.exists(workflow_log_path):
            with open(workflow_log_path, 'r') as f:
                old_data = json.load(f)
                old_count = len(old_data.get('emails_sent', []))

            with open(workflow_log_path, 'w') as f:
                json.dump({'emails_sent': []}, f, indent=2)
            print(f"   [OK] Cleared {old_count} emails from global log")
        else:
            print("   [OK] File doesn't exist (will be created on first email campaign)")

        print("\n[4/4] Clearing global handshake_dm_log.json...")
        dm_log_path = os.path.join(os.path.dirname(__file__), 'handshake_dm_log.json')
        if os.path.exists(dm_log_path):
            with open(dm_log_path, 'r') as f:
                old_data = json.load(f)
                old_count = len(old_data.get('contacted_companies', []))

            with open(dm_log_path, 'w') as f:
                json.dump({
                    'contacted_companies': [],
                    'last_updated': None
                }, f, indent=2)
            print(f"   [OK] Cleared {old_count} companies from global log")
        else:
            print("   [OK] File doesn't exist (will be created on first DM campaign)")

        print("\n" + "="*60)
        print("MIGRATION COMPLETE")
        print("="*60)
        print("\nAll contact history data has been cleared.")
        print("Future email campaigns and Handshake DMs will be tracked with complete data.")
        print("="*60)

if __name__ == "__main__":
    import sys

    print("\nThis script will permanently delete:")
    print("  - All email contact history")
    print("  - All Handshake DM history")
    print("  - Global workflow log")
    print("  - Global Handshake DM log")

    # Check for --force flag
    if '--force' in sys.argv:
        print("\n--force flag detected, proceeding with migration...")
        clear_all_contact_data()
    else:
        confirm = input("\nType 'yes' to proceed (or use --force flag): ")
        if confirm.lower() == 'yes':
            clear_all_contact_data()
        else:
            print("\nMigration cancelled.")
