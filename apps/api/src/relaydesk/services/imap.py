"""The only module in Relaydesk that speaks IMAP.

Fetch and persist, nothing else. Parsing happens in a separate task so that
a message we cannot parse fails alone rather than wedging the poll and
stalling every other workspace's mail behind it — and so the bytes survive
for replay once the parser is fixed.
"""

import re
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

# A FETCH response header line declares the literal that follows it as
# "... RFC822 {n}" — n is the exact byte length of the octets on the next
# line. Trusting that declared length, rather than guessing which line is
# the body by its length, is what stays correct for a message shorter than
# its own wrapper line.
_FETCH_LITERAL = re.compile(rb"\{(\d+)\}\s*$")


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
        try:
            # A savepoint scopes the rollback to this one row. Without it,
            # `session.rollback()` on a conflict unwinds the *whole*
            # transaction — including any earlier row in this same batch
            # that already flushed cleanly, and the uidvalidity resync
            # above — even though that earlier row's id was already
            # captured into `created`, which would then name a row that
            # was never actually committed.
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            # Already stored: another poll, or a redelivered task.
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
                # Deliberate best-effort cleanup, nothing more: the poll's
                # outcome is already decided by this point, and a failed
                # logout must not mask it or raise in its place.
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
            body = _literal_body(fetched.lines)
            if body is not None:
                results.append(Fetched(uid=uid, raw=body))
        return results


def _literal_body(lines: list[object]) -> bytes | None:
    """Extract the RFC822 octets from a FETCH response.

    The literal comes back as its own line — a ``bytearray``, not
    ``bytes`` — sandwiched between the "n FETCH (... RFC822 {size}" header
    line and a closing ")". The header line declares the literal's exact
    byte length; trusting that declared length (rather than assuming the
    body is simply the longest line) is what stays correct for a message
    shorter than its own wrapper line.
    """
    for index, line in enumerate(lines):
        if not isinstance(line, bytes | bytearray):
            continue
        match = _FETCH_LITERAL.search(bytes(line))
        if match is None:
            continue
        size = int(match.group(1))
        if index + 1 >= len(lines):
            return None
        candidate = bytes(lines[index + 1])
        return candidate[:size] if len(candidate) >= size else None
    return None
