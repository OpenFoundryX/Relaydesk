from email.message import EmailMessage

from relaydesk.email_parse import normalize
from relaydesk.email_parse.classify import Disposition, classify


def _parse(**headers: str) -> normalize.InboundMessage:
    message = EmailMessage()
    message["From"] = headers.pop("From", "ada@example.com")
    message["To"] = headers.pop("To", "support@acme.com")
    message["Subject"] = headers.pop("Subject", "Hello")
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    message.set_content("body")
    return normalize.parse(message.as_bytes())


def test_ordinary_mail_is_normal() -> None:
    assert classify(_parse()) is Disposition.normal


def test_a_delivery_status_report_is_a_bounce() -> None:
    raw = (
        b"From: MAILER-DAEMON@mx.example.com\r\n"
        b"To: acme-a3f9c2@inbound.localhost\r\n"
        b"Subject: Undelivered Mail Returned to Sender\r\n"
        b'Content-Type: multipart/report; report-type=delivery-status; boundary="b"\r\n'
        b"\r\n--b\r\nContent-Type: text/plain\r\n\r\nfailed\r\n"
        b"--b\r\nContent-Type: message/delivery-status\r\n\r\n"
        b"Action: failed\r\nStatus: 5.1.1\r\n\r\n--b--\r\n"
    )
    assert classify(normalize.parse(raw)) is Disposition.bounce


def test_a_mailer_daemon_sender_is_a_bounce() -> None:
    assert classify(_parse(From="MAILER-DAEMON@mx.example.com")) is Disposition.bounce
    assert classify(_parse(From="postmaster@mx.example.com")) is Disposition.bounce


def test_an_out_of_office_is_an_auto_reply() -> None:
    """Answering this automatically is how a support address and a vacation
    responder mail each other until one runs out of quota."""
    assert classify(_parse(Auto_Submitted="auto-replied")) is Disposition.auto_reply


def test_auto_submitted_no_is_still_a_human() -> None:
    """`Auto-Submitted: no` is the value a normal message may legitimately
    carry. Treating any presence of the header as automatic would drop real
    customer mail."""
    assert classify(_parse(Auto_Submitted="no")) is Disposition.normal


def test_newsletters_are_bulk() -> None:
    assert classify(_parse(Precedence="bulk")) is Disposition.bulk
    assert classify(_parse(List_Id="<news.example.com>")) is Disposition.bulk
    assert classify(_parse(List_Unsubscribe="<https://x/u>")) is Disposition.bulk


def test_a_bounce_wins_over_a_bulk_marker() -> None:
    """Bounces frequently carry Precedence headers. Misfiling one as bulk
    loses the delivery failure it was reporting."""
    message = _parse(From="MAILER-DAEMON@mx.example.com", Precedence="bulk")
    assert classify(message) is Disposition.bounce
