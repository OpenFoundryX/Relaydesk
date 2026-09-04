"""What a message *is*, decided before anything is created from it."""

import enum

from relaydesk.email_parse.normalize import InboundMessage

DAEMON_LOCAL_PARTS = frozenset(
    {"mailer-daemon", "postmaster", "no-reply", "noreply"}
)
BULK_PRECEDENCE = frozenset({"bulk", "list", "junk"})
AUTO_PRECEDENCE = frozenset({"auto_reply", "auto-reply"})


class Disposition(enum.StrEnum):
    normal = "normal"
    bounce = "bounce"
    auto_reply = "auto_reply"
    bulk = "bulk"


def _is_bounce(message: InboundMessage) -> bool:
    content_type = message.headers.get("content-type", "").lower()
    if "multipart/report" in content_type and "delivery-status" in content_type:
        return True
    local_part = message.from_email.split("@", 1)[0].lower()
    return local_part in DAEMON_LOCAL_PARTS


def _is_auto_reply(message: InboundMessage) -> bool:
    # `no` is the value ordinary mail may legitimately carry; only anything
    # else means automatic.
    auto_submitted = message.headers.get("auto-submitted", "").strip().lower()
    if auto_submitted and auto_submitted != "no":
        return True
    precedence = message.headers.get("precedence", "").strip().lower()
    if precedence in AUTO_PRECEDENCE:
        return True
    return "x-autoreply" in message.headers or "x-autorespond" in message.headers


def _is_bulk(message: InboundMessage) -> bool:
    if "list-id" in message.headers or "list-unsubscribe" in message.headers:
        return True
    precedence = message.headers.get("precedence", "").strip().lower()
    return precedence in BULK_PRECEDENCE


def classify(message: InboundMessage) -> Disposition:
    # Order matters. Bounces routinely carry bulk and auto-submitted markers,
    # and misfiling one loses the delivery failure it was reporting.
    if _is_bounce(message):
        return Disposition.bounce
    if _is_auto_reply(message):
        return Disposition.auto_reply
    if _is_bulk(message):
        return Disposition.bulk
    return Disposition.normal
