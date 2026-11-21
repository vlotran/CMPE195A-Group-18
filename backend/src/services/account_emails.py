"""
Account emails: sent after sign-up and after an account is deleted.

Each builder returns (subject, plain text, HTML). The HTML uses inline styles
and a simple layout because mail apps strip <style> blocks and most modern CSS.
Sending is done by email_service.send_email, which does nothing while email is
turned off (no SMTP_USERNAME) and never raises.
"""

import html

APP_NAME = "Smart Hydroponic Garden System"


def _html(heading: str, color: str, name: str, message: str) -> str:
    """Shared layout: colored heading, greeting, one paragraph."""
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;color:#1f2933">'
        f'<h2 style="margin:0 0 16px;color:{color}">{html.escape(heading)}</h2>'
        f'<p style="margin:0 0 12px">Hi {html.escape(name)},</p>'
        f'<p style="margin:0">{html.escape(message)}</p>'
        '</div>'
    )


def build_welcome_email(name: str) -> tuple[str, str, str]:
    """After sign-up."""
    heading = "CONGRATULATIONS!"
    message = f"You have successfully signed up for {APP_NAME}."
    text = f"{heading}\n\nHi {name},\n\n{message}\n"
    return f"Welcome to {APP_NAME}", text, _html(heading, "#2e7d32", name, message)


def build_goodbye_email(name: str) -> tuple[str, str, str]:
    """After the account was deleted."""
    heading = "SORRY TO SEE YOU GO..."
    message = f"Your {APP_NAME} account and email have been successfully deleted."
    text = f"{heading}\n\nHi {name},\n\n{message}\n"
    return f"Your {APP_NAME} account has been deleted", text, _html(heading, "#4b5563", name, message)
