"""
Script to restore email and DM history to user database from global log files.
This keeps the applications history cleared but restores contact history.
"""

from app import app, db
from models import User
import json
import os

def restore_history():
    """Restore email and DM history from global tracking files."""

    with app.app_context():
        # Get the user
        user = User.query.first()

        if not user:
            print("No user found in database!")
            return

        print(f"Restoring history for user: {user.username}\n")

        # Restore email history from workflow_company_log.json
        workflow_log_path = 'workflow_company_log.json'
        if os.path.exists(workflow_log_path):
            with open(workflow_log_path, 'r') as f:
                workflow_data = json.load(f)

            emails_sent = workflow_data.get('emails_sent', [])

            if emails_sent:
                # Restore emails_sent_history
                user.emails_sent_history = json.dumps(emails_sent)
                print(f"[OK] Restored {len(emails_sent)} email addresses to emails_sent_history")

                # Create basic contact history entries
                contact_history = []
                for email in emails_sent:
                    # Extract company from email domain
                    if '@' in email:
                        domain = email.split('@')[1]
                        company_name = domain.split('.')[0].title()
                    else:
                        company_name = "Unknown"

                    contact_history.append({
                        'company_name': company_name,
                        'contact_name': 'N/A',
                        'email_address': email,
                        'email_summary': 'Email campaign sent (history restored)',
                        'date_sent': '2025-01-01T00:00:00'  # Placeholder date
                    })

                user.contact_history = json.dumps(contact_history)
                print(f"[OK] Recreated {len(contact_history)} contact history entries")
            else:
                print("[INFO] No email history found in workflow_company_log.json")
        else:
            print("[INFO] workflow_company_log.json not found")

        # Restore Handshake DM history from handshake_dm_log.json
        dm_log_path = 'handshake_dm_log.json'
        if os.path.exists(dm_log_path):
            with open(dm_log_path, 'r') as f:
                dm_data = json.load(f)

            if dm_data and len(dm_data) > 0:
                user.handshake_dm_history = json.dumps(dm_data)
                print(f"[OK] Restored {len(dm_data)} Handshake DM records")
            else:
                print("[INFO] No DM history found in handshake_dm_log.json")
        else:
            print("[INFO] handshake_dm_log.json not found")

        # Keep handshake_applications_history cleared (as requested)
        user.handshake_applications_history = '[]'
        print("[OK] Kept Handshake applications history cleared\n")

        # Commit changes
        db.session.commit()
        print("="*60)
        print("History restoration complete!")
        print("- Email and DM history: RESTORED")
        print("- Job applications history: CLEARED")
        print("="*60)

if __name__ == '__main__':
    print("="*60)
    print("Restore Email and DM History")
    print("="*60)
    print()
    restore_history()
