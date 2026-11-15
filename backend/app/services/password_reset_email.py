"""SMTP delivery for password recovery links."""
from email.message import EmailMessage
import smtplib
import ssl

from backend.app.config import Settings


def send_password_reset_email(config: Settings, recipient: str, reset_url: str) -> None:
    if not config.smtp_host.strip() or not config.smtp_from_email.strip():
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = "Reset your BHASHALEARN AI password"
    message["From"] = config.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "We received a request to reset your BHASHALEARN AI password. "
        "This link expires in 30 minutes and can be used once:\n\n"
        f"{reset_url}\n\nIf you did not request this, you can ignore this email."
    )
    context = ssl.create_default_context()
    if config.smtp_port == 465:
        connection = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15, context=context)
    else:
        connection = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
    with connection as client:
        if config.smtp_port != 465:
            client.starttls(context=context)
        if config.smtp_username:
            client.login(config.smtp_username, config.smtp_password)
        client.send_message(message)
