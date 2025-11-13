"""
Email sending workflow without Excel files.
Works directly with Python data structures.
"""

from SimpleEmailer import SimpleEmailer, Email


def prepare_emails(contacts_with_bodies, resume_path):
    """
    Convert contact data with email bodies into Email objects.

    Args:
        contacts_with_bodies: List of dicts with company_name, contact_name,
                             email_address, email_body
        resume_path: Path to resume PDF file to attach

    Returns:
        list: List of Email objects ready to send
    """
    subject = "Georgia Tech Undergraduate Student Interested in Internship Opportunity"

    emails = []
    for contact in contacts_with_bodies:
        email_obj = Email(
            recipient_email=contact.get("email_address", ""),
            subject=subject,
            body=contact.get("email_body", ""),
            attachment_path=resume_path,
        )
        emails.append(email_obj)

    return emails


def main(
    contacts_with_bodies,
    resume_path,
    sender_email,
    sender_password,
    delay_seconds=2
):
    """
    Prepare and send emails.

    Args:
        contacts_with_bodies: List of contact dicts with email_body field
        resume_path: Path to resume file
        sender_email: Sender's email address (SMTP server auto-detected from domain)
        sender_password: Sender's email password or app-specific password
        delay_seconds: Delay between emails to avoid rate limiting (default: 2)

    Returns:
        dict: Email sending results with success/failure counts
    """
    # Convert to Email objects
    emails = prepare_emails(contacts_with_bodies, resume_path)

    # Create emailer and send (SMTP server auto-detected)
    emailer = SimpleEmailer(sender_email, sender_password)

    results = emailer.send_bulk_emails(emails, delay_seconds=delay_seconds)

    print(f"\nResults: {results}")
    print(f"Success: {results['success']}/{results['total']}")
    print(f"Failed: {results['failure']}/{results['total']}")

    return results


if __name__ == "__main__":
    import os

    # Load credentials from environment variables
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")

    if not sender_email or not sender_password:
        raise ValueError(
            "SMTP_EMAIL and SMTP_PASSWORD environment variables must be set."
        )

    # Test with sample data
    sample_contacts = [
        {
            "company_name": "Test Company",
            "contact_name": "John Doe",
            "email_address": "test@example.com",
            "email_body": "Hi, this is a test email body.",
        }
    ]

    main(
        sample_contacts,
        "Sumedh_Kothari_Resume.pdf",
        sender_email=sender_email,
        sender_password=sender_password
    )
