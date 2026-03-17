"""Mailer module: sends digest emails via Gmail SMTP."""
import logging
import smtplib
import os
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

DAILY_EMAIL_LIMIT = 500


def make_subject(d: date | None = None) -> str:
    """Generate subject line with date."""
    d = d or date.today()
    return f"Your Job Digest - {d.isoformat()}"


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send a single email via Gmail SMTP. Returns True on success."""
    try:
        msg = MIMEMultipart()
        msg["From"] = os.getenv("GMAIL_USER", "")
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(os.getenv("GMAIL_USER", ""), os.getenv("GMAIL_APP_PASSWORD", ""))
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def send_digests(digests: list[dict]) -> dict:
    """
    Send all digests. Stops if daily limit (500) is reached.
    Each digest dict has keys: to_email, subject, body.
    Returns {"sent": int, "failed": int, "skipped_rate_limit": int}.
    """
    stats = {"sent": 0, "failed": 0, "skipped_rate_limit": 0}
    for d in digests:
        if stats["sent"] >= DAILY_EMAIL_LIMIT:
            stats["skipped_rate_limit"] += 1
            continue
        success = send_email(d["to_email"], d["subject"], d["body"])
        if success:
            stats["sent"] += 1
        else:
            stats["failed"] += 1

    if stats["skipped_rate_limit"] > 0:
        logger.warning("Rate limit reached. Skipped %d digests.", stats["skipped_rate_limit"])
    return stats
