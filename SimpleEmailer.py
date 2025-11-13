import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
import os
import mimetypes
from typing import List, Optional
import logging
from datetime import datetime
import time


class Email:
    """Represents a single email to be sent."""

    def __init__(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        attachment_path: Optional[str] = None
    ):
        """
        Create a new email.

        Args:
            recipient_email: Email address to send to
            subject: Email subject line
            body: Email body text
            attachment_path: Optional path to file to attach
        """
        self.recipient_email = recipient_email
        self.subject = subject
        self.body = body
        self.attachment_path = attachment_path


class SimpleEmailer:
    """Simple email sender that works with a list of Email objects."""

    # Common email domain to SMTP server mapping
    SMTP_SERVERS = {
        'gmail.com': ('smtp.gmail.com', 587),
        'googlemail.com': ('smtp.gmail.com', 587),
        'outlook.com': ('smtp.office365.com', 587),
        'hotmail.com': ('smtp.office365.com', 587),
        'live.com': ('smtp.office365.com', 587),
        'office365.com': ('smtp.office365.com', 587),
        'gatech.edu': ('smtp.office365.com', 587),
        'yahoo.com': ('smtp.mail.yahoo.com', 587),
        'yahoo.co.uk': ('smtp.mail.yahoo.com', 587),
        'icloud.com': ('smtp.mail.me.com', 587),
        'me.com': ('smtp.mail.me.com', 587),
        'mac.com': ('smtp.mail.me.com', 587),
        'aol.com': ('smtp.aol.com', 587),
        'zoho.com': ('smtp.zoho.com', 587),
    }

    def __init__(
        self,
        sender_email: str,
        sender_password: str
    ):
        """
        Initialize the email sender. SMTP server is automatically detected from email domain.

        Args:
            sender_email: Your email address
            sender_password: Your email password or app password
        """
        self.sender_email = sender_email
        self.sender_password = sender_password

        # Auto-detect SMTP server from email domain
        self.smtp_server, self.smtp_port = self._detect_smtp_server(sender_email)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'email_log_{datetime.now().strftime("%Y%m%d")}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Using SMTP server: {self.smtp_server}:{self.smtp_port}")

    def _detect_smtp_server(self, email: str) -> tuple:
        """
        Auto-detect SMTP server and port from email domain.

        Args:
            email: Email address to detect SMTP server for

        Returns:
            Tuple of (smtp_server, smtp_port)

        Raises:
            ValueError: If email domain is not supported
        """
        try:
            domain = email.split('@')[1].lower()
        except IndexError:
            raise ValueError(f"Invalid email address format: {email}")

        if domain in self.SMTP_SERVERS:
            return self.SMTP_SERVERS[domain]
        else:
            raise ValueError(
                f"Unsupported email domain: {domain}\n"
                f"Supported domains: {', '.join(sorted(self.SMTP_SERVERS.keys()))}"
            )

    def _add_attachment(self, message: MIMEMultipart, file_path: str) -> bool:
        """
        Add an attachment to the email message.

        Args:
            message: MIMEMultipart message object
            file_path: Path to the file to attach

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.isfile(file_path):
                self.logger.warning(f"Attachment file not found: {file_path}")
                return False

            # Check file size (25MB limit)
            file_size = os.path.getsize(file_path)
            if file_size > 25 * 1024 * 1024:
                self.logger.warning(f"Attachment too large ({file_size} bytes): {file_path}")
                return False

            filename = os.path.basename(file_path)

            # Detect MIME type
            ctype, encoding = mimetypes.guess_type(file_path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'

            maintype, subtype = ctype.split('/', 1)

            with open(file_path, 'rb') as fp:
                if maintype == 'image':
                    attachment = MIMEImage(fp.read(), _subtype=subtype)
                elif maintype == 'application':
                    attachment = MIMEApplication(fp.read(), _subtype=subtype)
                else:
                    attachment = MIMEApplication(fp.read())

            attachment.add_header('Content-Disposition', 'attachment', filename=filename)
            message.attach(attachment)

            self.logger.info(f"Added attachment: {filename} ({file_size} bytes)")
            return True

        except Exception as e:
            self.logger.error(f"Error adding attachment {file_path}: {str(e)}")
            return False

    def send_single_email(self, email: Email) -> bool:
        """
        Send a single email.

        Args:
            email: Email object to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart()
            message['From'] = self.sender_email
            message['To'] = email.recipient_email
            message['Subject'] = email.subject

            # Add body
            message.attach(MIMEText(email.body, 'plain'))

            # Add attachment if provided
            if email.attachment_path:
                self._add_attachment(message, email.attachment_path)

            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, email.recipient_email, message.as_string())

            self.logger.info(f"Email sent successfully to {email.recipient_email}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email to {email.recipient_email}: {str(e)}")
            return False

    def send_bulk_emails(
        self,
        emails: List[Email],
        delay_seconds: int = 1
    ) -> dict:
        """
        Send multiple emails with a delay between each.

        Args:
            emails: List of Email objects to send
            delay_seconds: Delay between emails to avoid rate limiting

        Returns:
            Dictionary with success/failure counts
        """
        success_count = 0
        failure_count = 0

        for i, email in enumerate(emails):
            self.logger.info(f"Sending email {i+1}/{len(emails)} to {email.recipient_email}")

            if self.send_single_email(email):
                success_count += 1
            else:
                failure_count += 1

            # Add delay between emails (except after the last one)
            if delay_seconds > 0 and i < len(emails) - 1:
                time.sleep(delay_seconds)

        results = {
            'success': success_count,
            'failure': failure_count,
            'total': len(emails)
        }

        self.logger.info(f"Bulk email completed: {success_count} sent, {failure_count} failed")
        return results


def main(sender_email, sender_password, emails, delay_seconds=2):
    """
    Example usage of SimpleEmailer.

    Args:
        sender_email: Sender's email address (SMTP server auto-detected from domain)
        sender_password: Sender's email password or app-specific password
        emails: List of Email objects to send
        delay_seconds: Delay between emails to avoid rate limiting (default: 2)

    Returns:
        dict: Email sending results with success/failure counts
    """
    # Create the emailer (SMTP server auto-detected)
    emailer = SimpleEmailer(sender_email, sender_password)

    # Send all emails
    results = emailer.send_bulk_emails(emails, delay_seconds=delay_seconds)
    print(f"\nResults: {results}")
    print(f"Success: {results['success']}/{results['total']}")
    print(f"Failed: {results['failure']}/{results['total']}")

    return results


if __name__ == '__main__':
    # Example usage - replace with actual credentials
    test_emails = [
        Email(
            'recipient@example.com',  # Replace with actual recipient
            'Test Subject',
            'This is a test email body.',
            'Sumedh_Kothari_Resume.pdf'
        )
    ]

    main(
        sender_email='your-email@example.com',  # Replace with actual email
        sender_password='your-password',  # Replace with actual password
        emails=test_emails
    )
