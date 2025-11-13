from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication and storing user preferences."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    # Job search preferences
    location = db.Column(db.String(100), default='')
    industry = db.Column(db.String(100), default='')
    num_emails = db.Column(db.Integer, default=5)
    custom_message = db.Column(db.Text, default='')

    # Email credentials (stored for convenience)
    sender_email = db.Column(db.String(120), default='')
    sender_password = db.Column(db.String(200), default='')

    # Resume storage
    resume_filename = db.Column(db.String(200), default='')

    # Resume list - JSON array of resume objects
    # Each entry: {original_name, stored_filename, upload_date}
    resumes_list = db.Column(db.Text, default='[]')

    # Transcript storage (single file)
    transcript_filename = db.Column(db.String(200), default='')

    # Email tracking - JSON array of all emails sent by this user
    emails_sent_history = db.Column(db.Text, default='[]')

    # Detailed contact history - JSON array of contact objects
    # Each entry: {company_name, contact_name, email_address, email_summary, date_sent}
    contact_history = db.Column(db.Text, default='[]')

    # Handshake DM preferences (credentials removed - users log in manually)
    handshake_city = db.Column(db.String(100), default='')
    handshake_job_type = db.Column(db.String(200), default='')
    handshake_num_dms = db.Column(db.Integer, default=10)

    # Handshake DM history - JSON array of companies contacted via Handshake
    # Each entry: {company_name, job_title, recruiter_name, message_sent, date_sent}
    handshake_dm_history = db.Column(db.Text, default='[]')

    # Handshake job applications history - JSON array of jobs applied to
    # Each entry: {job_id, job_title, company_name, applied_date, tailored_resume_path}
    handshake_applications_history = db.Column(db.Text, default='[]')

    def set_password(self, password):
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        """Check if the provided password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def get_emails_sent(self):
        """Get the list of emails this user has already sent to."""
        import json
        try:
            return json.loads(self.emails_sent_history or '[]')
        except:
            return []

    def get_contacted_domains(self):
        """Get the set of domains this user has already contacted."""
        emails = self.get_emails_sent()
        domains = set()
        for email in emails:
            if '@' in email:
                domain = email.split('@')[1]
                domains.add(domain)
        return domains

    def add_sent_emails(self, email_list):
        """Add a list of emails to the user's sent history."""
        import json
        current_emails = set(self.get_emails_sent())
        current_emails.update(email_list)
        self.emails_sent_history = json.dumps(list(current_emails))

    def get_contact_history(self):
        """Get the list of detailed contacts this user has sent to."""
        import json
        try:
            return json.loads(self.contact_history or '[]')
        except:
            return []

    def add_contact_history(self, contacts_data):
        """
        Add detailed contact information to history.

        Args:
            contacts_data: List of dicts with keys: company_name, contact_name,
                          email_address, email_body (optional), date_sent (optional)
        """
        import json
        from datetime import datetime

        current_history = self.get_contact_history()

        for contact in contacts_data:
            # Validate that contact is a dictionary
            if not isinstance(contact, dict):
                print(f"Warning: Skipping invalid contact (expected dict, got {type(contact).__name__}): {contact}")
                continue

            # Extract first 100 chars of email_body as summary
            email_body = contact.get('email_body', '')
            email_summary = email_body[:100] + '...' if len(email_body) > 100 else email_body

            # Create contact entry
            contact_entry = {
                'company_name': contact.get('company_name', 'Unknown'),
                'contact_name': contact.get('contact_name') or 'N/A',
                'email_address': contact.get('email_address', ''),
                'email_summary': email_summary,
                'date_sent': contact.get('date_sent') or datetime.now().isoformat()
            }

            # Add to history (avoiding duplicates based on email address)
            if not any(c['email_address'] == contact_entry['email_address'] for c in current_history):
                current_history.append(contact_entry)

        self.contact_history = json.dumps(current_history)

    def get_handshake_dm_history(self):
        """Get the list of companies contacted via Handshake DMs."""
        import json
        try:
            return json.loads(self.handshake_dm_history or '[]')
        except:
            return []

    def get_handshake_contacted_companies(self):
        """Get the set of companies this user has already contacted via Handshake."""
        dms = self.get_handshake_dm_history()
        companies = set()
        for dm in dms:
            company_name = dm.get('company_name', '')
            if company_name:
                companies.add(company_name)
        return companies

    def add_handshake_dm_history(self, dm_data):
        """
        Add Handshake DM information to history.

        Args:
            dm_data: List of dicts with keys: company_name, job_title,
                    recruiter_name, message_sent, date_sent
        """
        import json
        from datetime import datetime

        current_history = self.get_handshake_dm_history()

        for dm in dm_data:
            # Create DM entry
            dm_entry = {
                'company_name': dm.get('company_name', 'Unknown'),
                'job_title': dm.get('job_title', 'N/A'),
                'recruiter_name': dm.get('recruiter_name') or 'N/A',
                'message_summary': dm.get('message_sent', '')[:100] + '...' if len(dm.get('message_sent', '')) > 100 else dm.get('message_sent', ''),
                'date_sent': dm.get('date_sent') or datetime.now().isoformat()
            }

            # Add to history (avoiding duplicates based on company name and date)
            if not any(c['company_name'] == dm_entry['company_name'] and
                      c['date_sent'][:10] == dm_entry['date_sent'][:10] for c in current_history):
                current_history.append(dm_entry)

        self.handshake_dm_history = json.dumps(current_history)

    def get_resumes_list(self):
        """Get the list of all resumes uploaded by this user."""
        import json
        try:
            return json.loads(self.resumes_list or '[]')
        except:
            return []

    def add_resume(self, original_name, stored_filename):
        """Add a resume to the user's resumes list."""
        import json
        from datetime import datetime

        current_resumes = self.get_resumes_list()

        # Check if this resume already exists (by stored filename)
        for resume in current_resumes:
            if resume.get('stored_filename') == stored_filename:
                # Update upload date
                resume['upload_date'] = datetime.now().isoformat()
                self.resumes_list = json.dumps(current_resumes)
                return

        # Add new resume
        resume_entry = {
            'original_name': original_name,
            'stored_filename': stored_filename,
            'upload_date': datetime.now().isoformat()
        }
        current_resumes.append(resume_entry)
        self.resumes_list = json.dumps(current_resumes)
        print(self.resumes_list)

    def remove_resume(self, stored_filename):
        """Remove a resume from the user's resumes list."""
        import json

        current_resumes = self.get_resumes_list()
        current_resumes = [r for r in current_resumes if r.get('stored_filename') != stored_filename]
        self.resumes_list = json.dumps(current_resumes)

    def get_transcript_path(self):
        """Get the full path to the user's current transcript."""
        import os
        if self.transcript_filename:
            return os.path.join('user_transcripts', self.transcript_filename)
        return None

    def get_handshake_applications_history(self):
        """Get the list of Handshake job applications."""
        import json
        try:
            return json.loads(self.handshake_applications_history or '[]')
        except:
            return []

    def add_handshake_application(self, job_id, job_title, company_name, tailored_resume_path=None, cover_letter_path=None):
        """
        Add a Handshake job application to history.

        Args:
            job_id: Unique job ID from Handshake
            job_title: Title of the job
            company_name: Name of the company
            tailored_resume_path: Path to the tailored resume (optional)
            cover_letter_path: Path to the generated cover letter (optional)
        """
        import json
        from datetime import datetime

        current_history = self.get_handshake_applications_history()

        # Check if already applied to this job
        if any(app.get('job_id') == job_id for app in current_history):
            return  # Already applied

        application_entry = {
            'job_id': job_id,
            'job_title': job_title,
            'company_name': company_name,
            'applied_date': datetime.now().isoformat(),
            'tailored_resume_path': tailored_resume_path or 'N/A',
            'cover_letter_path': cover_letter_path or 'N/A'
        }

        current_history.append(application_entry)
        self.handshake_applications_history = json.dumps(current_history)

    def get_handshake_applied_job_ids(self):
        """Get the set of job IDs that have been applied to."""
        applications = self.get_handshake_applications_history()
        return set(app.get('job_id') for app in applications if app.get('job_id'))

    def __repr__(self):
        return f'<User {self.username}>'
