# Public Ticket Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the portal's ticket form real — an anonymous visitor submits a ticket and it lands in the workspace inbox indistinguishable from an emailed one.

**Architecture:** A public `POST /api/public/{slug}/tickets` composes services that already exist (`contacts.upsert`, `conversations.create_conversation`, `conversations.append_message`, `attachments.store`) rather than duplicating them, so a portal ticket and an email ticket produce the same rows. The genuinely new pieces are a Postgres-backed IP rate limiter and the trusted-proxy logic that makes the client IP knowable at all.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, Postgres 16, Next.js 16 App Router, React 19.

**Spec:** `docs/superpowers/specs/2026-09-06-public-ticket-submission-design.md`

## Global Constraints

- **Tenancy:** every domain table carries `workspace_id`; every query reading or writing a domain row carries a `workspace_id` predicate. A cross-workspace id returns **404, never 403**.
- **The workspace comes from the resolved slug in the URL path**, never from a header, a form field, or a query parameter.
- **No email verification** (spec D1). A submission creates the ticket immediately.
- **IP rate limiting is the primary abuse control**, not a secondary one, because D1 leaves the email address unattested and therefore trivially varied.
- **A rejected submission must not disclose which control rejected it.**
- **Enums:** `enum.StrEnum` with `sa.Enum(..., native_enum=False, length=16, create_constraint=True)`.
- **Migrations** continue from `0011`, starting at `0012`.
- **Schemas live in `relaydesk/schemas/`**, never inline in routers. All inherit `CamelModel` (`schemas/base.py`).
- **Errors:** services raise `relaydesk.errors.*`; routers never build error envelopes by hand.
- **Sessions:** `expire_on_commit=False` globally; relationships `lazy="selectin"`.
- **The image/attachment allowlist excludes `image/svg+xml`.**
- **Lint:** `ruff check .` clean, line length 88, rules `E,F,I,UP,B`. `pnpm lint` 0 problems, `pnpm build` clean.
- **Never call `asyncio.run()`, `asyncio.set_event_loop()`, or `loop.run_until_complete()` in a test.** The repo runs `asyncio_mode = "auto"` with a session-scoped fixture loop.
- **Test factories:** `make_workspace(session, slug="chronon") -> Workspace`; `make_member(session, workspace, email=..., role=...) -> **User**` (returns a User, NOT a membership); `sign_in(client, session, user_email) -> dict` returning ready-made headers.
- pydantic's `EmailStr` rejects `.test` addresses as a reserved TLD here; tests use `.dev`.
- **Default test command:** `pytest -m "not integration"` from `apps/api`. Baseline at plan start: **420 passing**.

## Existing interfaces this plan composes

Verified against the codebase at plan time — use these exactly, do not reimplement:

```python
# relaydesk.services.contacts
async def upsert(session, workspace_id: uuid.UUID, email: str, name: str) -> Contact

# relaydesk.services.conversations
async def allocate_number(session, workspace_id: uuid.UUID) -> int
async def create_conversation(
    session, workspace_id: uuid.UUID, contact: Contact, subject: str,
    channel: Channel, sent_at: datetime,
) -> Conversation
async def append_message(
    session, conversation: Conversation, *, role: MessageRole,
    direction: MessageDirection, author_name: str, body: str, sent_at: datetime,
    to_address: str = "", body_html: str | None = None,
    external_id: str | None = None, in_reply_to: str | None = None,
    channel_account_id: uuid.UUID | None = None,
    raw_message_id: uuid.UUID | None = None,
    delivery_state: DeliveryState = DeliveryState.none,
) -> Message
# append_message already denormalises conversation.preview and last_message_at.

# relaydesk.services.attachments
async def store(session, message: Message, parsed: Sequence[ParsedAttachment]) -> list[Attachment]
INLINE_SAFE_TYPES: frozenset[str]   # png, jpeg, gif, webp -- no svg

# relaydesk.email_parse.normalize
@dataclass(frozen=True)
class ParsedAttachment:
    filename: str
    content_type: str
    content: bytes
    inline: bool
    content_id: str | None

# relaydesk.api.public
async def resolve_workspace(session: DbSession, slug: str) -> Workspace
    # Reserved labels and unknown slugs both raise NotFound. Reuse it.

# relaydesk.services.ingest
CONTACT_HOURLY_CAP = 20
async def _over_cap(session, workspace_id: uuid.UUID, email: str) -> bool
```

