import json
import requests
import os
from anthropic import Anthropic
import FindEmailWorkFlowV2
import SendEmailWorkFlowV2
import setup

# Hunter.io API Key - Replace with your actual API key
HUNTER_API_KEY = setup.HUNTER_API_KEY


def load_legacy_excel_emails(excel_path="Workflow Company Log.xlsx"):
    """
    Load email addresses from the legacy Excel file as an initial database.
    This is a READ-ONLY operation - the Excel file is never modified.
    All new emails are stored in the SQLite database only.

    Args:
        excel_path: Path to the Excel file containing previously sent emails
                   (default: "Workflow Company Log.xlsx")

    Returns:
        tuple: (set of email addresses, set of domains)
    """
    emails = set()
    domains = set()

    # Check if file exists
    if not os.path.exists(excel_path):
        print(f"Legacy Excel file not found at '{excel_path}'. Skipping Excel import.")
        return emails, domains

    try:
        import pandas as pd

        # Read Excel file (no headers, just a list of email addresses)
        df = pd.read_excel(excel_path, header=None)

        # Extract email addresses from the first column
        for value in df.iloc[:, 0].dropna():
            email = str(value).strip()

            # Basic validation that it looks like an email
            if '@' in email and '.' in email:
                emails.add(email)

                # Extract domain
                domain = email.split('@')[1]
                domains.add(domain)

        print(f"Loaded {len(emails)} emails from legacy Excel file ({len(domains)} unique domains)")

    except Exception as e:
        print(f"Error reading Excel file '{excel_path}': {str(e)}")
        print("Continuing without legacy Excel data...")

    return emails, domains

def askClaudeToFindCompanies(api_key, location="Atlanta", industry="Clean Tech", num_companies=5):
    """
    Uses Claude API to find startup companies based on location and industry.
    Returns only company names and domains (no emails or contacts).

    Args:
        api_key: Anthropic API key for Claude API access
        location: City or region to search for companies (default: "Atlanta")
        industry: Industry type to target (default: "Clean Tech")
        num_companies: Number of companies to find (default: 5)

    Returns:
        list: List of dicts with keys: company_name, domain
    """
    client = Anthropic(api_key=api_key)

    # Build industry-specific guidance
    industry_examples = ""
    if "clean tech" in industry.lower() or "green" in industry.lower():
        industry_examples = "(renewable energy, carbon capture, waste reduction, sustainable materials, etc.)"
    elif "ai" in industry.lower() or "ml" in industry.lower():
        industry_examples = "(machine learning, artificial intelligence, natural language processing, computer vision, etc.)"
    elif "fintech" in industry.lower():
        industry_examples = "(payments, banking, investment platforms, cryptocurrency, financial software, etc.)"
    elif "healthcare" in industry.lower() or "health" in industry.lower():
        industry_examples = "(medical devices, health tech, biotech, telemedicine, health software, etc.)"
    elif "saas" in industry.lower():
        industry_examples = "(B2B software, enterprise tools, cloud platforms, productivity software, etc.)"
    else:
        industry_examples = f"({industry} related technologies and services)"

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    "Return only a valid JSON array of objects with exactly two fields: "
                    "company_name, domain.\n\n"
                    f"Find {num_companies} real, actively operating {industry} companies based in the {location} area. "
                    "These should be companies you have high confidence actually exist.\n\n"

                    "DOMAIN REQUIREMENTS:\n"
                    "- Provide the company's primary website domain (e.g., 'acmesolar.com', NOT 'www.acmesolar.com' or 'https://acmesolar.com')\n"
                    "- The domain should be the company's actual corporate domain\n"
                    "- Do NOT include protocol (http/https) or subdomains (www)\n"
                    "- ONLY include domains you are highly confident are correct\n"
                    "- If you cannot find the correct domain for a company, SKIP IT entirely\n\n"

                    "COMPANY REQUIREMENTS:\n"
                    f"- Only include companies working in {industry} {industry_examples}\n"
                    f"- Companies must be based in or have significant presence in {location}\n"
                    "- **CRITICAL: ONLY include startups and early-stage companies (NOT established enterprises)**\n"
                    "- Startups typically have more open internship opportunities and are more responsive\n"
                    "- Focus on companies with 10-200 employees (smaller is better)\n"
                    "- Prefer recently founded companies (last 10 years) that are actively growing\n"
                    "- Only include companies you have high confidence are real and currently operating\n\n"

                    "QUALITY OVER QUANTITY:\n"
                    f"- It is better to return fewer than {num_companies} companies with REAL domains\n"
                    f"- than to return {num_companies} companies with guessed or uncertain domains\n"
                    "- Each entry should represent a real company you can verify exists\n\n"

                    "OUTPUT FORMAT:\n"
                    "- Output only valid JSON with no markdown, explanations, or commentary\n"
                    "- Example: [{\"company_name\": \"Acme Solar\", \"domain\": \"acmesolar.com\"}]\n"
                    "- Example: [{\"company_name\": \"Green Energy Solutions\", \"domain\": \"greenenergysolutions.com\"}]"
                ),
            }
        ],
    )

    response_text = message.content[0].text


    # Clean response text - remove markdown code blocks if present
    cleaned_text = response_text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]  # Remove ```json
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:]  # Remove ```
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]  # Remove trailing ```
    cleaned_text = cleaned_text.strip()

    # Parse JSON response
    try:
        companies = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON. Error: {e}")
        print(f"Cleaned text that failed to parse:\n{cleaned_text}")
        raise

    # Validate that the response is a list of dictionaries
    if not isinstance(companies, list):
        raise ValueError(f"Expected list of companies, but got {type(companies).__name__}")

    for i, item in enumerate(companies):
        if not isinstance(item, dict):
            raise ValueError(f"Expected dict at index {i}, but got {type(item).__name__}: {item}")

        # Ensure required fields are present
        if 'company_name' not in item:
            raise ValueError(f"Company at index {i} missing 'company_name' field: {item}")
        if 'domain' not in item:
            raise ValueError(f"Company at index {i} missing 'domain' field: {item}")

    return companies


