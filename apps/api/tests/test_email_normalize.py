from datetime import UTC, datetime
from email.message import EmailMessage, Message

import pytest

from relaydesk.email_parse import normalize


def _build(**headers: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = headers.pop("From", "Ada Lovelace <ada@example.com>")
    message["To"] = headers.pop("To", "support@acme.com")
    message["Subject"] = headers.pop("Subject", "Refund please")
    message["Date"] = headers.pop("Date", "Tue, 2 Sep 2026 10:00:00 +0000")
    message["Message-ID"] = headers.pop("Message-ID", "<a1@example.com>")
    for name, value in headers.items():
        header_name = name.replace("_", "-")
        try:
            message[header_name] = value
        except ValueError:
            # Real folded headers (e.g. a multi-line References) arrive as
            # raw text on the wire; EmailPolicy's __setitem__ rejects an
            # embedded newline outright as an injection guard. Bypass that
            # guard the same way __setitem__ would build the header, so the
            # test can still construct realistic folded-header bytes.
            message._headers.append(
                (header_name, message.policy.header_factory(header_name, value))
            )
    return message


def test_a_plain_text_message() -> None:
    message = _build()
    message.set_content("I would like a refund.")

    parsed = normalize.parse(message.as_bytes())

    assert parsed.from_email == "ada@example.com"
    assert parsed.from_name == "Ada Lovelace"
    assert parsed.subject == "Refund please"
    assert parsed.text_body.strip() == "I would like a refund."
    assert parsed.html_body is None
    assert parsed.message_id == "<a1@example.com>"
    assert parsed.sent_at == datetime(2026, 9, 2, 10, 0, tzinfo=UTC)


def test_multipart_alternative_keeps_both_parts() -> None:
    message = _build()
    message.set_content("Plain words.")
    message.add_alternative("<p>Plain words.</p>", subtype="html")

    parsed = normalize.parse(message.as_bytes())

    assert parsed.text_body.strip() == "Plain words."
    assert parsed.html_body is not None
    assert "<p>" in parsed.html_body


def test_an_html_only_message_still_yields_readable_text() -> None:
    """Plenty of real mail has no text part. The console renders the text
    body, so producing one here is what keeps such a ticket readable."""
    message = _build()
    message.set_content("<p>Hello <b>there</b>.</p><br>Second line.", subtype="html")

    parsed = normalize.parse(message.as_bytes())

    assert "Hello there." in parsed.text_body
    assert "<p>" not in parsed.text_body
    assert parsed.html_body is not None


def test_encoded_headers_are_decoded() -> None:
    message = _build(Subject="=?utf-8?B?w4ZzdGhldGlj?=")
    message.set_content("hi")

    assert normalize.parse(message.as_bytes()).subject == "Æsthetic"


def test_references_are_split_and_ordered() -> None:
    message = _build(References="<one@x> <two@x>\n <three@x>", In_Reply_To="<three@x>")
    message.set_content("hi")

    parsed = normalize.parse(message.as_bytes())

    assert parsed.references == ("<one@x>", "<two@x>", "<three@x>")
    assert parsed.in_reply_to == "<three@x>"


def test_delivered_to_and_recipients_are_collected() -> None:
    message = _build(
        To="support@acme.com",
        Cc="cc@acme.com",
        Delivered_To="acme-a3f9c2@inbound.localhost",
    )
    message.set_content("hi")

    parsed = normalize.parse(message.as_bytes())

    assert parsed.to == ("support@acme.com",)
    assert parsed.cc == ("cc@acme.com",)
    assert parsed.delivered_to == ("acme-a3f9c2@inbound.localhost",)


def test_attachments_are_extracted() -> None:
    message = _build()
    message.set_content("See attached.")
    message.add_attachment(
        b"%PDF-1.4 fake",
        maintype="application",
        subtype="pdf",
        filename="invoice.pdf",
    )

    parsed = normalize.parse(message.as_bytes())

    assert parsed.text_body.strip() == "See attached."
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "invoice.pdf"
    assert parsed.attachments[0].content_type == "application/pdf"
    assert parsed.attachments[0].content == b"%PDF-1.4 fake"


def test_an_attachment_filename_can_never_reach_a_path() -> None:
    """The sender chooses this string. Storage is content-addressed anyway,
    but a traversal sequence must not survive parsing either."""
    message = _build()
    message.set_content("hi")
    message.add_attachment(
        b"x", maintype="text", subtype="plain", filename="../../../etc/passwd"
    )

    filename = normalize.parse(message.as_bytes()).attachments[0].filename

    assert "/" not in filename
    assert ".." not in filename


def test_a_message_with_no_date_falls_back_to_now() -> None:
    message = EmailMessage()
    message["From"] = "ada@example.com"
    message["To"] = "support@acme.com"
    message["Subject"] = "No date"
    message.set_content("hi")

    parsed = normalize.parse(message.as_bytes())

    assert parsed.sent_at.tzinfo is not None


def test_a_message_with_no_subject_gets_a_placeholder() -> None:
    message = EmailMessage()
    message["From"] = "ada@example.com"
    message["To"] = "support@acme.com"
    message.set_content("hi")

    assert normalize.parse(message.as_bytes()).subject == "(no subject)"


def test_undecodable_bytes_do_not_raise() -> None:
    """A parser that raises on bad encoding turns one malformed message into
    a poison pill that retries forever."""
    raw = (
        b"From: ada@example.com\r\n"
        b"To: support@acme.com\r\n"
        b"Subject: Broken\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"caf\xe9 \xff\xfe not utf-8\r\n"
    )

    parsed = normalize.parse(raw)

    assert "not utf-8" in parsed.text_body


def test_garbage_input_yields_an_empty_message_rather_than_an_exception() -> None:
    parsed = normalize.parse(b"\x00\x01\x02 not an email at all")

    assert parsed.from_email == ""
    assert parsed.text_body is not None


@pytest.mark.parametrize(
    ("raw_filename", "expected"),
    [
        ("../../../etc/passwd", "passwd"),
        ("..\\..\\windows\\x", "x"),
        ("..", "attachment"),
        ("/", "attachment"),
        # =?utf-8?B?...?= of "../../etc/passwd"
        ("=?utf-8?B?Li4vLi4vZXRjL3Bhc3N3ZA==?=", "passwd"),
    ],
)
def test_attachment_filenames_never_carry_a_path(
    raw_filename: str, expected: str
) -> None:
    """Pins the traversal cases traced during review: backslash separators,
    a bare '..', a separator-only name, and an RFC 2047-encoded path all
    neutralise to a plain, path-free filename."""
    message = _build()
    message.set_content("hi")
    message.add_attachment(
        b"x", maintype="text", subtype="plain", filename=raw_filename
    )

    filename = normalize.parse(message.as_bytes()).attachments[0].filename

    assert filename == expected


def test_an_encoded_word_filename_cannot_smuggle_a_control_character() -> None:
    """An RFC 2047 encoded-word decodes in memory, so a filename parameter
    that is on-the-wire harmless (no raw header can carry a literal CR/LF)
    can still decode to a string containing one. `policy.default` decodes
    it during parsing (`get_filename()` already returns the raw CR/LF here,
    confirmed against Python's own email package), so `_safe_filename` must
    strip it -- otherwise it survives into a Content-Disposition response
    header. This is why the raw bytes are hand-built rather than produced
    via `EmailMessage.add_attachment`: constructing the message through the
    normal API triggers Python's own header-injection guard at
    serialization time, which is reassuring for outbound mail but means it
    cannot be used to build this *inbound*, already-on-the-wire case."""
    raw = (
        b"From: ada@example.com\r\n"
        b"To: support@acme.com\r\n"
        b"Subject: hi\r\n"
        b'Content-Type: multipart/mixed; boundary="BOUNDARY"\r\n'
        b"\r\n"
        b"--BOUNDARY\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"hi\r\n"
        b"--BOUNDARY\r\n"
        b"Content-Type: text/plain\r\n"
        # =?utf-8?B?...?= of "a\r\nX-Injected: 1"
        b"Content-Disposition: attachment; "
        b'filename="=?utf-8?B?YQ0KWC1JbmplY3RlZDogMQ==?="\r\n'
        b"\r\n"
        b"x\r\n"
        b"--BOUNDARY--\r\n"
    )

    filename = normalize.parse(raw).attachments[0].filename

    assert "\r" not in filename
    assert "\n" not in filename
    assert filename == "aX-Injected: 1"


class _ExplodingPart(EmailMessage):
    """A MIME part that raises the moment it is inspected. Simulates a
    hostile or corrupted part that survives message.walk() but blows up on
    any of the per-part accessor calls."""

    def get_filename(self, failobj: object = None) -> str:
        raise RuntimeError("boom")


def test_a_malformed_part_does_not_take_down_the_rest_of_the_message() -> None:
    """One hostile part must not cost the message its body or its other,
    well-formed attachments. This can only be exercised in-memory: once a
    message round-trips through bytes, BytesParser rebuilds fresh Message
    objects and any subclass behaviour is lost."""
    root = EmailMessage()
    root["From"] = "ada@example.com"
    root["To"] = "support@acme.com"
    root["Subject"] = "Has a bad part"
    root.set_content("Good body.")
    root.add_attachment(
        b"data", maintype="application", subtype="octet-stream", filename="ok.bin"
    )

    bad = _ExplodingPart()
    bad["Content-Type"] = "application/octet-stream"
    root.attach(bad)

    text, _html, attachments = normalize._walk(root)

    assert text.strip() == "Good body."
    assert [a.filename for a in attachments] == ["ok.bin"]


def test_a_wholly_hostile_message_still_yields_a_valid_inbound_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even if something outside _walk's per-part guard blows up, parse()
    must degrade to a headers-only InboundMessage rather than propagate —
    and that degraded message must still carry delivered_to, since that is
    the field Task 11 routes on."""

    def _explode(_message: Message) -> tuple[str, str | None, list]:
        raise RuntimeError("the whole tree is hostile")

    monkeypatch.setattr(normalize, "_walk", _explode)

    message = _build(Delivered_To="acme-a3f9c2@inbound.localhost")
    message.set_content("irrelevant")

    parsed = normalize.parse(message.as_bytes())

    assert parsed.from_email == "ada@example.com"
    assert parsed.subject == "Refund please"
    assert parsed.message_id == "<a1@example.com>"
    assert parsed.delivered_to == ("acme-a3f9c2@inbound.localhost",)
    assert parsed.text_body == ""
    assert parsed.html_body is None
    assert parsed.attachments == ()


def test_minimal_message_preserves_delivered_to_and_message_id() -> None:
    """The routing contract for the headers-only last resort: Task 11
    routes on delivered_to and threads on message_id, so a message that
    falls into _minimal_message must still carry both rather than stranding
    the mail as surely as the original exception would have."""
    message = _build(
        To="support@acme.com",
        Cc="cc@acme.com",
        Delivered_To="acme-a3f9c2@inbound.localhost",
    )
    message.set_content("hi")

    parsed = normalize._minimal_message(message)

    assert parsed.delivered_to == ("acme-a3f9c2@inbound.localhost",)
    assert parsed.message_id == "<a1@example.com>"
    assert parsed.to == ("support@acme.com",)
    assert parsed.cc == ("cc@acme.com",)
    assert parsed.text_body == ""
    assert parsed.attachments == ()