**`Channel.portal` already exists** in `models/conversation.py` alongside `email`, `discord`, `api`. Spec decision D2 (mark portal-origin submissions) therefore costs **zero new columns** — set `channel=Channel.portal`. Do not add a column.

**`MessageRole.customer`** and **`MessageDirection.inbound`** are the values an inbound ticket uses.

---

### Task 1: Client IP resolution behind a proxy

The rate limiter is worthless if it cannot tell callers apart. The form posts from a browser to a Next server action, which calls the API — so the API's peer address is the Next server for every portal submission. Resolving the real client IP is therefore a prerequisite, not a detail, and it is its own task because getting it wrong makes the limit either useless (one shared bucket) or bypassable (trusting a forged header).

**Files:**
- Create: `apps/api/src/relaydesk/services/client_ip.py`
- Modify: `apps/api/src/relaydesk/config.py`
- Modify: `.env.example`
- Test: `apps/api/tests/test_client_ip.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `client_ip.resolve(request: Request) -> str`
  - `Settings.trusted_proxy_ips: str` (default `""`, comma-separated)

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_client_ip.py`:

```python
from unittest.mock import Mock

from relaydesk.services import client_ip


def _request(peer: str, forwarded: str | None = None) -> Mock:
    request = Mock()
    request.client = Mock(host=peer)
    request.headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return request


def test_the_peer_address_is_used_when_no_proxy_is_trusted(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    assert client_ip.resolve(_request("203.0.113.9")) == "203.0.113.9"


def test_a_forwarded_header_from_an_untrusted_peer_is_ignored(monkeypatch) -> None:
    """The whole point. A caller reaching the API directly must not be able
    to choose its own rate-limit bucket by sending a header."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("203.0.113.9", forwarded="198.51.100.1")
    assert client_ip.resolve(request) == "203.0.113.9"


def test_a_forwarded_header_from_a_trusted_peer_is_honoured(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("10.0.0.5", forwarded="198.51.100.1")
    assert client_ip.resolve(request) == "198.51.100.1"


def test_the_left_most_forwarded_address_wins(monkeypatch) -> None:
    """X-Forwarded-For appends, so the client is left-most and every entry
    to its right was added by a hop closer to us."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("10.0.0.5", forwarded="198.51.100.1, 10.0.0.5")
    assert client_ip.resolve(request) == "198.51.100.1"


def test_a_malformed_forwarded_header_falls_back_to_the_peer(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("10.0.0.5", forwarded="not-an-address")
    assert client_ip.resolve(request) == "10.0.0.5"


def test_a_missing_peer_yields_a_stable_placeholder(monkeypatch) -> None:
    """Starlette leaves request.client None for some transports. The limiter
    still needs a key, and every such caller sharing one bucket is the safe
    direction."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    request = Mock()
    request.client = None
    request.headers = {}
    assert client_ip.resolve(request) == "unknown"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `docker exec relaydesk-api-1 pytest tests/test_client_ip.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.services.client_ip'`.

- [ ] **Step 3: Add the setting**

In `apps/api/src/relaydesk/config.py`, beside `attachment_dir`:

```python
    # Comma-separated peer addresses whose X-Forwarded-For we believe. Empty
    # means believe nobody, which is correct for a directly-exposed API: a
    # forged header must never let a caller pick its own rate-limit bucket.
    trusted_proxy_ips: str = ""
```

Add to `.env.example`:

```
TRUSTED_PROXY_IPS=
```

- [ ] **Step 4: Write the module**

