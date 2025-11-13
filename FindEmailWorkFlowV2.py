"""
Contact deduplication workflow using per-user email history.
"""

import json


def is_email_okay_to_send(email, domains):
    """
    Check if an email is safe to send (not already contacted at this domain).

    Args:
        email: Email address to check
        domains: Set of already-contacted domains

    Returns:
        bool: True if okay to send, False otherwise
    """
    if "@" not in email:
        return False

    domain = email.split("@")[1]
    return domain not in domains


def filter_contacts(contacts, user_emails_sent, user_domains_contacted):
    """
    Filter contacts based on user's email history.

    Args:
        contacts: List of dicts with company_name, contact_name, email_address
        user_emails_sent: Set of emails already sent by this user
        user_domains_contacted: Set of domains already contacted by this user

    Returns:
        list: Filtered list of contacts that are safe to contact
    """
    cleaned_contacts = []

    for contact in contacts:
        email = contact.get("email_address", "")

        if is_email_okay_to_send(email, user_domains_contacted):
            cleaned_contacts.append(contact)

    return cleaned_contacts


def main(contacts, user_emails_sent=None, user_domains_contacted=None):
    """
    Main workflow function - filters contacts based on user's history.

    Args:
        contacts: List of contact dicts from contact finder
        user_emails_sent: Set of emails already sent by this user (optional)
        user_domains_contacted: Set of domains already contacted by this user (optional)

    Returns:
        list: Deduplicated contacts ready for email generation
    """
    if user_emails_sent is None:
        user_emails_sent = set()
    if user_domains_contacted is None:
        user_domains_contacted = set()

    return filter_contacts(contacts, user_emails_sent, user_domains_contacted)


if __name__ == "__main__":
    # Test with sample data
    sample_contacts = [
        {
            "company_name": "Test Company 1",
            "contact_name": "John Doe",
            "email_address": "john@testcompany1.com",
        },
        {
            "company_name": "Test Company 2",
            "contact_name": None,
            "email_address": "info@testcompany2.com",
        },
    ]

    result = main(sample_contacts)
    print(f"Cleaned contacts: {json.dumps(result, indent=2)}")
