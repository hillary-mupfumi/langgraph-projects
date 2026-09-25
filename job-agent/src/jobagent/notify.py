"""Optional email notification for the daily shortlist. Only sends if SMTP_*
env vars are configured in .env; otherwise the daily run just logs the
shortlist to a file and prints it, which is enough for a single local user
and doesn't force an email setup no one asked for.
"""

import os
import smtplib
from email.message import EmailMessage


def send_shortlist_email(
    body: str, subject: str = "Job Application Agent: today's shortlist"
) -> bool:
    """Returns True if it actually sent, False if SMTP isn't configured (not an error)."""
    host = os.environ.get("SMTP_HOST")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to_addr = os.environ.get("NOTIFY_EMAIL_TO") or user

    if not all([host, port, user, password, to_addr]):
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP(host, int(port)) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    return True