Create `apps/api/src/relaydesk/services/client_ip.py`:

```python
import ipaddress

from fastapi import Request

from relaydesk.config import get_settings

UNKNOWN = "unknown"


def _trusted() -> frozenset[str]:
    raw = get_settings().trusted_proxy_ips
    return frozenset(entry.strip() for entry in raw.split(",") if entry.strip())


def _valid(address: str) -> str | None:
    try:
        return str(ipaddress.ip_address(address))
    except ValueError:
        return None


def resolve(request: Request) -> str:
    """The caller's address, as far as it can be trusted.

    ``X-Forwarded-For`` is honoured only when the immediate peer is a proxy
    we configured. Anyone can send the header; only a hop we put there can
    make us believe it.
    """
    peer = request.client.host if request.client else None
    if peer is None:
        return UNKNOWN
    if peer not in _trusted():
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return _valid(first) or peer
```

- [ ] **Step 5: Run the tests and the linter**

Run: `docker exec relaydesk-api-1 pytest tests/test_client_ip.py -q && docker exec relaydesk-api-1 ruff check .`
Expected: 6 passed, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/relaydesk/services/client_ip.py apps/api/src/relaydesk/config.py apps/api/tests/test_client_ip.py .env.example
git commit -m "feat(api): resolve the client IP behind a trusted proxy"
```

---

### Task 2: The rate limiter

Postgres-backed rather than in-process, because the API runs multiple workers and an in-process counter would give each worker its own allowance — multiplying the real limit by the worker count. There is no Redis in this deployment; Postgres is already here and the write volume on an anti-abuse counter is trivial.

**Files:**
- Create: `apps/api/src/relaydesk/models/rate_limit.py`
- Create: `apps/api/src/relaydesk/services/ratelimit.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Create: `apps/api/migrations/versions/0012_rate_limits.py`
- Modify: `apps/api/src/relaydesk/config.py`, `.env.example`
- Test: `apps/api/tests/test_ratelimit.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ratelimit.check(session, bucket: str, key: str, *, limit: int, window: timedelta) -> bool` — `True` when the caller is **within** the limit, and records the hit. `False` when over.
  - `Settings.ticket_ip_hourly_cap: int` (default `5`)

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_ratelimit.py`:

```python
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.services import ratelimit

WINDOW = timedelta(hours=1)


async def test_calls_under_the_limit_are_allowed(db_session: AsyncSession) -> None:
    for _ in range(3):
        assert await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
        )


async def test_the_call_over_the_limit_is_refused(db_session: AsyncSession) -> None:
    for _ in range(3):
        await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
        )
    assert not await ratelimit.check(
        db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
    )


async def test_two_callers_have_separate_allowances(db_session: AsyncSession) -> None:
    for _ in range(3):
        await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
        )
    assert await ratelimit.check(
        db_session, "tickets", "198.51.100.1", limit=3, window=WINDOW
    )


async def test_two_buckets_have_separate_allowances(db_session: AsyncSession) -> None:
    for _ in range(3):
        await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
        )
    assert await ratelimit.check(
        db_session, "other", "203.0.113.9", limit=3, window=WINDOW
    )


async def test_hits_outside_the_window_do_not_count(db_session: AsyncSession) -> None:
    """A caller who used the whole allowance yesterday starts today fresh."""
    for _ in range(3):
        await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=timedelta(seconds=0)
        )
    assert await ratelimit.check(
        db_session, "tickets", "203.0.113.9", limit=3, window=timedelta(seconds=0)
    )
```

- [ ] **Step 2: Run it and watch it fail**

Run: `docker exec relaydesk-api-1 pytest tests/test_ratelimit.py -q`
Expected: FAIL — no module `relaydesk.services.ratelimit`.

- [ ] **Step 3: The model**

Create `apps/api/src/relaydesk/models/rate_limit.py`:

```python
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, UUIDMixin