def enrichCompaniesWithHunter(companies):
    """
    Uses Hunter.io Company Enrichment API to find email addresses and contact names
    for a list of companies. Returns ONLY 1 contact per company.

    Args:
        companies: List of dicts with keys: company_name, domain

    Returns:
        list: List of dicts with keys: company_name, contact_name, email_address
              Only includes companies where valid contacts were found (1 contact per company)
    """
    contacts = []

    for company in companies:
        company_name = company['company_name']
        domain = company['domain']

        print(f"Searching for contacts at {company_name} ({domain})...")

        try:
            # Call Hunter.io Domain Search API
            url = f"https://api.hunter.io/v2/domain-search"
            params = {
                'domain': domain,
                'api_key': HUNTER_API_KEY,
                'limit': 10  # Get up to 10 emails to choose the best one
            }

            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # Check if we got valid data
            if 'data' not in data:
                print(f"  No data returned for {company_name}")
                continue

            emails_data = data['data'].get('emails', [])

            if not emails_data:
                print(f"  No emails found for {company_name}")
                continue

            # Process each email found
            # Prioritize: Resume-specific emails > HR/recruiting roles > generic emails
            resume_specific_addresses = ['resume', 'resumes', 'careers', 'jobs', 'hiring', 'intern', 'internships', 'talent']
            role_priority = ['hr', 'recruiting', 'talent', 'careers', 'people']

            # Sort emails by relevance
            def email_score(email_info):
                position = email_info.get('position', '').lower()
                email = email_info.get('value', '').lower()
                email_local_part = email.split('@')[0] if '@' in email else email

                # Higher score = better match
                score = 0

                # HIGHEST PRIORITY: Resume-specific email addresses (resume@, careers@, jobs@, etc.)
                for resume_keyword in resume_specific_addresses:
                    if email_local_part == resume_keyword or email_local_part.startswith(resume_keyword):
                        score += 20  # Very high priority
                        break  # Only count once

                # MEDIUM PRIORITY: HR/recruiting roles
                for role in role_priority:
                    if role in position or role in email:
                        score += 10

                # BONUS: Prefer emails with a person's name (but lower than resume-specific addresses)
                if email_info.get('first_name') and email_info.get('last_name'):
                    score += 5

                # BONUS: Prefer verified emails
                if email_info.get('verification', {}).get('status') == 'valid':
                    score += 3

                return score

            sorted_emails = sorted(emails_data, key=email_score, reverse=True)

            # Take the best email (or top few if needed)
            for email_info in sorted_emails[:1]:  # Change to [:3] if you want multiple contacts per company
                email_address = email_info.get('value')
                first_name = email_info.get('first_name')
                last_name = email_info.get('last_name')

                # Determine contact_name
                if first_name and last_name:
                    contact_name = f"{first_name} {last_name}"
                elif first_name:
                    contact_name = first_name
                else:
                    contact_name = None

                contact = {
                    'company_name': company_name,
                    'contact_name': contact_name,
                    'email_address': email_address
                }

                contacts.append(contact)
                print(f"  Found: {contact_name or 'Generic email'} - {email_address}")

        except requests.exceptions.RequestException as e:
            print(f"  Error fetching data for {company_name}: {e}")
            continue
        except Exception as e:
            print(f"  Unexpected error for {company_name}: {e}")
            continue

    print(f"\nTotal contacts found: {len(contacts)}")
    return contacts


