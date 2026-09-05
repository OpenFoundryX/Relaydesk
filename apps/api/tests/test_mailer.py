from email import message_from_bytes
from email.policy import default as default_policy

from relaydesk.services import mailer


async def test_send_delivers_a_multipart_alternative(smtp_server) -> None:
    """HTML-only mail lands in spam folders. Every system email carries a
    text part."""
    await mailer.send(
        to="ada@example.com",
        subject="You have a ticket",
        text_body="Plain words.",
        html_body="<p>Plain words.</p>",
    )

    assert len(smtp_server.messages) == 1
    sent = message_from_bytes(smtp_server.messages[0], policy=default_policy)
    assert sent["To"] == "ada@example.com"
    assert sent["Subject"] == "You have a ticket"
    assert sent.get_content_type() == "multipart/alternative"
    parts = {part.get_content_type() for part in sent.iter_parts()}
    assert parts == {"text/plain", "text/html"}


async def test_system_mail_is_marked_auto_generated(smtp_server) -> None:
    """Without this header, our notification and a customer's vacation
    responder will mail each other until one of them exhausts a quota."""
    await mailer.send(
        to="ada@example.com",
        subject="Hello",
        text_body="Hi",
        headers=mailer.system_headers(),
    )

    sent = message_from_bytes(smtp_server.messages[0], policy=default_policy)
    assert sent["Auto-Submitted"] == "auto-generated"


async def test_a_text_only_message_is_not_multipart(smtp_server) -> None:
    await mailer.send(to="ada@example.com", subject="Hello", text_body="Hi")

    sent = message_from_bytes(smtp_server.messages[0], policy=default_policy)
    assert sent.get_content_type() == "text/plain"


async def test_send_message_delivers_an_already_built_message(smtp_server) -> None:
    """Task 13's outbound reply path builds its own MIME message (threading
    headers, a specific From/Reply-To) and hands it to send_message()
    directly, bypassing build(). It needs to actually reach the wire."""
    message = mailer.build(
        to="ada@example.com",
        subject="Re: Refund",
        text_body="On it.",
        headers={"In-Reply-To": "<abc123@relaydesk>"},
        sender="Support <support@inbound.localhost>",
    )

    await mailer.send_message(message)

    assert len(smtp_server.messages) == 1
    sent = message_from_bytes(smtp_server.messages[0], policy=default_policy)
    assert sent["To"] == "ada@example.com"
    assert sent["From"] == "Support <support@inbound.localhost>"
    assert sent["In-Reply-To"] == "<abc123@relaydesk>"