class RateLimitHit(UUIDMixin, Base):
    """One recorded call against a rate-limited endpoint.

    Deliberately not workspace-scoped: the caller is anonymous and the whole
    point is to bound them before any workspace is trusted. Rows are counted
    inside a window and swept by age, never read individually.
    """

    __tablename__ = "rate_limit_hits"
    __table_args__ = (
        sa.Index("ix_rate_limit_hits_lookup", "bucket", "key", "created_at"),
    )

    bucket: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    key: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
```

Register it in `apps/api/src/relaydesk/models/__init__.py` alongside the others.

- [ ] **Step 4: The service**

Create `apps/api/src/relaydesk/services/ratelimit.py`:

```python
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.rate_limit import RateLimitHit


async def check(
    session: AsyncSession,
    bucket: str,
    key: str,
    *,
    limit: int,
    window: timedelta,
) -> bool:
    """Record a call and say whether the caller is still within the limit.

    Counted in Postgres rather than in process memory on purpose: the API
    runs several workers, and a per-process counter would hand each of them
    its own allowance, multiplying the real limit by the worker count.
    """
    since = datetime.now(UTC) - window
    used = await session.scalar(
        sa.select(sa.func.count())
        .select_from(RateLimitHit)
        .where(
            RateLimitHit.bucket == bucket,
            RateLimitHit.key == key,
            RateLimitHit.created_at >= since,
        )
    )
    if int(used or 0) >= limit:
        return False

    session.add(RateLimitHit(bucket=bucket, key=key[:64]))
    await session.flush()
    return True
```

- [ ] **Step 5: The setting**

In `config.py`:

```python
    # Portal ticket submissions allowed from one address per hour. Low on
    # purpose: a genuine customer opens one ticket, not five.
    ticket_ip_hourly_cap: int = 5
```

In `.env.example`: `TICKET_IP_HOURLY_CAP=5`

- [ ] **Step 6: The migration**

Create `apps/api/migrations/versions/0012_rate_limits.py`, `down_revision = "0011"`, creating `rate_limit_hits` with the columns and the composite index above. Generate it with `alembic revision --autogenerate -m "rate limits"` inside the container, then **read what it produced** — autogenerate has twice in this codebase emitted something subtly wrong for a hand-written index.

Verify the head moved:

```
docker exec relaydesk-api-1 alembic heads
```

- [ ] **Step 7: Run the tests, the linter, and an empty autogenerate**

```bash
docker exec relaydesk-api-1 pytest tests/test_ratelimit.py -q
docker exec relaydesk-api-1 ruff check .
docker exec relaydesk-api-1 alembic revision --autogenerate -m "should be empty"
```
Expected: 5 passed; ruff clean; the third command produces an **empty** migration, proving the model and the migration agree. Delete that empty file.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/relaydesk/models/rate_limit.py apps/api/src/relaydesk/models/__init__.py apps/api/src/relaydesk/services/ratelimit.py apps/api/src/relaydesk/config.py apps/api/migrations/versions/0012_rate_limits.py apps/api/tests/test_ratelimit.py .env.example
git commit -m "feat(api): add a Postgres-backed rate limiter"
```

---

### Task 3: The ticket service

**Files:**
- Create: `apps/api/src/relaydesk/services/tickets.py`
- Modify: `apps/api/src/relaydesk/config.py`, `.env.example`
- Test: `apps/api/tests/test_tickets.py` (create)

**Interfaces:**
- Consumes: `contacts.upsert`, `conversations.create_conversation`, `conversations.append_message`, `attachments.store`, `ingest._over_cap`, `Channel.portal`, `MessageRole.customer`, `MessageDirection.inbound`, `ParsedAttachment`.
- Produces:
  - `tickets.submit(session, workspace_id, *, email, name, subject, message, attachments: Sequence[ParsedAttachment]) -> Conversation`
  - `Settings.ticket_message_max_chars: int` (default `10000`)
  - `Settings.ticket_attachment_max_count: int` (default `5`)

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_tickets.py`:

```python
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid
from relaydesk.models.conversation import Channel, Conversation
from relaydesk.models.message import Message, MessageDirection, MessageRole
from relaydesk.services import tickets
from tests.factories import make_workspace