def createEmailsUsingClaude(contacts, resume_path, api_key, industry="Clean Tech", custom_message=""):
    """
    Uses Claude API to generate personalized emails for each contact.

    Args:
        contacts: List of contact dicts from askClaudeToFindContacts
        resume_path: Path to PDF resume file
        api_key: Anthropic API key for Claude API access
        industry: Industry type to tailor email content (default: "Clean Tech")
        custom_message: Optional custom message to incorporate into emails (default: "")

    Returns:
        list: List of dicts with company_name, contact_name, email_address, email_body
    """
    client = Anthropic(api_key=api_key)

    # Read and encode resume
    with open(resume_path, "rb") as file:
        import base64
        file_data = file.read()
        encoded_file = base64.standard_b64encode(file_data).decode("utf-8")

    # Create contact list text for Claude
    contact_text = json.dumps(contacts, indent=2)

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"You are helping draft personalized internship outreach emails for companies in the {industry} industry. "
                            f"For each company listed below, create a tailored email that:\n\n"
                            f"1. References specific work or projects the company is doing in {industry}\n"
                            f"2. Connects the applicant's background (found in the resume) to the company's mission\n"
                            f"3. Sounds authentic, human, and genuinely interested (NOT AI-generated)\n"
                            f"4. Is professional but warm and conversational\n"
                            f"5. Asks for internship opportunities without being pushy\n\n"
                            f"6. Keeps the email concise (150-200 words)\n\n"
                            f"7. Does not fabricate any information about the company or the applicant\n\n"
                            f"{f'8. Incorporates this specific message/requirement: {custom_message}' if custom_message else ''}\n\n"
                            f"Example email structure (adapt this based on the resume and each company):\n\n"
                            f"Hi [Company Name Team],\n\n"
                            f"I hope you're well. My name is [Name from resume], and I'm a [major/background from resume] student at [university from resume]. "
                            f"I recently came across [Company Name]'s work on [specific project/technology in {industry}] and was fascinated by [specific technical aspect]. "
                            f"I've spent time working on [relevant experience from resume], and I'd love to see how these skills might apply in a real-world, high-impact setting like yours. "
                            f"My interest is to learn from experienced teams and contribute in any way I can, however small. "
                            f"If there is a way for me to get involved with the technical side at [Company Name], I'd be grateful for the chance to discuss.\n\n"
                            f"I've attached my resume for reference. Thank you very much for considering this note, and I appreciate any time or advice you can offer.\n\n"
                            f"Best,\n[Name from resume]\n\n"
                            f"IMPORTANT:\n"
                            f"- Research each company and reference their actual work in {industry}\n"
                            f"- Extract the applicant's name, university, and major from the resume\n"
                            f"- Match skills from the resume to each company's focus area\n"
                            f"- Make each email unique - no copy-paste language between companies\n"
                            f"- Keep emails concise (150-200 words)\n\n"
                            f"Company contacts:\n{contact_text}\n\n"
                            f"Return a JSON array with the same contacts but add an 'email_body' field containing the tailored email body. "
                            f"Do not include subject line or attachment information. Return only valid JSON with no additional text."
                        ),
                    },
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": encoded_file,
                        },
                    },
                ],
            }
        ],
    )

    response_text = message.content[0].text
    

    # Clean response text - remove markdown code blocks if present
    cleaned_text = response_text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]  # Remove ```json
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:]  # Remove ```
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]  # Remove trailing ```
    cleaned_text = cleaned_text.strip()

    # Parse JSON response
    try:
        emails_with_bodies = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON. Error: {e}")
        print(f"Cleaned text that failed to parse:\n{cleaned_text}")
        raise

    # Validate that the response is a list of dictionaries
    if not isinstance(emails_with_bodies, list):
        raise ValueError(f"Expected list of contacts, but got {type(emails_with_bodies).__name__}")

    for i, item in enumerate(emails_with_bodies):
        if not isinstance(item, dict):
            raise ValueError(f"Expected dict at index {i}, but got {type(item).__name__}: {item}")

        # Ensure required fields are present
        if 'email_address' not in item:
            raise ValueError(f"Contact at index {i} missing 'email_address' field: {item}")
        if 'email_body' not in item:
            raise ValueError(f"Contact at index {i} missing 'email_body' field: {item}")

    return emails_with_bodies


