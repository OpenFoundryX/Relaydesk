"""RFC 5322 bytes to a plain dataclass.

Pure by design — no database, no settings, no network. This is where
attacker-controlled input first arrives, and keeping it free of I/O is what
makes it cheap to test against every malformed shape real mail produces.

Nothing in this module raises on bad input. A parser that raises turns one
malformed message into a task that retries forever.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

NO_SUBJECT = "(no subject)"

_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"(?i)<br\s*/?>|</p>|</div>|</tr>")
_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_MESSAGE_ID = re.compile(r"<[^<>@\s]+@[^<>@\s]+>")


@dataclass(frozen=True)
class ParsedAttachment:
    filename: str
    content_type: str
    content: bytes
    inline: bool
    content_id: str | None


@dataclass(frozen=True)
class InboundMessage:
    message_id: str | None
    in_reply_to: str | None
    references: tuple[str, ...]
    from_email: str
    from_name: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    delivered_to: tuple[str, ...]
    subject: str
    text_body: str
    html_body: str | None
    sent_at: datetime
    headers: dict[str, str]
    attachments: tuple[ParsedAttachment, ...]


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _addresses(message: Message, name: str) -> tuple[str, ...]:
    values = message.get_all(name, [])
    return tuple(
        address.lower() for _display, address in getaddresses(values) if address
    )


def _safe_filename(raw: str | None) -> str:
    """The sender chose this. Storage is content-addressed, so this string is
    for display only — but it must not carry a path either way."""
    name = _decode(raw) or "attachment"
    name = name.replace("\\", "/").split("/")[-1]
    name = name.replace("..", "").strip() or "attachment"
    return name[:255]


def html_to_text(html: str) -> str:
    text = _BREAK.sub("\n", html)
    text = _TAG.sub("", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = _WHITESPACE.sub(" ", text)
    return _BLANK_LINES.sub("\n\n", text).strip()


def _part_text(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        return ""
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _walk(message: Message) -> tuple[str, str | None, list[ParsedAttachment]]:
    text: str | None = None
    html: str | None = None
    attachments: list[ParsedAttachment] = []

    for part in message.walk():
        try:
            if part.get_content_maintype() == "multipart":
                continue

            disposition = (part.get_content_disposition() or "").lower()
            content_type = part.get_content_type()
            is_attachment = (
                disposition == "attachment" or part.get_filename() is not None
            )

            if is_attachment:
                payload = part.get_payload(decode=True) or b""
                content_id = part.get("Content-ID")
                attachments.append(
                    ParsedAttachment(
                        filename=_safe_filename(part.get_filename()),
                        content_type=content_type,
                        content=payload,
                        inline=disposition == "inline",
                        content_id=(str(content_id) if content_id else None),
                    )
                )
                continue

            if content_type == "text/plain" and text is None:
                text = _part_text(part)
            elif content_type == "text/html" and html is None:
                html = _part_text(part)
        except Exception:
            # A single malformed part (an attacker-controlled MIME tree can
            # have one) must not cost the rest of the message its body.
            continue

    if text is None and html is not None:
        # Real mail is often HTML-only. The console renders the text body, so
        # deriving one here is what keeps such a ticket readable at all.
        text = html_to_text(html)

    return text or "", html, attachments


def _message_ids(raw: str) -> tuple[str, ...]:
    return tuple(_MESSAGE_ID.findall(raw or ""))


def _safe_headers(message: Message) -> dict[str, str]:
    try:
        return {k.lower(): str(v) for k, v in message.items()}
    except Exception:
        return {}


def _guarded(build: Callable[[], Any], default: Any) -> Any:
    """Run one field extraction in isolation. One failing header (a
    malformed address list, a garbled Message-ID) must not cost the others
    — each caller gets its own try/except via this."""
    try:
        return build()
    except Exception:
        return default


def _header_fields(message: Message) -> dict[str, Any]:
    """Every InboundMessage field derivable from headers alone, each
    independently guarded.

    Shared by the normal path and the headers-only last resort below,
    because ``delivered_to`` and ``message_id`` are exactly what Task 11
    routes and threads on — a degraded message is only a usable ticket if
    these still come through.
    """

    def _from() -> tuple[str, str]:
        from_pairs = getaddresses(message.get_all("From", []))
        return from_pairs[0] if from_pairs else ("", "")

    from_name, from_email = _guarded(_from, ("", ""))

    return {
        "message_id": _guarded(
            lambda: (_message_ids(str(message.get("Message-ID", ""))) or (None,))[0],
            None,
        ),
        "in_reply_to": _guarded(
            lambda: (_message_ids(str(message.get("In-Reply-To", ""))) or (None,))[0],
            None,
        ),
        "references": _guarded(
            lambda: _message_ids(str(message.get("References", ""))), ()
        ),
        "from_email": from_email.lower(),
        "from_name": _decode(from_name) or from_email,
        "to": _guarded(lambda: _addresses(message, "To"), ()),
        "cc": _guarded(lambda: _addresses(message, "Cc"), ()),
        "delivered_to": _guarded(
            lambda: (
                _addresses(message, "Delivered-To")
                + _addresses(message, "X-Original-To")
            ),
            (),
        ),
        "subject": _guarded(
            lambda: _decode(message.get("Subject")) or NO_SUBJECT, NO_SUBJECT
        ),
    }


def _minimal_message(message: Message) -> InboundMessage:
    """Last-resort construction, used when something inside ``_assemble``
    blows up in a way the per-part guard in ``_walk`` didn't catch.

    Degrades to headers-only rather than dropping the message: Task 11
    threads on ``message_id`` and routes on ``delivered_to``, so a message
    that keeps its headers is still a usable ticket even with no body.
    """
    return InboundMessage(
        **_header_fields(message),
        text_body="",
        html_body=None,
        sent_at=datetime.now(UTC),
        headers=_safe_headers(message),
        attachments=(),
    )


def _assemble(message: Message) -> InboundMessage:
    text, html, attachments = _walk(message)

    try:
        sent_at = parsedate_to_datetime(message.get("Date", ""))
    except Exception:
        sent_at = None
    if sent_at is None:
        sent_at = datetime.now(UTC)
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=UTC)

    return InboundMessage(
        **_header_fields(message),
        text_body=text,
        html_body=html,
        sent_at=sent_at,
        headers=_safe_headers(message),
        attachments=tuple(attachments),
    )


def parse(raw: bytes) -> InboundMessage:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception:
        message = EmailMessage()

    try:
        return _assemble(message)
    except Exception:
        # A genuine last resort: _walk already isolates a single bad part,
        # so reaching here means something outside that guard broke. Degrade
        # to headers-only rather than propagating and losing the message.
        return _minimal_message(message)