def _file(name: str = "shot.png", content_type: str = "image/png") -> ParsedAttachment:
    return ParsedAttachment(
        filename=name,
        content_type=content_type,
        content=b"\x89PNG\r\n\x1a\n" + b"0" * 32,
        inline=False,
        content_id=None,
    )


async def test_a_submission_opens_a_conversation(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    conversation = await tickets.submit(
        db_session,
        workspace.id,
        email="ada@example.dev",
        name="Ada",
        subject="Refund please",
        message="My order never arrived.",
        attachments=[],
    )

    assert conversation.channel is Channel.portal
    assert conversation.subject == "Refund please"
    assert conversation.contact.email == "ada@example.dev"


async def test_the_first_message_is_an_inbound_customer_message(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)

    await tickets.submit(
        db_session,
        workspace.id,
        email="ada@example.dev",
        name="Ada",
        subject="Refund please",
        message="My order never arrived.",
        attachments=[],
    )

    message = await db_session.scalar(sa.select(Message))
    assert message.role is MessageRole.customer
    assert message.direction is MessageDirection.inbound
    assert message.body == "My order never arrived."


async def test_a_missing_subject_falls_back_rather_than_failing(
    db_session: AsyncSession,
) -> None:
    """The form does not require a subject. An inbox row with a blank title
    is worse than one titled from the sender."""
    workspace = await make_workspace(db_session)

    conversation = await tickets.submit(
        db_session,
        workspace.id,
        email="ada@example.dev",
        name="Ada",
        subject="",
        message="My order never arrived.",
        attachments=[],
    )

    assert conversation.subject == "Message from Ada"


async def test_an_empty_message_is_refused(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="   ",
            attachments=[],
        )


async def test_an_oversize_message_is_refused(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="x" * 10_001,
            attachments=[],
        )


async def test_too_many_attachments_are_refused(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="See these.",
            attachments=[_file(f"{index}.png") for index in range(6)],
        )


async def test_a_disallowed_content_type_is_refused(db_session: AsyncSession) -> None:
    """SVG executes script when rendered inline. The allowlist is shared with
    email attachments so there is exactly one list to keep right."""
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="See this.",
            attachments=[_file("x.svg", "image/svg+xml")],
        )


async def test_an_attachment_is_stored(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    conversation = await tickets.submit(
        db_session,
        workspace.id,
        email="ada@example.dev",
        name="Ada",
        subject="Refund please",
        message="See this.",
        attachments=[_file()],
    )

    message = await db_session.scalar(
        sa.select(Message).where(Message.conversation_id == conversation.id)
    )
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "shot.png"


async def test_a_submission_never_threads_into_an_existing_conversation(
    db_session: AsyncSession,
) -> None:
    """Spec D4. Threading an unattested submission into a stranger's thread
    would hand them its contents."""
    workspace = await make_workspace(db_session)
    for _ in range(2):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="Still waiting.",
            attachments=[],
        )

    count = await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
    assert count == 2


async def test_a_sender_over_the_hourly_cap_is_refused(
    db_session: AsyncSession,
) -> None:
    """Reuses the same per-contact cap email ingest enforces."""
    workspace = await make_workspace(db_session)
    for _ in range(20):
        await tickets.submit(
            db_session,
            workspace.id,
            email="flood@example.dev",
            name="Flood",
            subject="Hi",
            message="Hi",
            attachments=[],
        )

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="flood@example.dev",
            name="Flood",
            subject="Hi",
            message="Hi",
            attachments=[],
        )
```

- [ ] **Step 2: Run it and watch it fail**

Run: `docker exec relaydesk-api-1 pytest tests/test_tickets.py -q`
Expected: FAIL — no module `relaydesk.services.tickets`.

- [ ] **Step 3: Add the settings**

```python
    ticket_message_max_chars: int = 10000
    ticket_attachment_max_count: int = 5
