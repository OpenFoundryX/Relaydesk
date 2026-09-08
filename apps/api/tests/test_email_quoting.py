"""Trimming the quoted chain off an inbound reply.

A customer's client appends the message it is answering. Stored whole, every
round trip carries another copy of the thread -- and `conversation.preview`,
which is derived from the body, fills with somebody's own words quoted back
at them.

Nothing is lost by trimming here: `raw_messages.raw` keeps the complete MIME
source and `messages.body_html` keeps the untrimmed HTML.
"""

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.email_parse.quoting import strip_quoted
from relaydesk.models.conversation import Conversation
from relaydesk.models.message import Message
from relaydesk.models.raw_message import RawMessage
from relaydesk.services import channel_accounts, ingest
from tests.factories import make_workspace


def test_a_gmail_reply_keeps_only_what_the_customer_wrote() -> None:
    """The shape Gmail actually sends: the attribution line wraps, because
    the address is long enough to fold."""
    text = (
        "Hey Nilesh,\n"
        "Are there any updates on this\n"
        "\n"
        "Regards\n"
        "Nilesh Pant\n"
        "\n"
        "On Tue, Sep 8, 2026 at 1:19 PM Chronon <\n"
        "chronon-ce0a9ba227d0+c27@inboxoshq.com> wrote:\n"
        "\n"
        "> Hey Priya\n"
        ">\n"
        "> Can you hear me ??\n"
        "> We need to get on a call to test this.\n"
        ">\n"
    )

    assert strip_quoted(text) == (
        "Hey Nilesh,\nAre there any updates on this\n\nRegards\nNilesh Pant"
    )


def test_a_single_line_attribution_is_cut() -> None:
    text = (
        "No thanks.\n"
        "\n"
        "On Mon, 1 Sep 2026 at 10:00, Ada <ada@example.com> wrote:\n"
        "> Are you still interested?\n"
    )

    assert strip_quoted(text) == "No thanks."


def test_a_bare_quote_block_with_no_attribution_is_cut() -> None:
    """Some clients quote without introducing it."""
    text = "Sounds good.\n\n> the original question\n> spanning two lines\n"

    assert strip_quoted(text) == "Sounds good."


def test_outlooks_original_message_separator_is_cut() -> None:
    text = (
        "Approved.\n"
        "\n"
        "-----Original Message-----\n"
        "From: Ada <ada@example.com>\n"
        "Sent: Monday, September 1, 2026 10:00 AM\n"
        "Subject: Approval needed\n"
    )

    assert strip_quoted(text) == "Approved."


def test_an_outlook_header_block_is_cut() -> None:
    """Outlook for Windows quotes with a bare header block and no separator."""
    text = (
        "Looks fine to me.\n"
        "\n"
        "From: Ada <ada@example.com>\n"
        "Sent: Monday, September 1, 2026 10:00 AM\n"
        "To: Support <support@example.com>\n"
        "Subject: Re: Approval needed\n"
        "\n"
        "Please review.\n"
    )

    assert strip_quoted(text) == "Looks fine to me."


def test_outlook_web_rule_line_is_cut() -> None:
    text = "Thanks!\n\n" + "_" * 32 + "\nFrom: Ada\n"

    assert strip_quoted(text) == "Thanks!"


def test_a_message_with_no_quote_is_returned_untouched() -> None:
    """Byte-identical: a trimmer that reformats ordinary mail is worse than
    no trimmer at all."""
    text = "Hi there,\n\nMy order 12345 never arrived.\n\nRegards\nAda\n"

    assert strip_quoted(text) == text


def test_a_reply_that_is_only_a_quote_keeps_its_text() -> None:
    """Trimming to nothing would turn a real message into a blank one. The
    quoted text is all there is, so it is better than an empty ticket."""
    text = "On Mon, 1 Sep 2026 at 10:00, Ada <ada@example.com> wrote:\n> Help!\n"

    assert strip_quoted(text) == text


def test_a_sign_off_is_not_mistaken_for_a_quote() -> None:
    """Signatures are deliberately out of scope -- customers put real content
    after 'Regards', and losing it is worse than keeping a name."""
    text = "Please close this.\n\nRegards\nAda Lovelace\nAcme Ltd\n"

    assert strip_quoted(text) == text


def test_empty_input_survives() -> None:
    assert strip_quoted("") == ""


# --- end to end -------------------------------------------------------------


async def test_an_ingested_reply_stores_only_the_new_text(
    db_session: AsyncSession,
) -> None:
    """The stored body and the inbox preview both come out clean.

    ``conversation.preview`` is derived from the body in ``append_message``,
    so a quoted chain reaching the body reaches the inbox list too.
    """
    workspace = await make_workspace(db_session, slug="quoting")
    account = await channel_accounts.create(db_session, workspace.id, "Support")
    await db_session.flush()

    message = EmailMessage()
    message["From"] = "ada@example.com"
    message["To"] = channel_accounts.address_for(account, "quoting")
    message["Subject"] = "Re: Help with order"
    message["Date"] = format_datetime(datetime.now(UTC) - timedelta(minutes=5))
    message["Message-ID"] = "<reply@example.com>"
    message.set_content(
        "Are there any updates on this\n"
        "\n"
        "On Tue, Sep 8, 2026 at 1:19 PM Chronon <\n"
        "quoting-abc+c1@example.com> wrote:\n"
        "\n"
        "> Can you hear me ??\n"
        ">\n"
    )
    row = RawMessage(
        mailbox="INBOX",
        uidvalidity=1,
        uid=1,
        raw=message.as_bytes(),
        received_at=datetime.now(UTC),
    )
    db_session.add(row)
    await db_session.flush()

    await ingest.ingest_raw(db_session, row.id)

    stored = await db_session.scalar(
        sa.select(Message).where(Message.external_id == "<reply@example.com>")
    )
    assert stored.body == "Are there any updates on this"

    conversation = await db_session.get(Conversation, stored.conversation_id)
    assert "wrote:" not in conversation.preview
    assert ">" not in conversation.preview
