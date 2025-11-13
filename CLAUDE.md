# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flask web application for automated job outreach combining two workflows:
1. **Email Campaigns**: Claude API finds contacts → generates personalized emails → sends via SMTP
2. **Handshake DM Automation**: Selenium automates direct messages to recruiters on Handshake

Key features: User authentication, SQLite persistence, real-time SSE progress updates, contact deduplication.

## Running the Application

```bash
# Install and start
pip install -r requirements.txt
python app.py  # Access at http://localhost:5000

# Test ChromeDriver (for Handshake)
python test_chromedriver.py

# Run database migrations when schema changes
python migrate_db.py
python migrate_handshake.py
```

## Architecture Overview

### Email Campaign Workflow (V2)
Three-stage **in-memory** pipeline (no intermediate files):

1. **Contact Discovery** (`EmailFinderUsingClaude.py`):
   - `askClaudeToFindContacts(location, industry)` → list of `{company_name, contact_name, email_address}`

2. **Deduplication** (`FindEmailWorkFlowV2.py`):
   - `main(contacts, user_emails_sent, user_domains_contacted)` → filtered list
   - Checks both user history (DB) and global `workflow_company_log.json`

3. **Email Generation & Sending**:
   - `createEmailsUsingClaude(contacts, resume_path, custom_message)` → adds `email_body` field (resume as base64)
   - `SendEmailWorkFlowV2.main()` → sends via `SimpleEmailer` with rate limiting

### Handshake DM Workflow
Browser automation with manual login (`HandshakeDMAutomation.py`):

1. Selenium WebDriver opens Chrome (visible, not headless)
2. User logs in manually → clicks "I'm Logged In" UI button
3. Claude API maps user's industry to Handshake taxonomy + geocodes city
4. `sendAllDMs()` iterates employer pages:
   - Checks `handshake_dm_log.json` for duplicates
   - Finds recruiter profiles → generates personalized message (Claude + resume PDF)
   - Automates Message button → enters text → sends
   - Saves company to log after success

### SSE Progress Updates Pattern
Flask routes use `queue.Queue()` for background threads:
```python
progress_queue = queue.Queue()
progress_queues[task_id] = progress_queue
threading.Thread(target=workflow_func, args=(progress_queue,)).start()

# In background thread:
progress_queue.put({"message": "Status", "type": "in-progress", "complete": False})

# SSE endpoint streams to client:
@app.route('/progress/<task_id>')
def progress(task_id):
    return Response(stream_with_context(generate()), mimetype='text/event-stream')
```

**Important**: `current_user` unavailable in threads; capture `user_id` first, then query DB with `app.app_context()`.

### User Model (`models.py`)
Stores per-user state in JSON columns:
- `emails_sent_history`: List of email addresses (for deduplication)
- `contact_history`: List of `{company_name, contact_name, email_address, email_summary, date_sent}`
- `handshake_dm_history`: List of `{company_name, job_title, recruiter_name, message_summary, date_sent}`

Methods: `get_contacted_domains()`, `add_sent_emails()`, `add_contact_history()`, `get_handshake_contacted_companies()`

## Key Implementation Details

### API Configuration
- **Claude API key**: `setup.py` as `API_KEY` (⚠️ DO NOT commit `setup.py` - add to `.gitignore`)
- **SMTP credentials**: Per-user in DB (`User.sender_email`, `User.sender_password`)
- **Current model**: `claude-sonnet-4-20250514` (update in `EmailFinderUsingClaude.py` and `HandshakeDMAutomation.py`)

### Deduplication Strategy
**Email**: Check `User.emails_sent_history` + `User.get_contacted_domains()` + `workflow_company_log.json`
**Handshake**: Check `User.handshake_dm_history` + `handshake_dm_log.json`

Both systems prevent re-contacting same company/domain.

### Claude Prompt Patterns
1. **Contact Discovery**: Returns JSON `[{company_name, contact_name, email_address}]` with `contact_name: null` for generic emails
2. **Email Generation**: Resume PDF as base64 document attachment → JSON with `email_body` field
3. **Handshake Industry**: Maps user input to 100+ Handshake categories (cleantech forced to "Utilities & Renewable Energy")
4. **Handshake Location**: Converts "City, State" to lat/long (requires comma in input)
5. **Handshake DM**: 3-4 sentence limit, resume PDF attachment, handles "Dr. Name\nTitle" format

### SimpleEmailer (`SimpleEmailer.py`)
- Auto-detects SMTP server from email domain (Gmail, Office365, Yahoo, etc.)
- 2-second rate limiting between emails
- Logs to `email_log_YYYYMMDD.log`
- Subject line hardcoded in `SendEmailWorkFlowV2.py:18`

### Handshake Automation Quirks
- Browser visible by default (users see automation)
- Manual login required (no credential storage)
- 30-second wait before closing browser
- Multiple XPath selectors tried in sequence (Handshake DOM changes)
- URL encoding: `[]` → `%5B%5D` for filter URLs
- Requires `Industry Codes Handshake.xlsx` for industry code lookup

## Common Development Tasks

### Add Database Column
1. Update `User` model in `models.py`
2. Create `migrate_xyz.py`:
   ```python
   from app import app, db
   from sqlalchemy import text

   with app.app_context():
       with db.engine.connect() as conn:
           result = conn.execute(text("PRAGMA table_info(user)"))
           if 'new_column' not in [row[1] for row in result]:
               conn.execute(text("ALTER TABLE user ADD COLUMN new_column TEXT DEFAULT ''"))
               conn.commit()
   ```

### Add SSE Progress Callbacks
```python
if progress_callback:
    progress_callback("Status message", "in-progress")  # or "success", "error", "info"
```

### Test Individual Modules
```bash
python EmailFinderUsingClaude.py   # Update credentials in __main__ block
python HandshakeDMAutomation.py
python SimpleEmailer.py
```

## File Structure

**Database**: `instance/users.db` (SQLite)
**Resumes**: `user_resumes/user_{id}_{filename}.pdf`
**Tracking logs**: `workflow_company_log.json`, `handshake_dm_log.json`
**Email logs**: `email_log_YYYYMMDD.log`
**Temp uploads**: `uploads/` (cleaned after processing)

## Known Limitations

- **Security**: API keys in `setup.py`, unencrypted SMTP passwords in DB, placeholder Flask secret key
- **Scalability**: SQLite (single-threaded writes), in-memory SSE queues, no Celery
- **Error Handling**: No retry logic for Claude API/SMTP failures, brittle XPath selectors for Handshake DOM
- **Platform**: Windows paths, Chrome required, Selenium may break on Chrome updates