```

`.env.example`: `TICKET_MESSAGE_MAX_CHARS=10000` and `TICKET_ATTACHMENT_MAX_COUNT=5`.

- [ ] **Step 4: Write the service**

Create `apps/api/src/relaydesk/services/tickets.py`:

```python
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid
from relaydesk.models.conversation import Channel, Conversation
from relaydesk.models.message import MessageDirection, MessageRole
from relaydesk.services import contacts, conversations, ingest
from relaydesk.services import attachments as attachment_store


async def submit(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    email: str,
    name: str,
    subject: str,
    message: str,
    attachments: Sequence[ParsedAttachment],
) -> Conversation:
    """Turn an anonymous portal submission into an ordinary inbox ticket.

    Composes the same services email ingest uses, so a portal ticket and an
    emailed one are the same rows -- the only difference is the channel,
    which records that the sender's address was never attested (spec D1/D2).
    """
    settings = get_settings()

    body = message.strip()
    if not body:
        raise Invalid("A message is required.")
    if len(body) > settings.ticket_message_max_chars:
        raise Invalid("That message is too long.")
    if len(attachments) > settings.ticket_attachment_max_count:
        raise Invalid("Too many attachments.")
    for item in attachments:
        if item.content_type.lower() not in attachment_store.INLINE_SAFE_TYPES:
            raise Invalid("That file type is not accepted.")

    if await ingest._over_cap(session, workspace_id, email):
        raise Invalid("Too many messages from this address just now.")

    display_name = name.strip() or email
    contact = await contacts.upsert(session, workspace_id, email, display_name)

    now = datetime.now(UTC)
    conversation = await conversations.create_conversation(
        session,
        workspace_id,
        contact,
        subject.strip() or f"Message from {display_name}",
        Channel.portal,
        now,
    )
    appended = await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name=display_name,
        body=body,
        sent_at=now,
    )
    if attachments:
        await attachment_store.store(session, appended, attachments)

    await session.flush()
    return conversation
```

- [ ] **Step 5: Run the tests and the linter**

Run: `docker exec relaydesk-api-1 pytest tests/test_tickets.py -q && docker exec relaydesk-api-1 ruff check .`
Expected: 10 passed, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/relaydesk/services/tickets.py apps/api/src/relaydesk/config.py apps/api/tests/test_tickets.py .env.example
git commit -m "feat(api): turn a portal submission into an inbox ticket"
```

---

### Task 4: The public endpoint

**Files:**
- Modify: `apps/api/src/relaydesk/api/public.py`
- Modify: `apps/api/src/relaydesk/schemas/kb.py` (or create `schemas/tickets.py` if it reads better)
- Test: `apps/api/tests/test_ticket_api.py` (create)

**Interfaces:**
- Consumes: `resolve_workspace`, `tickets.submit`, `ratelimit.check`, `client_ip.resolve`.
- Produces: `POST /api/public/{slug}/tickets`, `TicketSubmittedOut`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_ticket_api.py`:

```python
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.conversation import Conversation
from tests.factories import make_workspace


def _form(**overrides) -> dict:
    form = {
        "email": "ada@example.dev",
        "name": "Ada",
        "subject": "Refund please",
        "message": "My order never arrived.",
        "company": "",
    }
    form.update(overrides)
    return form


async def test_a_submission_creates_a_ticket(db_session: AsyncSession, client) -> None:
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post("/api/public/chronon/tickets", data=_form())

    assert response.status_code == 201
    conversation = await db_session.scalar(sa.select(Conversation))
    assert conversation is not None


async def test_the_response_carries_no_ticket_identifier(
    db_session: AsyncSession, client
) -> None:
    """The submitter gets confirmation, not a handle to probe the inbox with."""
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post("/api/public/chronon/tickets", data=_form())

    body = response.json()
    assert "id" not in body
    assert "number" not in body


