# AI Job Application System - Web Interface

A web-based interface for the automated job application system that allows users to upload their resume and specify their job preferences (location and industry) through a browser.

## Features

- **Resume Upload**: Upload your resume in PDF format (up to 25MB)
- **Location Targeting**: Specify your preferred work location (city/region)
- **Industry Selection**: Choose your target industry (Clean Tech, AI/ML, FinTech, Healthcare, SaaS, etc.)
- **Automated Workflow**: Complete end-to-end automation from contact discovery to email sending
- **Personalized Emails**: Claude AI generates company-specific, industry-tailored emails
- **Real-time Feedback**: Flash messages show workflow progress and results

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `anthropic` - Claude API client
- `flask` - Web framework
- `werkzeug` - File upload handling

### 2. Verify Existing Components

Make sure these files exist in your project directory:
- `EmailFinderUsingClaude.py` - Main workflow orchestrator
- `FindEmailWorkFlowV2.py` - Contact deduplication
- `SendEmailWorkFlowV2.py` - Email preparation
- `SimpleEmailer.py` - Email sending engine

## Usage

### Starting the Web Server

Run the Flask application:

```bash
python app.py
```

The server will start on `http://localhost:5000`

### Using the Web Interface

1. **Open your browser** and navigate to `http://localhost:5000`