def main(
    sender_email,
    sender_password,
    user_id=None,
    user_emails_sent=None,
    user_domains_contacted=None,
    resume_path="Sumedh_Kothari_Resume.pdf",
    location="Atlanta",
    industry="Clean Tech",
    num_emails=5,
    custom_message="",
    progress_callback=None,
    max_attempts=10
):
    """
    Execute the complete workflow from contact discovery to email sending.
    Uses Claude to find companies, then Hunter.io to find contacts.
    Loops until the desired number of unique emails is found or max attempts is reached.

    Args:
        sender_email: User's email address for sending emails (SMTP server auto-detected from domain)
        sender_password: User's email password or app-specific password
        user_id: User ID for tracking sent emails (optional)
        user_emails_sent: Set of emails already sent by this user (optional)
        user_domains_contacted: Set of domains already contacted by this user (optional)
        resume_path: Path to resume PDF file (default: "Sumedh_Kothari_Resume.pdf")
        location: City or region to search for companies (default: "Atlanta")
        industry: Industry type to target (default: "Clean Tech")
        num_emails: Number of unique emails to send (default: 5)
        custom_message: Optional custom message to include in emails (default: "")
        progress_callback: Optional callback function for progress updates (default: None)
                          Signature: callback(message, msg_type='in-progress', count=None)
        max_attempts: Maximum number of search attempts (default: 10)

    Returns:
        dict: Email sending results with success/failure counts and emails_sent list
    """
    # Get API key from environment variable (more secure than hardcoding)
    import os
    api_key = setup.API_KEY

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it with your Claude API key from https://console.anthropic.com/"
        )

    # Initialize user history if not provided
    if user_emails_sent is None:
        user_emails_sent = set()
    if user_domains_contacted is None:
        user_domains_contacted = set()

    # Load legacy Excel emails and merge with user's database
    # This is READ-ONLY - Excel file is never modified
    excel_emails, excel_domains = load_legacy_excel_emails()

    # Merge Excel data with user's database (union of sets)
    user_emails_sent = user_emails_sent | excel_emails
    user_domains_contacted = user_domains_contacted | excel_domains

    if len(excel_emails) > 0:
        print(f"Merged {len(excel_emails)} legacy emails from Excel with {len(user_emails_sent) - len(excel_emails)} database emails")
        print(f"Total emails to avoid: {len(user_emails_sent)}")
        print(f"Total domains to avoid: {len(user_domains_contacted)}")

    # Helper to send progress updates
    def progress(msg, msg_type='in-progress', count=None):
        print(msg)
        if progress_callback:
            progress_callback(msg, msg_type, count)

    # Track unique contacts found in this session
    all_unique_contacts = []
    session_emails = set()
    session_domains = set()
    attempt = 0
    batch_size = max(5, num_emails)  # Start with at least 5 companies per batch

    progress(f"Starting search for {num_emails} unique {industry} contacts in {location}...", 'in-progress')

    # Loop until we have enough unique contacts or reach max attempts
    while len(all_unique_contacts) < num_emails and attempt < max_attempts:
        attempt += 1
        progress(f"Search attempt {attempt}/{max_attempts} (found {len(all_unique_contacts)}/{num_emails} unique contacts so far)...", 'in-progress')

        # Step 1: Find companies using Claude (only company names and domains)
        progress(f"Searching for {batch_size} {industry} companies...", 'in-progress')
        companies = askClaudeToFindCompanies(api_key, location, industry, batch_size)
        progress(f"Found {len(companies)} companies", 'success')

        if len(companies) == 0:
            progress("No companies found in this batch", 'error')
            break

        # Step 2: Enrich companies with contacts using Hunter.io (1 contact per company)
        progress(f"Finding email contacts for {len(companies)} companies...", 'in-progress')
        contacts = enrichCompaniesWithHunter(companies)
        progress(f"Found {len(contacts)} email contacts", 'success')

        if len(contacts) == 0:
            progress("No email contacts found in this batch", 'error')
            continue  # Try another batch

        # Step 3: Clean and deduplicate contacts using user's history AND session history
        progress("Removing duplicates and previously contacted companies...", 'in-progress')

        # Combine user history with session history for deduplication
        combined_emails = user_emails_sent | session_emails
        combined_domains = user_domains_contacted | session_domains

        cleaned_contacts = FindEmailWorkFlowV2.main(contacts, combined_emails, combined_domains)
        progress(f"After deduplication: {len(cleaned_contacts)} new contacts in this batch", 'success')

        if len(cleaned_contacts) == 0:
            progress("No new unique contacts in this batch (all were duplicates)", 'in-progress')
            continue  # Try another batch

        # Add new unique contacts to our collection
        for contact in cleaned_contacts:
            if len(all_unique_contacts) >= num_emails:
                break  # We have enough

            all_unique_contacts.append(contact)
            session_emails.add(contact['email_address'])

            # Extract domain from email
            domain = contact['email_address'].split('@')[1] if '@' in contact['email_address'] else None
            if domain:
                session_domains.add(domain)

        progress(f"Total unique contacts collected: {len(all_unique_contacts)}/{num_emails}", 'in-progress')

        # If we have enough, stop searching
        if len(all_unique_contacts) >= num_emails:
            progress(f"Successfully found {len(all_unique_contacts)} unique contacts!", 'success')
            break

    # Check if we found enough contacts
    if len(all_unique_contacts) == 0:
        progress("Unable to find any new unique contacts. All available contacts have already been contacted or no contacts were found.", 'error')
        return {"successful": 0, "failed": 0, "total": 0, "emails_sent": []}

    if len(all_unique_contacts) < num_emails:
        progress(f"Could only find {len(all_unique_contacts)} unique contacts after {attempt} attempts. All other available contacts in {location} {industry} have already been contacted or could not be found.", 'error')
        # Continue with what we found instead of failing completely

    # Trim to exactly num_emails if we found more
    final_contacts = all_unique_contacts[:num_emails]

    # Step 4: Generate personalized emails
    progress(f"Generating {len(final_contacts)} personalized emails using Claude AI...", 'in-progress')
    emails_with_bodies = createEmailsUsingClaude(final_contacts, resume_path, api_key, industry, custom_message)
    progress(f"Created {len(emails_with_bodies)} personalized emails", 'success')

    # Step 5: Send emails
    progress("Sending emails (this may take a few minutes)...", 'in-progress')
    results = SendEmailWorkFlowV2.main(
        emails_with_bodies,
        resume_path,
        sender_email,
        sender_password
    )

    # Collect emails that were sent successfully
    emails_sent = [contact['email_address'] for contact in final_contacts]

    # Map results to expected format
    final_results = {
        "successful": results.get("success", 0),
        "failed": results.get("failure", 0),
        "total": results.get("total", 0),
        "emails_sent": emails_sent,  # Return list of emails sent for tracking
        "contacts_data": emails_with_bodies  # Return detailed contact info with email bodies
    }

    progress(f"Emails sent successfully: {final_results['successful']}/{final_results['total']}", 'success', final_results['successful'])
    return final_results


if __name__ == "__main__":
    # This script is designed to be called from the Flask web app
    # Credentials are passed from the web form, not hardcoded
    # To test standalone, provide credentials as arguments to main()
    print("This script should be run through the web application.")
    print("To test standalone, call main() with required parameters.")
