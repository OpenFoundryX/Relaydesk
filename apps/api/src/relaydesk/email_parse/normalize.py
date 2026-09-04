"""RFC 5322 bytes to a plain dataclass.

Pure by design — no database, no settings, no network. This is where
attacker-controlled input first arrives, and keeping it free of I/O is what
makes it cheap to test against every malformed shape real mail produces.

Nothing in this module raises on bad input. A parser that raises turns one
malformed message into a task that retries forever.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime

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
        if part.get_content_maintype() == "multipart":
            continue

        disposition = (part.get_content_disposition() or "").lower()
        content_type = part.get_content_type()
        is_attachment = disposition == "attachment" or part.get_filename() is not None

        if is_attachment:
            payload = part.get_payload(decode=True) or b""
            attachments.append(
                ParsedAttachment(
                    filename=_safe_filename(part.get_filename()),
                    content_type=content_type,
                    content=payload,
                    inline=disposition == "inline",
                    content_id=(part.get("Content-ID") or None),
                )
            )
            continue

        if content_type == "text/plain" and text is None:
            text = _part_text(part)
        elif content_type == "text/html" and html is None:
            html = _part_text(part)

    if text is None and html is not None:
        # Real mail is often HTML-only. The console renders the text body, so
        # deriving one here is what keeps such a ticket readable at all.
        text = html_to_text(html)

    return text or "", html, attachments


def _message_ids(raw: str) -> tuple[str, ...]:
    return tuple(_MESSAGE_ID.findall(raw or ""))


def parse(raw: bytes) -> InboundMessage:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception:
        message = EmailMessage()

    text, html, attachments = _walk(message)

    from_pairs = getaddresses(message.get_all("From", []))
    from_name, from_email = (from_pairs[0] if from_pairs else ("", ""))

    try:
        sent_at = parsedate_to_datetime(message.get("Date", ""))
    except Exception:
        sent_at = None
    if sent_at is None:
        sent_at = datetime.now(UTC)
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=UTC)

    references = _message_ids(str(message.get("References", "")))
    in_reply_to_ids = _message_ids(str(message.get("In-Reply-To", "")))

    return InboundMessage(
        message_id=(_message_ids(str(message.get("Message-ID", ""))) or (None,))[0],
        in_reply_to=(in_reply_to_ids[0] if in_reply_to_ids else None),
        references=references,
        from_email=from_email.lower(),
        from_name=_decode(from_name) or from_email,
        to=_addresses(message, "To"),
        cc=_addresses(message, "Cc"),
        delivered_to=(
            _addresses(message, "Delivered-To") + _addresses(message, "X-Original-To")
        ),
        subject=_decode(message.get("Subject")) or NO_SUBJECT,
        text_body=text,
        html_body=html,
        sent_at=sent_at,
        headers={k.lower(): str(v) for k, v in message.items()},
        attachments=tuple(attachments),
    )