async def test_an_unknown_workspace_is_a_404(db_session: AsyncSession, client) -> None:
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post("/api/public/nobody/tickets", data=_form())

    assert response.status_code == 404


async def test_a_reserved_label_is_a_404(db_session: AsyncSession, client) -> None:
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post("/api/public/api/tickets", data=_form())

    assert response.status_code == 404


async def test_a_filled_honeypot_is_accepted_but_creates_nothing(
    db_session: AsyncSession, client
) -> None:
    """A bot must not learn it was caught, so the response is the same 201 a
    real submission gets -- and no ticket exists behind it."""
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post(
        "/api/public/chronon/tickets", data=_form(company="Acme Inc")
    )

    assert response.status_code == 201
    count = await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
    assert count == 0


async def test_the_ip_cap_refuses_the_call_over_the_limit(
    db_session: AsyncSession, client
) -> None:
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    for index in range(5):
        ok = await client.post(
            "/api/public/chronon/tickets",
            data=_form(email=f"ada{index}@example.dev"),
        )
        assert ok.status_code == 201

    refused = await client.post(
        "/api/public/chronon/tickets", data=_form(email="ada5@example.dev")
    )
    assert refused.status_code == 429


async def test_a_refusal_does_not_say_which_control_fired(
    db_session: AsyncSession, client
) -> None:
    """An attacker who learns which limit they hit learns how to tune around
    it."""
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    for index in range(5):
        await client.post(
            "/api/public/chronon/tickets",
            data=_form(email=f"ada{index}@example.dev"),
        )
    refused = await client.post(
        "/api/public/chronon/tickets", data=_form(email="ada5@example.dev")
    )

    body = refused.text.lower()
    for leaked in ("ip", "address", "rate", "honeypot", "cap"):
        assert leaked not in body
```

- [ ] **Step 2: Run it and watch it fail**

Run: `docker exec relaydesk-api-1 pytest tests/test_ticket_api.py -q`
Expected: FAIL with 404 or 405 on every case — the route does not exist.

- [ ] **Step 3: The schema**

In `apps/api/src/relaydesk/schemas/kb.py` (public schemas already live here):

```python
class TicketSubmittedOut(CamelModel):
    """Deliberately says nothing but "received". No id, no number: the
    submitter is anonymous and must not be handed a handle to the inbox."""

    received: bool
