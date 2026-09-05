import logging
from datetime import UTC, datetime
from types import SimpleNamespace

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


async def test_a_conflict_does_not_discard_an_earlier_row_in_the_same_batch(
    db_session: AsyncSession,
) -> None:
    """A per-row savepoint scopes the rollback to the one conflicting row.

    Without it, `session.rollback()` on an IntegrityError unwinds the whole
    transaction, wiping out an earlier row in the same batch that had
    already flushed cleanly — yet its id was already captured into
    `created`, so the caller would go on to `.delay()` an ingest task for a
    row that was never actually committed. `FakeReader` cannot exercise this
    on its own (it self-filters by `last_uid`, so it never re-offers a UID
    already recorded through `store_new`); a row is inserted directly here
    to force a genuine unique-constraint conflict.
    """
    existing = RawMessage(
        mailbox="INBOX",
        uidvalidity=1,
        uid=2,
        raw=_mail("already here"),
        received_at=datetime.now(UTC),
    )
    db_session.add(existing)
    await db_session.commit()

    reader = FakeReader(1, {1: _mail("new"), 2: _mail("duplicate")})
    created = await imap.store_new(db_session, "INBOX", reader)

    rows = {
        row.uid: row.id for row in await db_session.scalars(sa.select(RawMessage))
    }
    assert rows.keys() == {1, 2}
    assert created == [rows[1]]
    for row_id in created:
        assert await db_session.get(RawMessage, row_id) is not None


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


def test_literal_body_uses_the_declared_length_not_line_length() -> None:
    """A message far shorter than its own wrapper line must not be misread
    as the wrapper text itself."""
    lines = [
        b"1 FETCH (FLAGS (\\Seen) UID 1 RFC822 {2}",
        bytearray(b"hi"),
        b")",
        b"FETCH completed.",
    ]

    assert imap._literal_body(lines) == b"hi"


def test_literal_body_returns_none_when_the_literal_is_missing() -> None:
    assert imap._literal_body([b"FETCH completed."]) is None


def test_literal_body_bounds_an_absurd_declared_length() -> None:
    """The declared length feeds straight into int(); an unbounded digit
    run in a malformed or hostile FETCH response must not reach it."""
    lines = [
        f"1 FETCH (FLAGS (\\Seen) UID 1 RFC822 {{{'9' * 5000}}}".encode(),
        bytearray(b"hi"),
        b")",
    ]

    assert imap._literal_body(lines) is None


class _StubImapClient:
    """Just enough of aioimaplib's client for AioImapReader.fetch_since:
    a UID search followed by one FETCH per uid."""

    def __init__(self, uids: list[int], fetch_lines: dict[int, list[object]]) -> None:
        self._uids = uids
        self._fetch_lines = fetch_lines
        self.fetched_uids: list[int] = []

    async def uid_search(self, _query: str) -> SimpleNamespace:
        return SimpleNamespace(
            lines=[
                b" ".join(str(uid).encode() for uid in self._uids),
                b"SEARCH completed.",
            ]
        )

    async def uid(self, _command: str, uid: str, _spec: str) -> SimpleNamespace:
        self.fetched_uids.append(int(uid))
        return SimpleNamespace(lines=self._fetch_lines[int(uid)])


async def test_a_short_literal_is_logged_and_does_not_advance_past_its_uid(
    monkeypatch, caplog
) -> None:
    """_literal_body returns None when a FETCH response's declared literal
    length doesn't match what's actually on the wire. Before this, that UID
    was silently skipped and the poll moved on: store_new's
    `max(state.last_uid, fetched.uid)` would then advance last_uid past the
    dropped UID using a *later* one's success, and the next poll's
    `UID last_uid+1:*` search would never offer it again -- permanent,
    silent loss with nothing logged. This pins that the poll stops at the
    short literal instead (so a later UID cannot advance past it) and that
    the drop is logged with the UID."""
    # See test_outbound.py's identical comment: migrations disable every
    # logger created before they run, including this module's.
    monkeypatch.setattr(imap.logger, "disabled", False)
    reader = imap.AioImapReader.__new__(imap.AioImapReader)
    reader._mailbox = "INBOX"
    reader._client = _StubImapClient(
        uids=[5, 6],
        fetch_lines={
            5: [
                b"1 FETCH (FLAGS (\\Seen) UID 5 RFC822 {10}",
                bytearray(b"hi"),
                b")",
            ],
            6: [
                b"2 FETCH (FLAGS (\\Seen) UID 6 RFC822 {5}",
                bytearray(b"hello"),
                b")",
            ],
        },
    )

    with caplog.at_level(logging.WARNING):
        results = await reader.fetch_since(0)

    assert results == []
    # UID 6 (which would have succeeded) is never even fetched: continuing
    # past the short literal would let its success advance last_uid past 5.
    assert reader._client.fetched_uids == [5]
    assert "5" in caplog.text


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


@pytest.mark.integration
async def test_a_workspace_ingest_address_arrives_via_delivered_to(
    db_session: AsyncSession,
) -> None:
    """Every workspace's ingest address is a distinct local part on
    ``INBOUND_DOMAIN``; a real deployment must catch-all that domain into
    the one mailbox this poller reads (see the email channel design doc).
    Local dev simulates that forwarding by delivering to the polled mailbox
    with a ``Delivered-To`` header naming the real ingest address — the
    shape a forwarder produces, and the shape Task 11's routing reads first.

    The round-trip test above only proves send-to-self works; it says
    nothing about whether a message addressed the way real tickets are
    addressed ever reaches the poller. This does.
    """
    from relaydesk.services import channel_accounts, mailer
    from relaydesk.services.workspaces import create_workspace

    workspace = await create_workspace(
        db_session, name="Acme", slug="acme-ingest-test", monogram="AI"
    )
    await db_session.commit()
    [account] = await channel_accounts.list_for(db_session, workspace.id)
    address = channel_accounts.address_for(account, workspace.slug)

    await mailer.send(
        to=get_settings().imap_username,
        subject="Ticket via forwarding",
        text_body="hello",
        headers={"Delivered-To": address},
    )

    async with imap.AioImapReader("INBOX") as reader:
        created = await imap.store_new(db_session, "INBOX", reader)

    rows = await db_session.scalars(
        sa.select(RawMessage).where(RawMessage.id.in_(created))
    )
    assert any(address.encode() in row.raw for row in rows)
