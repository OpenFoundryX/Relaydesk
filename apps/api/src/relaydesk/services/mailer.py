"""The only module in Relaydesk that speaks SMTP."""

from email.message import EmailMessage

import aiosmtplib

from relaydesk.config import get_settings


def system_headers() -> dict[str, str]:
    """Headers for mail Relaydesk generates itself.

    ``Auto-Submitted: auto-generated`` tells the recipient's mail system not
    to answer this automatically. Sending it is half of the loop prevention
    in this slice; refusing to answer messages that carry it is the other
    half, and lives in the inbound classifier.
    """
    return {"Auto-Submitted": "auto-generated"}


def from_address() -> str:
    settings = get_settings()
    return f"{settings.smtp_from_name} <noreply@{settings.inbound_domain}>"


def build(
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    headers: dict[str, str] | None = None,
    sender: str | None = None,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender or from_address()
    message["To"] = to
    message["Subject"] = subject
    for name, value in (headers or {}).items():
        message[name] = value

    message.set_content(text_body)
    if html_body is not None:
        # Promotes the message to multipart/alternative with the text part
        # first, which is the ordering mail clients expect.
        message.add_alternative(html_body, subtype="html")
    return message


async def send(
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    headers: dict[str, str] | None = None,
    sender: str | None = None,
) -> None:
    settings = get_settings()
    message = build(to, subject, text_body, html_body, headers, sender)
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_use_tls,
    )


async def send_message(message: EmailMessage) -> None:
    """Send an already-built message. Used by the outbound reply path, which
    needs full control of From, Reply-To, and the threading headers."""
    settings = get_settings()
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_use_tls,
    )