```

- [ ] **Step 4: The route**

In `apps/api/src/relaydesk/api/public.py`:

```python
@router.post(
    "/{slug}/tickets", response_model=TicketSubmittedOut, status_code=201
)
async def submit_ticket(
    session: DbSession,
    request: Request,
    slug: str,
    email: Annotated[EmailStr, Form()],
    message: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
    subject: Annotated[str, Form()] = "",
    company: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile], File()] = [],
) -> TicketSubmittedOut:
    workspace = await resolve_workspace(session, slug)

    # The honeypot. `company` is hidden from humans by the form's stylesheet,
    # so anything in it came from something filling fields blindly. Answered
    # with the same 201 a real submission gets: telling a bot it was caught
    # only teaches it which field to leave alone.
    if company.strip():
        return TicketSubmittedOut(received=True)

    within = await ratelimit.check(
        session,
        "tickets",
        client_ip.resolve(request),
        limit=get_settings().ticket_ip_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within:
        raise TooManyRequests("We could not accept that just now.")

    parsed = [
        ParsedAttachment(
            filename=upload.filename or "attachment",
            content_type=upload.content_type or "application/octet-stream",
            content=await upload.read(),
            inline=False,
            content_id=None,
        )
        for upload in files
    ]

    await tickets.submit(
        session,
        workspace.id,
        email=str(email),
        name=name,
        subject=subject,
        message=message,
        attachments=parsed,
    )
    await session.commit()
    return TicketSubmittedOut(received=True)
```

`TooManyRequests` does not exist yet. Add it to `relaydesk/errors.py` beside the others, mapping to **429**, following exactly how `Invalid` and `Conflict` are declared and handled there.

Every message a refusal returns must be the same shape regardless of which control fired — the tests above assert that.

- [ ] **Step 5: Run the tests and the linter**

Run: `docker exec relaydesk-api-1 pytest tests/test_ticket_api.py -q && docker exec relaydesk-api-1 ruff check .`
Expected: 7 passed, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/relaydesk/api/public.py apps/api/src/relaydesk/schemas/kb.py apps/api/src/relaydesk/errors.py apps/api/tests/test_ticket_api.py
git commit -m "feat(api): accept a ticket from the public portal"
```

---

### Task 5: The form, wired

**Files:**
- Modify: `apps/web/components/portal/submit-ticket-form.tsx`
- Create: `apps/web/app/(portal)/submit-ticket/actions.ts`
- Modify: `apps/web/lib/api/public.ts`
- Modify: `README.md`
- Test: `apps/web/components/portal/submit-ticket-form.test.tsx` (create)

**Interfaces:**
- Consumes: `POST /api/public/{slug}/tickets`.
- Produces: no API surface.

- [ ] **Step 1: The server action**

Create `apps/web/app/(portal)/submit-ticket/actions.ts`. It reads the workspace slug from the `x-relaydesk-workspace` header the middleware set — **never from a form field**, or a submitter could file into another tenant's inbox — forwards the multipart body to the API, and forwards the caller's address so the API's rate limiter sees the customer rather than the Next server.

The header the API believes is governed by `TRUSTED_PROXY_IPS` (Task 1). Set it to the Next server's address in `docker-compose.yml` for the API service, and say so in the README.

- [ ] **Step 2: Replace the fake submit**

`submit-ticket-form.tsx:52` currently does `event.preventDefault(); setSubmitted(true);` — a success message for a message that went nowhere. Replace it with a call to the action, and give the form three real states: submitting, submitted, and failed-with-a-reason. A failure must not silently look like a success; that is the bug this whole slice exists to fix.

Add the honeypot: a `company` field, hidden from humans with CSS rather than `type="hidden"` (a hidden input is trivially skipped; a styled-away visible one is not), `autocomplete="off"`, and `tabIndex={-1}` so a keyboard user never lands on it.

- [ ] **Step 3: Write the tests**

Create `apps/web/components/portal/submit-ticket-form.test.tsx` asserting: a successful submit calls the action once with the typed values; a failed submit shows an error and **does not** show the success state; the honeypot field is present, empty by default, and not reachable by tab.

- [ ] **Step 4: Verify against the running stack**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -F 'email=ada@example.dev' -F 'subject=Refund' -F 'message=Where is my order?' \
  http://localhost:8000/api/public/chronon/tickets
```
Expected: `201`, and the ticket visible in the console inbox as a `portal` conversation.

- [ ] **Step 5: Run the web checks**

```bash
docker compose exec web pnpm test && docker compose exec web pnpm lint && docker compose exec web pnpm build
```

- [ ] **Step 6: Update the README**

Document that the portal ticket form is live, and that `TRUSTED_PROXY_IPS` must name the proxy in front of the API or the rate limit degrades to one shared bucket for all portal traffic. That misconfiguration is silent and the README is the only place it will be caught.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/portal/submit-ticket-form.tsx apps/web/app/\(portal\)/submit-ticket/actions.ts apps/web/lib/api/public.ts apps/web/components/portal/submit-ticket-form.test.tsx README.md
git commit -m "feat(web): submit a real ticket from the portal"
```

---

## Notes for the executor

- **The API suite must end at 420 + the new tests, with nothing previously passing now failing.** `ingest._over_cap` is reused by Task 3; if email-ingest tests break, the reuse is wrong, not the tests.
- **`docker exec` on this machine can take many minutes to start** under memory pressure. Run focused test files while iterating and the full suite once at the end.
- **No browser is available** — the Claude browser extension is not connected. Verify by `curl` and say plainly what could not be checked.
