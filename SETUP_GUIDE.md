# AI Job Application System - Setup Guide

## Overview
Your AI-powered job application system now includes a complete user authentication system with data persistence. Users can create accounts, save their preferences, and manage their automated job search campaigns.

## New Features
- User registration and login system
- Persistent storage of user preferences (location, industry, email credentials, resume)
- Form fields remain populated after sending emails
- Visual confirmation of successful email sending
- Support for custom number of emails per campaign (1-50)
- Custom message field for personalized requirements
- Resume upload with persistent storage
- **Handshake DM Automation**: Send personalized direct messages to recruiters on Handshake (NEW!)
- **Contact History**: View all email and Handshake contacts in one place (NEW!)

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```

The application will:
- Automatically create the SQLite database (`users.db`)
- Set up necessary folders (`uploads/`, `user_resumes/`)
- Start the Flask web server on http://0.0.0.0:5000

### 3. Access the Application
Open your browser and navigate to:
```
http://localhost:5000
```

## First Time Setup

### Create an Account
1. Click "Register here" on the login page
2. Choose a username and provide your email
3. Create a password (minimum 6 characters)
4. Click "Create Account"

### Login
1. Enter your username and password
2. Click "Login"
3. You'll be redirected to your dashboard

## Using the Dashboard

### Required Fields
- **Preferred Work Location**: City where you want to find opportunities
- **Industry Type**: Target industry (e.g., Clean Tech, AI/ML, FinTech)
- **Number of Emails**: How many companies to contact (1-50)
- **Your Email Address**: SMTP credentials for sending emails
- **Email Password**: Your email password or app-specific password
- **Resume**: PDF file (only required on first upload)

### Optional Fields
- **Custom Message**: Any specific talking points you want included in emails

### Sending Emails
1. Fill out the form (or use pre-populated values from previous session)
2. Click "Start Automated Job Search"
3. Wait for the confirmation message showing success/failure counts

### Important Notes
- **Your data is saved**: All form fields are automatically saved after each submission
- **Resume persistence**: Upload your resume once - it's saved for future campaigns
- **No data loss**: Form fields remain populated after sending emails (no need to re-enter)
- **Gmail users**: Use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password

## Using Handshake DM Automation (NEW!)

The system can now automatically send personalized direct messages to recruiters on Handshake using browser automation.

### Prerequisites
1. **Upload a resume first** in the Email Campaign tab
2. Have an active Handshake account with login credentials
3. **ChromeDriver**: Selenium will automatically use Chrome browser
   - Chrome browser must be installed on your system
   - ChromeDriver is managed automatically by webdriver-manager

### Setup Handshake Credentials
1. Navigate to the **Handshake DMs** tab
2. Click "Configure Handshake Credentials"
3. Enter your Handshake login email and password
4. Click "Save Credentials"

### Running a Handshake Campaign
1. **Preferred City**: Enter the city where you want to find jobs (e.g., "San Francisco")
2. **Job Type/Title**: Enter the job title you're searching for (e.g., "Software Engineer Intern")
3. **Number of DMs**: Choose how many DMs to send (1-50)
4. **Custom Message** (Optional): Add talking points to personalize your DMs
5. Click "Start Handshake DM Campaign"

### What Happens During a Campaign
1. A Chrome browser window will open (you'll see it on your screen)
2. The system logs into Handshake automatically
3. Searches for jobs matching your criteria
4. Clicks through job postings and sends personalized DMs
5. Tracks which companies you've contacted to avoid duplicates
6. Closes when complete or after sending the requested number of DMs

### Important Notes
- **Do not close the browser window** while the campaign is running
- The browser automation is visible (not headless) so you can see what's happening
- Campaign progress is shown in real-time on the webpage
- Companies you've already contacted will be automatically skipped
- All DM history is saved and visible in the Contact History tab

## How It Works

### Email Campaign Workflow (Three Stages)
1. **Contact Discovery**: Claude API finds companies matching your criteria
2. **Deduplication**: System filters out duplicate domains and previously contacted companies
3. **Email Generation & Sending**: Claude creates personalized emails and sends them via SMTP

### Handshake DM Workflow (Automated Browser)
1. **Browser Login**: Selenium WebDriver logs into your Handshake account
2. **Job Search**: Searches for jobs matching city and job type criteria
3. **Message Generation**: Claude API creates personalized DMs based on job details and your resume
4. **DM Sending**: Automated clicks through job postings and sends DMs to recruiters
5. **Tracking**: Saves company names to prevent duplicate contacts

### Data Storage
- **User accounts**: Stored in SQLite database (`users.db`)
- **Resumes**: Stored in `user_resumes/` folder
- **Email log**: Tracked in `workflow_company_log.json`
- **Daily logs**: Email operations logged to `email_log_YYYYMMDD.log`

## Logout
Click the "Logout" button in the top right corner of the dashboard.

## Troubleshooting

### Email Authentication Issues
- **Gmail**: Use an app-specific password, not your regular password
- **Outlook/Office365**: Regular password should work
- **Other providers**: May need to enable "less secure apps" or SMTP access

### Database Reset
If you need to reset the database:
```bash
# Delete the database file
rm users.db  # On Windows: del users.db

# Restart the app - it will create a fresh database
python app.py
```

### Resume Upload Issues
- Ensure file is PDF format
- Maximum file size: 25MB
- After first upload, resume is optional (existing resume will be used)

## Security Notes

### Important for Production
If deploying beyond local use:
1. Change `app.secret_key` in `app.py` to a strong random value
2. Move Claude API key to environment variable
3. Use HTTPS for all connections
4. Consider more robust password requirements
5. Add email verification for new accounts
6. Use environment variables for sensitive data

### Current Configuration
- Local deployment only (localhost)
- Passwords are hashed with werkzeug
- SMTP credentials stored encrypted in database
- Session-based authentication with Flask-Login

## File Structure
```
.
├── app.py                      # Main Flask application
├── models.py                   # Database models
├── EmailFinderUsingClaude.py   # Email workflow orchestrator
├── FindEmailWorkFlowV2.py      # Deduplication logic
├── SendEmailWorkFlowV2.py      # Email sending coordinator
├── SimpleEmailer.py            # SMTP email engine
├── HandshakeDMAutomation.py    # Handshake DM automation (NEW!)
├── migrate_handshake.py        # Database migration for Handshake (NEW!)
├── templates/
│   ├── login.html             # Login page
│   ├── register.html          # Registration page
│   ├── dashboard.html         # Main dashboard with tabs
│   └── settings.html          # Settings page
├── users.db                    # SQLite database (created on first run)
├── user_resumes/               # User resume storage (created on first run)
└── workflow_company_log.json   # Email tracking log
```

## Support
For issues or questions, refer to the CLAUDE.md file in this directory for detailed technical documentation.