2. **Fill out the form**:
   - **Preferred Work Location**: Enter a city (e.g., "Atlanta", "San Francisco", "Boston")
   - **Industry Type**: Enter your target industry (e.g., "Clean Tech", "AI/ML", "FinTech", "Healthcare")
   - **Resume**: Upload your resume as a PDF file
   - **Claude API Key**: Enter your Anthropic API key (get it from [console.anthropic.com](https://console.anthropic.com))
   - **Your Email Address**: Enter the email you'll send from
   - **Email Password**: Enter your email password or app-specific password
   - **SMTP Server** (optional): Defaults to `smtp.office365.com`
   - **SMTP Port** (optional): Defaults to `587`

3. **Click "Start Automated Job Search"**

4. **Wait for completion**: The system will:
   - Find 5 companies in your target industry and location
   - Filter out duplicates from previous runs
   - Generate personalized emails using Claude AI
   - Send emails with your resume attached

5. **View results**: Success/failure counts will be displayed after completion

## How It Works

### Workflow Architecture

```
User Input (Web Form)
    ↓
EmailFinderUsingClaude.askClaudeToFindContacts()
    - Uses location and industry parameters
    - Returns 5 verified contacts
    ↓
FindEmailWorkFlowV2.main()
    - Deduplicates contacts
    - Prevents re-contacting companies
    ↓
EmailFinderUsingClaude.createEmailsUsingClaude()
    - Generates industry-specific emails
    - Tailors content to each company
    ↓
SendEmailWorkFlowV2.main()
    - Converts to Email objects
    - Sends via SMTP with resume attached
```

### Claude Prompt Customization

The system dynamically adjusts Claude prompts based on user input:

**Contact Discovery Prompt**:
- Searches for companies in specified `location`
- Filters by `industry` type
- Provides industry-specific examples (e.g., "renewable energy" for Clean Tech)

**Email Generation Prompt**:
- References specific work in the target `industry`
- Extracts applicant info from uploaded resume
- Tailors each email to the company's focus area
- Ensures authentic, human-like language

### Industry Examples Supported

The system provides tailored guidance for:
- **Clean Tech**: renewable energy, carbon capture, sustainable materials
- **AI/ML**: machine learning, NLP, computer vision
- **FinTech**: payments, banking, investment platforms
- **Healthcare**: medical devices, health tech, telemedicine
- **SaaS**: B2B software, enterprise tools, cloud platforms
- **Custom**: Any industry you specify

## Email Configuration

### Gmail Users

1. Enable 2-factor authentication
2. Generate an app-specific password:
   - Go to Google Account → Security → 2-Step Verification → App passwords
   - Generate a password for "Mail"
3. Use these settings:
   - SMTP Server: `smtp.gmail.com`
   - SMTP Port: `587`
   - Email Password: Use the app-specific password

### Office 365 / Outlook Users

- SMTP Server: `smtp.office365.com` (default)
- SMTP Port: `587` (default)
- Email Password: Your regular password or app password

## Data Persistence

### Files Created/Modified

- `uploads/`: Temporary directory for uploaded resumes (auto-deleted after processing)
- `workflow_company_log.json`: Tracks all emails sent to prevent duplicates
- `email_log_YYYYMMDD.log`: Daily log of email sending operations

### Deduplication Logic

The system maintains a persistent log to avoid:
- Sending multiple emails to the same company
- Re-contacting companies from previous runs
- Uses domain-level tracking (everything after `@` in email)

## Security Considerations

### Current Implementation

The current version requires users to enter their API key and email credentials in the web form. This is suitable for:
- Personal use on localhost
- Trusted networks
- Single-user deployments

### Production Recommendations

For production deployment, implement:

1. **Environment Variables**: Store credentials server-side
   ```python
   import os
   api_key = os.getenv('CLAUDE_API_KEY')
   sender_email = os.getenv('SMTP_EMAIL')
   sender_password = os.getenv('SMTP_PASSWORD')
   ```

2. **User Authentication**: Add login system to protect the interface

3. **HTTPS**: Use SSL/TLS encryption for data transmission

4. **Rate Limiting**: Prevent abuse with request throttling

5. **Input Validation**: Sanitize all user inputs

6. **Secret Management**: Use tools like AWS Secrets Manager or HashiCorp Vault

## Troubleshooting

### Common Issues

**"No module named 'anthropic'"**
```bash
pip install anthropic
```

**"No module named 'flask'"**
```bash
pip install flask
```

**"Failed to send emails"**
- Check SMTP credentials
- Verify SMTP server and port
- Check firewall settings
- For Gmail, ensure app-specific password is used

**"Claude API error"**
- Verify API key is correct
- Check API key has sufficient credits
- Ensure API key has access to Claude Sonnet 4.5

**"No contacts found"**
- Try a different location or industry
- Check that location/industry are specific enough
- Verify Claude API is accessible

## File Structure

```
project/
├── app.py                          # Flask web application
├── templates/
│   └── index.html                  # Web form interface
├── uploads/                        # Temporary resume storage
├── EmailFinderUsingClaude.py       # Main workflow (updated with location/industry)
├── FindEmailWorkFlowV2.py          # Contact deduplication
├── SendEmailWorkFlowV2.py          # Email preparation
├── SimpleEmailer.py                # Email sending engine
├── workflow_company_log.json       # Persistent deduplication log
├── requirements.txt                # Python dependencies
└── WEB_INTERFACE_README.md         # This file
```

## Customization

### Changing Number of Contacts

Edit `EmailFinderUsingClaude.py:44`:
```python
f"Find 5 verified {industry} startups..."  # Change 5 to desired number
```

### Adjusting Email Delay

Edit `SendEmailWorkFlowV2.py`:
```python
results = emailer.send_bulk_emails(emails, delay_seconds=2)  # Change delay
```

### Adding New Industry Templates

Edit `EmailFinderUsingClaude.py:20-33` to add industry-specific examples:
```python
elif "your_industry" in industry.lower():
    industry_examples = "(example 1, example 2, example 3)"
```

### Customizing Email Template

Edit `EmailFinderUsingClaude.py:125-133` to change the base email structure.

## API Usage and Costs

Each workflow execution makes 2 Claude API calls:
1. **Contact Discovery**: ~1,000 tokens ($0.01-0.02)
2. **Email Generation**: ~5,000 tokens ($0.05-0.10)

Estimated cost per run: **$0.06-0.12**

For 25 companies (default): **~$0.15-0.30**

## Next Steps

Consider adding:
- User authentication system
- Database for tracking applications
- Email scheduling/drip campaigns
- Analytics dashboard
- Multi-resume support
- Saved preferences
- Batch processing

## Support

For issues or questions:
1. Check the main `CLAUDE.md` for system architecture
2. Review error logs in `email_log_YYYYMMDD.log`
3. Verify all dependencies are installed
4. Check API credentials and quotas
