import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.models.raw_message import RawMessage, RawMessageState
from relaydesk.services import imap


class FakeReader:
    def __init__(self, validity: int, messages: dict[int, bytes]) -> None:
        self.validity = validity
        self.messages = messages
        self.fetch_calls: list[int] = []

    async def uidvalidity(self) -> int:
        return self.validity

    async def fetch_since(self, last_uid: int) -> list[imap.Fetched]:
        self.fetch_calls.append(last_uid)
        return [
            imap.Fetched(uid=uid, raw=raw)
            for uid, raw in sorted(self.messages.items())
            if uid > last_uid
        ]


def _mail(subject: str) -> bytes:
    return (
        f"From: ada@example.com\r\nTo: support@acme.com\r\n"
        f"Subject: {subject}\r\n\r\nbody\r\n"
    ).encode()


async def test_new_messages_are_stored_as_raw_rows(db_session: AsyncSession) -> None:
    reader = FakeReader(1, {1: _mail("one"), 2: _mail("two")})

    created = await imap.store_new(db_session, "INBOX", reader)

    assert len(created) == 2
    rows = list(await db_session.scalars(sa.select(RawMessage)))
    assert {row.uid for row in rows} == {1, 2}
    assert all(row.state is RawMessageState.fetched for row in rows)


async def test_a_second_poll_fetches_only_what_is_new(
    db_session: AsyncSession,
) -> None:
    reader = FakeReader(1, {1: _mail("one")})
    await imap.store_new(db_session, "INBOX", reader)

    reader.messages[2] = _mail("two")
    created = await imap.store_new(db_session, "INBOX", reader)

    assert len(created) == 1
    assert reader.fetch_calls == [0, 1]


async def test_replaying_the_same_uid_creates_nothing(
    db_session: AsyncSession,
) -> None:
    """RabbitMQ is at-least-once and IMAP servers re-serve on reconnect.
    Neither may produce a duplicate ticket."""
    reader = FakeReader(1, {1: _mail("one")})
    await imap.store_new(db_session, "INBOX", reader)

    replay = FakeReader(1, {1: _mail("one")})
    created = await imap.store_new(db_session, "INBOX", replay)

    assert created == []
    count = await db_session.scalar(sa.select(sa.func.count()).select_from(RawMessage))
    assert count == 1


async def test_a_uidvalidity_change_resyncs_from_zero(
    db_session: AsyncSession,
) -> None:
    """IMAP servers may renumber UIDs. Without this the poller keeps asking
    for messages above a UID that no longer exists and silently ingests
    nothing, forever."""
    await imap.store_new(db_session, "INBOX", FakeReader(1, {5: _mail("old")}))

    reader = FakeReader(2, {1: _mail("new")})
    created = await imap.store_new(db_session, "INBOX", reader)

    assert reader.fetch_calls == [0]
    assert len(created) == 1


async def test_poll_state_records_the_high_water_mark(
    db_session: AsyncSession,
) -> None:
    from relaydesk.models.poll_state import PollState

    await imap.store_new(
        db_session, "INBOX", FakeReader(7, {3: _mail("a"), 9: _mail("b")})
    )

    state = await db_session.scalar(
        sa.select(PollState).where(PollState.mailbox == "INBOX")
    )
    assert state is not None
    assert state.last_uid == 9
    assert state.uidvalidity == 7


@pytest.mark.integration
async def test_a_real_round_trip_through_greenmail(db_session: AsyncSession) -> None:
    """The fake reader proves the bookkeeping; this proves the wire protocol.
    Requires the compose stack, so it is marked and excluded by default."""
    from relaydesk.services import mailer

    await mailer.send(
        to=get_settings().imap_username,
        subject="Round trip",
        text_body="hello",
    )
    async with imap.AioImapReader("INBOX") as reader:
        created = await imap.store_new(db_session, "INBOX", reader)

    assert created
