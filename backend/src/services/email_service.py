"""
Send email through an SMTP account (e.g. a Gmail account with an App Password).
Uses only the Python standard library. Settings come from .env
"""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from backend.src.config.settings import settings
from backend.src.utils.logger import logger


def _send(to: str, subject: str, body: str) -> None:
    """Blocking send: connect, encrypt, log in, deliver to the SMTP server."""
    msg = EmailMessage()
    msg["From"] = f"{settings.app_name} <{settings.smtp_username}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    # timeout: a dead mail server gives up instead of hanging the thread forever
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> bool:
    """
    Send one email without blocking the event loop.
    Returns False instead of raising: a mail problem must never stop the backend.
    """
    if not settings.smtp_username:
        return False  # email is turned off

    try:
        await asyncio.to_thread(_send, to, subject, body)
        logger.info(f"Alert email sent to {to}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False
