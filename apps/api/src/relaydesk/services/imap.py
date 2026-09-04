"""The only module in Relaydesk that speaks IMAP.

Fetch and persist, nothing else. Parsing happens in a separate task so that
a message we cannot parse fails alone rather than wedging the poll and
stalling every other workspace's mail behind it — and so the bytes survive
for replay once the parser is fixed.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import aioimaplib
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.models.poll_state import PollState
from relaydesk.models.raw_message import RawMessage

FETCH_LIMIT = 200


@dataclass(frozen=True)
class Fetched:
    uid: int
    raw: bytes


class MailboxReader(Protocol):
    async def uidvalidity(self) -> int: ...
    async def fetch_since(self, last_uid: int) -> list[Fetched]: ...


async def _state(session: AsyncSession, mailbox: str) -> PollState:
    state = await session.scalar(
        sa.select(PollState).where(PollState.mailbox == mailbox)
    )
    if state is None:
        state = PollState(mailbox=mailbox, uidvalidity=0, last_uid=0)
        session.add(state)
        await session.flush()
    return state


async def store_new(
    session: AsyncSession, mailbox: str, reader: MailboxReader
) -> list[uuid.UUID]:
    state = await _state(session, mailbox)
    validity = await reader.uidvalidity()

    if validity != state.uidvalidity:
        # Every stored UID is meaningless now. Re-syncing is safe: the unique
        # constraint below makes re-fetched messages no-ops.
        state.uidvalidity = validity
        state.last_uid = 0
        await session.flush()

    created: list[uuid.UUID] = []
    for fetched in (await reader.fetch_since(state.last_uid))[:FETCH_LIMIT]:
        row = RawMessage(
            mailbox=mailbox,
            uidvalidity=validity,
            uid=fetched.uid,
            raw=fetched.raw,
            received_at=datetime.now(UTC),
        )
        session.add(row)
        try:
            await session.flush()
        except IntegrityError:
            # Already stored: another poll, or a redelivered task.
            await session.rollback()
            state = await _state(session, mailbox)
            continue
        created.append(row.id)
        state.last_uid = max(state.last_uid, fetched.uid)

    await session.commit()
    return created


class AioImapReader:
    """The real reader. Opens a connection per poll — support-ticket volume
    does not justify holding one open, and a fresh connection cannot go stale
    between polls."""

    def __init__(self, mailbox: str) -> None:
        self._mailbox = mailbox
        self._client: aioimaplib.IMAP4 | None = None
        self._uidvalidity = 0

    async def __aenter__(self) -> "AioImapReader":
        settings = get_settings()
        factory = aioimaplib.IMAP4_SSL if settings.imap_use_ssl else aioimaplib.IMAP4
        self._client = factory(host=settings.imap_host, port=settings.imap_port)
        await self._client.wait_hello_from_server()
        await self._client.login(settings.imap_username, settings.imap_password)
        response = await self._client.select(self._mailbox)
        for line in response.lines:
            text = line.decode() if isinstance(line, bytes) else str(line)
            if "UIDVALIDITY" in text.upper():
                digits = "".join(
                    c for c in text.split("UIDVALIDITY")[1] if c.isdigit()
                )
                if digits:
                    self._uidvalidity = int(digits)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None:
            try:
                await self._client.logout()
            except Exception:
                pass

    async def uidvalidity(self) -> int:
        return self._uidvalidity

    async def fetch_since(self, last_uid: int) -> list[Fetched]:
        assert self._client is not None
        search = await self._client.uid_search(f"UID {last_uid + 1}:*")
        uids = [int(u) for u in b" ".join(search.lines[:-1]).split() if u.isdigit()]
        results: list[Fetched] = []
        for uid in sorted(u for u in uids if u > last_uid)[:FETCH_LIMIT]:
            fetched = await self._client.uid("fetch", str(uid), "(RFC822)")
            # The literal RFC822 body comes back as its own line — a
            # ``bytearray``, not ``bytes`` — sandwiched between the
            # "n FETCH (... {size}" header line and a closing ")". Both of
            # those are short; the body is not, so the longest line is it.
            candidates = [
                bytes(line)
                for line in fetched.lines
                if isinstance(line, bytes | bytearray)
            ]
            body = max(candidates, key=len, default=None)
            if body:
                results.append(Fetched(uid=uid, raw=body))
        return results
