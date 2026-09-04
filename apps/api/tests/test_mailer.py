import socket
from email import message_from_bytes
from email.policy import default as default_policy

import pytest
from aiosmtpd.controller import Controller

from relaydesk.config import get_settings
from relaydesk.services import mailer


class _Collector:
    def __init__(self) -> None:
        self.messages: list[bytes] = []

    async def handle_DATA(self, server, session, envelope) -> str:  # noqa: N802
        self.messages.append(envelope.content)
        return "250 OK"


def _free_port() -> int:
    """aiosmtpd's Controller never learns the port the OS picked for it when
    given ``port=0`` (it keeps echoing back the 0 it was passed, so its own
    startup probe fails to connect) — so we find a free one ourselves and
    hand it a concrete port instead."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def smtp_server(monkeypatch):
    collector = _Collector()
    controller = Controller(collector, hostname="127.0.0.1", port=_free_port())
    controller.start()
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(settings, "smtp_port", controller.port)
    monkeypatch.setattr(settings, "smtp_use_tls", False)
    try:
        yield collector
    finally:
        controller.stop()


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
