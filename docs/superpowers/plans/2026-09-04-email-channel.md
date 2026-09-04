# Email Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the inbox real — mail sent to a workspace becomes a ticket, an agent's reply is delivered, and the customer's reply threads back onto the same conversation.

**Architecture:** A Celery/RabbitMQ worker tier runs alongside the existing FastAPI app. Inbound mail arrives at one deployment mailbox by customer-configured forwarding; a Beat-scheduled `imap_poll` persists raw bytes and fans out one `ingest_message` task per message, which routes to a workspace by recipient, classifies, threads, and appends. Outbound replies are written synchronously by the API and delivered by the worker. Celery is synchronous and this codebase is async, so every task is a thin sync wrapper that calls `asyncio.run`-equivalent bridge code and reuses the existing `services/` layer unchanged.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, Postgres 16, Celery 5 + RabbitMQ, aiosmtplib, aioimaplib, GreenMail (dev), Next.js 16 / React 19 (web).

**Spec:** `docs/superpowers/specs/2026-09-04-email-channel-design.md`

## Global Constraints

Copied from the spec. Every task's requirements implicitly include this section.

- **Tenancy:** every domain table carries `workspace_id`; every query that reads or writes a domain row carries a `workspace_id` predicate. An id belonging to another workspace returns **404, never 403**.
- **Enums:** `enum.StrEnum` with `sa.Enum(..., native_enum=False, length=16, create_constraint=True)`, producing `VARCHAR` + a named `CHECK`. Never `native_enum=True`.
- **JSON casing:** response and request bodies are camelCase via the existing `alias_generator=to_camel`. Query parameters are **not** covered by it and need explicit `Query(alias="...")`.
- **Migrations:** continue slice 1's numbering, starting at `0007`.
- **Sessions:** `expire_on_commit=False` is set globally, and relationships are `lazy="selectin"`. After mutating a relationship, `await session.refresh(obj, [...])` before serializing.
- **Errors:** services raise `relaydesk.errors.*` (`NotFound`, `Invalid`, `Conflict`, `Unavailable`); routers never build error envelopes by hand.
- **No mailbox credentials in the database.** The deployment mailbox is configured through the environment only (spec D4).
- **Ingest tokens are random** — `secrets.token_hex(6)` — never derived from the slug or id (spec D5).
- **Tasks must be idempotent.** RabbitMQ is at-least-once; a crashed worker's task will be redelivered after its writes committed.
- **Never render inbound HTML.** Stored `body_html` is never sent to a browser as HTML in this slice.
- **Lint/format:** `ruff check .` clean, line length 88, rules `E,F,I,UP,B`.
- **Web lint:** `pnpm lint` must report 0 problems; unused args are silenced with a leading `_` (configured `argsIgnorePattern`).

---

## File Structure

**New API packages**

| Path | Responsibility |
|---|---|
| `worker/app.py` | Celery app, config, Beat schedule, process-init signal |
| `worker/bridge.py` | One event loop + one engine per worker process; `run()` and `session_scope()` |
| `worker/tasks/mail.py` | `send_email`, `reconcile_outbound` |
| `worker/tasks/inbound.py` | `imap_poll`, `ingest_message` |
| `services/mailer.py` | The only module that speaks SMTP; `send()` plus the three templates |
| `services/imap.py` | The only module that speaks IMAP; fetch + UID/UIDVALIDITY bookkeeping |
| `email_parse/normalize.py` | Bytes → `InboundMessage`. Pure, no I/O, no database |
| `email_parse/classify.py` | `InboundMessage` → `Disposition`. Pure |
| `services/channel_accounts.py` | Ingest address CRUD and lookup by token |
| `services/ingest.py` | Routing, threading, append. The pipeline's database half |
| `services/attachments.py` | Content-addressed storage and scoped reads |
| `api/channels.py`, `api/attachments.py` | Routers |

`email_parse/` is deliberately pure and separate from `services/`: MIME parsing is where hostile input lands, and keeping it free of database access means it can be tested exhaustively against `.eml` fixtures with no fixtures-in-Postgres ceremony.

**Modified**

`config.py`, `models/{message,contact,user}.py`, `models/__init__.py`, `services/{conversations,team,auth}.py`, `api/{team,workspace,router}.py`, `cli.py`, `docker-compose.yml`, `.env.example`, `pyproject.toml`, `README.md`, and the web files in Task 13.

---

### Task 1: Configuration, compose services, and GreenMail

Stands up the infrastructure the rest of the plan assumes. No application behaviour yet — the deliverable is that `docker compose up` starts five services and the API still passes its suite.

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/src/relaydesk/config.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Test: `apps/api/tests/test_config.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `Settings` fields used by every later task — `celery_broker_url: str`, `inbound_domain: str`, `imap_host: str`, `imap_port: int`, `imap_username: str`, `imap_password: str`, `imap_use_ssl: bool`, `imap_mailbox: str`, `imap_poll_seconds: int`, `smtp_host: str`, `smtp_port: int`, `smtp_username: str`, `smtp_password: str`, `smtp_use_tls: bool`, `smtp_from_name: str`, `attachment_dir: str`, `attachment_max_bytes: int`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_config.py`:

```python
from relaydesk.config import Settings


def test_mail_settings_default_to_the_development_stack() -> None:
    """A fresh clone must have a working mail path with no external account,
    so the defaults point at the GreenMail container in docker-compose."""
    settings = Settings(_env_file=None)

    assert settings.smtp_host == "greenmail"
    assert settings.smtp_port == 3025
    assert settings.imap_host == "greenmail"
    assert settings.imap_port == 3143
    assert settings.inbound_domain == "inbound.localhost"
    assert settings.celery_broker_url.startswith("amqp://")


def test_attachment_cap_is_twenty_five_megabytes() -> None:
    assert Settings(_env_file=None).attachment_max_bytes == 26214400
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'smtp_host'`.

- [ ] **Step 3: Add the settings fields**

In `apps/api/src/relaydesk/config.py`, add to `Settings` after `web_url`:

```python
    celery_broker_url: str = "amqp://guest:guest@rabbitmq:5672//"

    inbound_domain: str = "inbound.localhost"

    imap_host: str = "greenmail"
    imap_port: int = 3143
    imap_username: str = "relaydesk"
    imap_password: str = "relaydesk"
    imap_use_ssl: bool = False
    imap_mailbox: str = "INBOX"
    imap_poll_seconds: int = 60

    smtp_host: str = "greenmail"
    smtp_port: int = 3025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_from_name: str = "Relaydesk"

    attachment_dir: str = "/var/lib/relaydesk/attachments"
    attachment_max_bytes: int = 26214400
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Add the dependencies**

In `apps/api/pyproject.toml`, add to `dependencies` (keeping alphabetical order):

```toml
    "aioimaplib>=1.1,<2",
    "aiosmtplib>=3.0,<4",
    "celery[amqp]>=5.4,<6",
```

and to `dependency-groups.dev`:

```toml
    "aiosmtpd>=1.4,<2",
```

`aiosmtpd` is the in-process SMTP server the outbound tests assert against; it is a test dependency and must not appear in `dependencies`.

- [ ] **Step 6: Add the compose services**

In `docker-compose.yml`, add alongside the existing `postgres`, `api`, and `web` services. Match the existing file's indentation and its `env_file`/`depends_on` conventions exactly — read the `api` service first and mirror it.

```yaml
  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  greenmail:
    image: greenmail/standalone:2.1.0
    environment:
      # `setup.test.all` opens SMTP 3025, POP3 3110, IMAP 3143 (plus TLS
      # variants) against a single store, so mail we send is mail we can then
      # poll. `auth.disabled` auto-creates any mailbox on first use, which is
      # what lets a fresh clone work with no account setup.
      GREENMAIL_OPTS: >-
        -Dgreenmail.setup.test.all
        -Dgreenmail.hostname=0.0.0.0
        -Dgreenmail.auth.disabled
        -Dgreenmail.verbose
    ports:
      - "3025:3025"
      - "3143:3143"
```

Then the two worker services. They reuse the API image and bind mount, so a code change is picked up without a rebuild:

```yaml
  worker:
    build: ./apps/api
    env_file: .env
    depends_on:
      postgres:
        condition: service_started
      rabbitmq:
        condition: service_healthy
    volumes:
      - ./apps/api:/app
      - attachments:/var/lib/relaydesk/attachments
    command: celery -A relaydesk.worker.app worker --loglevel=info --concurrency=2

  beat:
    build: ./apps/api
    env_file: .env
    depends_on:
      rabbitmq:
        condition: service_healthy
    volumes:
      - ./apps/api:/app
    command: celery -A relaydesk.worker.app beat --loglevel=info
```

Add `attachments:` and `rabbitmq-data:` to the top-level `volumes:` block, and mount `attachments:/var/lib/relaydesk/attachments` on the `api` service too — the download route in Task 11 reads the same files the worker writes.

- [ ] **Step 7: Add the environment variables**

Append to `.env.example`:

```
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
INBOUND_DOMAIN=inbound.localhost
IMAP_HOST=greenmail
IMAP_PORT=3143
IMAP_USERNAME=relaydesk
IMAP_PASSWORD=relaydesk
IMAP_USE_SSL=false
IMAP_MAILBOX=INBOX
IMAP_POLL_SECONDS=60
SMTP_HOST=greenmail
SMTP_PORT=3025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=false
SMTP_FROM_NAME=Relaydesk
ATTACHMENT_DIR=/var/lib/relaydesk/attachments
ATTACHMENT_MAX_BYTES=26214400
```

- [ ] **Step 8: Verify the stack starts**

Run: `docker compose up -d --build && docker compose ps`
Expected: `postgres`, `rabbitmq`, `greenmail`, `api`, `web` all running. `worker` and `beat` will restart-loop because `relaydesk.worker.app` does not exist yet — that is expected and Task 2 fixes it.

Run: `docker compose exec api pytest -q`
Expected: the full existing suite still passes (120 passed).

- [ ] **Step 9: Commit**

```bash
git add apps/api/pyproject.toml apps/api/src/relaydesk/config.py apps/api/tests/test_config.py docker-compose.yml .env.example
git commit -m "feat(api): add mail, broker, and attachment configuration"
```

---

### Task 2: The Celery app and the async bridge

Celery is synchronous; this codebase is async end to end. This task builds the single bridge every later task uses, so no task ever needs its own event-loop handling.

**Files:**
- Create: `apps/api/src/relaydesk/worker/__init__.py`
- Create: `apps/api/src/relaydesk/worker/bridge.py`
- Create: `apps/api/src/relaydesk/worker/app.py`
- Create: `apps/api/src/relaydesk/worker/tasks/__init__.py`
- Test: `apps/api/tests/test_worker_bridge.py` (create)

**Interfaces:**
- Consumes: `Settings.celery_broker_url`, `Settings.imap_poll_seconds` (Task 1).
- Produces:
  - `relaydesk.worker.bridge.init_worker_process() -> None`
  - `relaydesk.worker.bridge.run(coro: Coroutine[Any, Any, T]) -> T`
  - `relaydesk.worker.bridge.session_scope() -> AsyncContextManager[AsyncSession]`
  - `relaydesk.worker.app.app` — the Celery application, named `relaydesk`
  - Later tasks register with `@app.task(name="relaydesk.<name>")` and are bodied as `return bridge.run(_impl(...))`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_worker_bridge.py`. These are **synchronous** tests on purpose — `bridge.run` drives a loop itself and cannot be called from inside pytest-asyncio's running loop:

```python
import asyncio

from relaydesk.worker import bridge


def test_run_executes_a_coroutine_and_returns_its_value() -> None:
    async def answer() -> int:
        return 42

    bridge.init_worker_process()
    assert bridge.run(answer()) == 42


def test_run_reuses_one_event_loop_across_calls() -> None:
    """asyncpg binds connections to the loop that created them, so a fresh
    loop per task would discard the pool every time. One loop per process is
    what makes the engine reusable."""

    async def current_loop() -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    bridge.init_worker_process()
    first = bridge.run(current_loop())
    second = bridge.run(current_loop())

    assert first is second


def test_run_before_init_is_a_clear_error() -> None:
    async def noop() -> None:
        return None

    bridge.reset_for_tests()
    try:
        raised = None
        try:
            bridge.run(noop())
        except RuntimeError as error:
            raised = error
        assert raised is not None
        assert "init_worker_process" in str(raised)
    finally:
        bridge.init_worker_process()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_worker_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.worker'`.

- [ ] **Step 3: Write the bridge**

Create `apps/api/src/relaydesk/worker/__init__.py` (empty) and `apps/api/src/relaydesk/worker/bridge.py`:

```python
"""Synchronous Celery, asynchronous everything else.

Celery tasks are synchronous functions, but every service in this codebase is
``async def`` and enforces its own ``workspace_id`` predicates. Rather than
maintain a second, synchronous data-access path — which would mean
reimplementing that tenant scoping, and getting it wrong — tasks call
``run()`` and reuse the services unchanged.

One event loop and one engine per worker process. asyncpg binds pooled
connections to the loop that opened them, so a fresh loop per task would
throw away the pool on every message.
"""

import asyncio
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from relaydesk.config import get_settings

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_worker_process() -> None:
    """Called once per worker process, from Celery's ``worker_process_init``."""
    global _loop, _session_factory

    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    _session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


def reset_for_tests() -> None:
    global _loop, _session_factory
    _loop = None
    _session_factory = None


def run(coro: Coroutine[Any, Any, T]) -> T:
    if _loop is None:
        coro.close()
        raise RuntimeError(
            "Worker process is not initialised; init_worker_process() must run first."
        )
    return _loop.run_until_complete(coro)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError(
            "Worker process is not initialised; init_worker_process() must run first."
        )
    async with _session_factory() as session:
        yield session
```

`coro.close()` before raising matters: an un-awaited coroutine otherwise emits a `RuntimeWarning` that turns the clear error message into noise.

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_worker_bridge.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Write the Celery app**

Create `apps/api/src/relaydesk/worker/tasks/__init__.py` (empty) and `apps/api/src/relaydesk/worker/app.py`:

```python
from celery import Celery
from celery.signals import worker_process_init

from relaydesk.config import get_settings
from relaydesk.worker import bridge

settings = get_settings()

app = Celery("relaydesk", broker=settings.celery_broker_url)

app.conf.update(
    # These are fire-and-forget jobs; a result backend would add Redis for
    # results nothing reads.
    task_ignore_result=True,
    # Acknowledge after the task finishes, not on receipt, so a worker killed
    # mid-send redelivers rather than silently dropping the mail. This is what
    # makes idempotency load-bearing: see the dedupe indexes in Task 3.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="relaydesk",
    timezone="UTC",
    beat_schedule={
        "poll-inbound-mail": {
            "task": "relaydesk.imap_poll",
            "schedule": float(settings.imap_poll_seconds),
        },
        "reconcile-outbound": {
            "task": "relaydesk.reconcile_outbound",
            "schedule": 300.0,
        },
    },
)

app.autodiscover_tasks(["relaydesk.worker.tasks"], force=True)


@worker_process_init.connect
def _init_process(**_kwargs: object) -> None:
    bridge.init_worker_process()
```

The Beat entries reference tasks that Tasks 10 and 12 create. Beat logs a warning for an unregistered task and keeps running, so the schedule can be declared before its tasks exist.

- [ ] **Step 6: Add a ping task proving the worker reaches the database**

Create `apps/api/src/relaydesk/worker/tasks/health.py`:

```python
import sqlalchemy as sa

from relaydesk.worker import bridge
from relaydesk.worker.app import app


async def _ping() -> int:
    async with bridge.session_scope() as session:
        return int(await session.scalar(sa.select(sa.literal(1))) or 0)


@app.task(name="relaydesk.ping")
def ping() -> int:
    """Smoke test: proves the worker process can reach Postgres through the
    bridge. Invoked by hand, never scheduled."""
    return bridge.run(_ping())
```

- [ ] **Step 7: Verify the worker starts and executes**

Run: `docker compose up -d --build worker beat && docker compose logs --tail 30 worker`
Expected: `celery@... ready.` and the task list includes `relaydesk.ping`.

Run:
```bash
docker compose exec api python -c "
from relaydesk.worker.tasks.health import ping
print(ping.delay().id)
"
docker compose logs --tail 20 worker
```
Expected: the worker log shows `Task relaydesk.ping[...] succeeded`.

Run: `docker compose logs --tail 20 beat`
Expected: Beat is running and scheduling; warnings about the two not-yet-registered tasks are expected here.

- [ ] **Step 8: Run the full suite and lint**

Run: `docker compose exec api pytest -q && docker compose exec api ruff check .`
Expected: all tests pass, ruff clean.

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/relaydesk/worker apps/api/tests/test_worker_bridge.py
git commit -m "feat(api): add Celery worker with an async bridge to the service layer"
```

---

### Task 3: Data model and migration 0007

Every table and column the rest of the plan writes to. One migration, and three parts of it that Alembic's autogenerate will **not** produce on its own — spelled out below because getting any of them wrong fails silently rather than loudly.

**Files:**
- Create: `apps/api/src/relaydesk/models/channel_account.py`
- Create: `apps/api/src/relaydesk/models/raw_message.py`
- Create: `apps/api/src/relaydesk/models/attachment.py`
- Create: `apps/api/src/relaydesk/models/poll_state.py`
- Modify: `apps/api/src/relaydesk/models/message.py`
- Modify: `apps/api/src/relaydesk/models/contact.py`
- Modify: `apps/api/src/relaydesk/models/user.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Create: `apps/api/migrations/versions/0007_email_channel.py`
- Test: `apps/api/tests/test_email_channel_models.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces, for every later task:
  - `ChannelAccount(workspace_id, kind, ingest_token, display_name, active)`, `ChannelAccountKind.email`
  - `RawMessage(mailbox, uidvalidity, uid, raw, state, error, received_at, workspace_id, channel_account_id, external_id)`, `RawMessageState.{fetched,ingested,unrouted,throttled,failed}`
  - `Attachment(workspace_id, message_id, filename, content_type, size_bytes, sha256, storage_key, inline, content_id)`
  - `PollState(mailbox, uidvalidity, last_uid)`
  - `MessageDirection.{inbound,outbound}`, `DeliveryState.{none,queued,sent,failed}`, `MessageRole.system`
  - `Message.{direction,external_id,raw_message_id,in_reply_to,body_html,channel_account_id,delivery_state,delivery_error}`
  - `Contact.bounced_at`, `User.notify_on_assignment`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_email_channel_models.py`:

```python
import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.channel_account import ChannelAccount, ChannelAccountKind
from relaydesk.models.message import DeliveryState, Message, MessageDirection, MessageRole
from tests.factories import make_conversation, make_workspace


async def _account(session: AsyncSession, workspace_id: uuid.UUID) -> ChannelAccount:
    account = ChannelAccount(
        workspace_id=workspace_id,
        kind=ChannelAccountKind.email,
        ingest_token=uuid.uuid4().hex[:12],
        display_name="Support",
        active=True,
    )
    session.add(account)
    await session.flush()
    return account


def _message(conversation, account_id, external_id) -> Message:
    return Message(
        workspace_id=conversation.workspace_id,
        conversation_id=conversation.id,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name="Ada",
        body="hello",
        sent_at=datetime.now(UTC),
        channel_account_id=account_id,
        external_id=external_id,
    )


async def test_the_same_external_id_cannot_be_ingested_twice(
    db_session: AsyncSession,
) -> None:
    """RabbitMQ is at-least-once, so a redelivered ingest task must append
    nothing the second time. This index is what makes that true."""
    workspace = await make_workspace(db_session)
    account = await _account(db_session, workspace.id)
    conversation = await make_conversation(db_session, workspace)

    db_session.add(_message(conversation, account.id, "<abc@example.com>"))
    await db_session.flush()

    db_session.add(_message(conversation, account.id, "<abc@example.com>"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_many_messages_may_have_no_external_id(
    db_session: AsyncSession,
) -> None:
    """The index must be partial. Postgres treats NULLs as distinct, so a
    plain unique index would appear to work here while silently permitting
    the duplicates it exists to prevent."""
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)

    db_session.add(_message(conversation, None, None))
    db_session.add(_message(conversation, None, None))
    await db_session.flush()


async def test_system_is_an_accepted_message_role(db_session: AsyncSession) -> None:
    """Bounce notices belong to a thread but were authored by neither a
    customer nor an agent. Slice 1's migration created ck_messages_role as a
    named CHECK, so widening the enum needs the constraint recreated."""
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)

    message = _message(conversation, None, None)
    message.role = MessageRole.system
    db_session.add(message)
    await db_session.flush()


async def test_delivery_state_defaults_to_none(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)

    message = _message(conversation, None, None)
    db_session.add(message)
    await db_session.flush()

    assert message.delivery_state == DeliveryState.none


async def test_existing_users_default_to_wanting_assignment_email(
    db_session: AsyncSession,
) -> None:
    """A Python-side default does not touch rows the migration already
    created, so this column needs a server default."""
    workspace = await make_workspace(db_session)
    from tests.factories import make_member

    member = await make_member(db_session, workspace, email="ada@example.com")
    value = await db_session.scalar(
        sa.text("SELECT notify_on_assignment FROM users WHERE id = :id").bindparams(
            id=member.user_id if hasattr(member, "user_id") else member.id
        )
    )
    assert value is True
```

If `make_member`'s return type does not expose `user_id`, read its signature in `tests/factories.py:32` and use whatever it returns to reach the user id — the assertion is what matters, not the accessor.

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_email_channel_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.models.channel_account'`.

- [ ] **Step 3: Write the four new models**

`apps/api/src/relaydesk/models/channel_account.py`:

```python
import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class ChannelAccountKind(enum.StrEnum):
    email = "email"


class ChannelAccount(UUIDMixin, TimestampMixin, Base):
    """A workspace's ingest address.

    Holds no credentials by design: the deployment owns one mailbox,
    configured through the environment, and workspaces are distinguished by
    the address mail was forwarded to. A database compromise therefore grants
    no mailbox access.
    """

    __tablename__ = "channel_accounts"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[ChannelAccountKind] = mapped_column(
        Enum(
            ChannelAccountKind,
            name="ck_channel_accounts_kind",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ChannelAccountKind.email,
        nullable=False,
    )
    ingest_token: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

`apps/api/src/relaydesk/models/raw_message.py`:

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class RawMessageState(enum.StrEnum):
    fetched = "fetched"
    ingested = "ingested"
    unrouted = "unrouted"
    throttled = "throttled"
    failed = "failed"


class RawMessage(UUIDMixin, TimestampMixin, Base):
    """Immutable landing zone for one fetched message.

    Parsing happens in a separate task so a message we cannot parse fails
    alone rather than wedging the poll, and so the bytes survive for replay
    once the parser is fixed.
    """

    __tablename__ = "raw_messages"
    __table_args__ = (UniqueConstraint("mailbox", "uidvalidity", "uid"),)

    mailbox: Mapped[str] = mapped_column(String(255), nullable=False)
    uidvalidity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    state: Mapped[RawMessageState] = mapped_column(
        Enum(
            RawMessageState,
            name="ck_raw_messages_state",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=RawMessageState.fetched,
        nullable=False,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # All three are unknown until routing succeeds.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
    )
    channel_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("channel_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(998), nullable=True)
```

`apps/api/src/relaydesk/models/attachment.py`:

```python
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Attachment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_message", "message_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Display only. The sender chose this string, so it never reaches a path.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    inline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

`apps/api/src/relaydesk/models/poll_state.py`:

```python
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class PollState(UUIDMixin, TimestampMixin, Base):
    """Where the poller got to. One row per mailbox.

    ``uidvalidity`` is stored beside ``last_uid`` because IMAP servers may
    renumber UIDs; when the server reports a different value, every stored UID
    is meaningless and the poller must re-sync from zero.
    """

    __tablename__ = "poll_state"

    mailbox: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    uidvalidity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_uid: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
```

- [ ] **Step 4: Extend the existing models**

In `apps/api/src/relaydesk/models/message.py`, add `system` to `MessageRole`, add two enums, and add the columns. Import `Boolean` is not needed; add `Index` and `sqlalchemy as sa` to the imports.

```python
class MessageRole(enum.StrEnum):
    customer = "customer"
    agent = "agent"
    ai = "ai"
    # Bounce notices and delivery failures belong to a thread but were
    # authored by neither a customer nor an agent.
    system = "system"


class MessageDirection(enum.StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class DeliveryState(enum.StrEnum):
    none = "none"
    queued = "queued"
    sent = "sent"
    failed = "failed"
```

Replace `__table_args__` with:

```python
    __table_args__ = (
        Index("ix_messages_thread", "conversation_id", "sent_at"),
        # Partial on purpose. Postgres treats NULLs as distinct in a unique
        # index, so a plain index here would permit unlimited duplicate
        # (NULL, NULL) rows — which is every outbound and seeded message —
        # while appearing to enforce the constraint.
        Index(
            "uq_messages_channel_external",
            "channel_account_id",
            "external_id",
            unique=True,
            postgresql_where=sa.text(
                "channel_account_id IS NOT NULL AND external_id IS NOT NULL"
            ),
        ),
    )
```

and add the columns after `sent_at`:

```python
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(
            MessageDirection,
            name="ck_messages_direction",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=MessageDirection.outbound,
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(String(998), nullable=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(998), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_message_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("raw_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("channel_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    delivery_state: Mapped[DeliveryState] = mapped_column(
        Enum(
            DeliveryState,
            name="ck_messages_delivery_state",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=DeliveryState.none,
        server_default="none",
        nullable=False,
    )
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    attachments = relationship(
        "Attachment", lazy="selectin", cascade="all, delete-orphan"
    )
```

`relationship` must be imported from `sqlalchemy.orm` in this file if it is not already.

In `contact.py` add:

```python
    bounced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

In `user.py` add:

```python
    notify_on_assignment: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=sa.true(), nullable=False
    )
```

Register all four new models in `models/__init__.py` following the existing import style there — Alembic's autogenerate only sees models that have been imported.

- [ ] **Step 5: Generate the migration**

Run: `docker compose exec api alembic revision --autogenerate -m "email channel"`

Rename the generated file to `0007_email_channel.py` and set `revision = "0007"`, `down_revision = "0006"`, matching the convention in `migrations/versions/0006_enum_check_constraints.py`.

- [ ] **Step 6: Hand-write the three things autogenerate misses**

Read the generated file and add these. Each fails silently if omitted.

**(a) `ck_messages_role` is not diffed.** SQLAlchemy does not autogenerate `CHECK` constraint changes, so widening `MessageRole` produces no migration output at all — and the old constraint would reject every `system` row at runtime. In `upgrade()`:

```python
    op.drop_constraint("ck_messages_role", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_role",
        "messages",
        sa.text("role IN ('customer', 'agent', 'ai', 'system')"),
    )
```

and the reverse in `downgrade()`, restoring the three-value form.

**(b) `direction` must be backfilled, not defaulted.** Autogenerate will emit a nullable column or demand a server default. A blanket default would mark every seeded customer message as outbound. Replace the generated `add_column` for `direction` with:

```python
    op.add_column("messages", sa.Column("direction", sa.String(16), nullable=True))
    op.execute(
        "UPDATE messages SET direction = "
        "CASE WHEN role = 'customer' THEN 'inbound' ELSE 'outbound' END"
    )
    op.alter_column("messages", "direction", nullable=False)
    op.create_check_constraint(
        "ck_messages_direction",
        "messages",
        sa.text("direction IN ('inbound', 'outbound')"),
    )
```

**(c) The partial index needs its `postgresql_where`.** Confirm the generated `create_index` for `uq_messages_channel_external` carries `postgresql_where=sa.text("channel_account_id IS NOT NULL AND external_id IS NOT NULL")`. If autogenerate dropped it, add it — without the predicate the index is not partial, and `test_many_messages_may_have_no_external_id` is the test that catches it.

- [ ] **Step 7: Run the migration and the tests**

Run: `docker compose exec api alembic upgrade head`
Expected: `Running upgrade 0006 -> 0007`.

Run: `docker compose exec api pytest tests/test_email_channel_models.py -v`
Expected: PASS (5 passed).

- [ ] **Step 8: Verify the migration matches the models**

Run: `docker compose exec api alembic revision --autogenerate -m "verify"`
Expected: the generated file's `upgrade()` body is empty (only `pass`). Any operation in it means a model and the migration disagree — fix the migration, not the model.

Then delete the verification file: `docker compose exec api rm migrations/versions/*_verify.py`

- [ ] **Step 9: Run the full suite**

Run: `docker compose exec api pytest -q && docker compose exec api ruff check .`
Expected: all tests pass (125+), ruff clean.

- [ ] **Step 10: Commit**

```bash
git add apps/api/src/relaydesk/models apps/api/migrations/versions/0007_email_channel.py apps/api/tests/test_email_channel_models.py
git commit -m "feat(api): add channel, raw message, attachment, and delivery models"
```

---

### Task 4: The mailer and assignment notifications

The only module that speaks SMTP, plus its first real consumer. This task is early on purpose: it delivers a visible improvement and proves the worker, the bridge, and SMTP in one pass, before any inbound machinery exists.

**Files:**
- Create: `apps/api/src/relaydesk/services/mailer.py`
- Create: `apps/api/src/relaydesk/services/queue.py`
- Create: `apps/api/src/relaydesk/worker/tasks/mail.py`
- Create: `apps/api/src/relaydesk/services/notifications.py`
- Modify: `apps/api/src/relaydesk/services/conversations.py` (`set_assignee`)
- Modify: `apps/api/src/relaydesk/api/auth.py` (add `PATCH /me`)
- Test: `apps/api/tests/test_mailer.py` (create)
- Test: `apps/api/tests/test_assignment_notifications.py` (create)

**Interfaces:**
- Consumes: `bridge.run`, `bridge.session_scope`, `app` (Task 2); `User.notify_on_assignment` (Task 3); SMTP settings (Task 1).
- Produces:
  - `services.mailer.send(to: str, subject: str, text_body: str, html_body: str | None = None, headers: dict[str, str] | None = None) -> None` — async
  - `services.mailer.system_headers() -> dict[str, str]`
  - `services.queue.enqueue_system_email(to: str, subject: str, text_body: str, html_body: str | None) -> None` — the seam tests monkeypatch
  - `worker.tasks.mail.send_system_email` — Celery task, `name="relaydesk.send_system_email"`
  - `services.notifications.notify_assignment(session, conversation, assignee, actor) -> None`

- [ ] **Step 1: Write the failing mailer test**

Create `apps/api/tests/test_mailer.py`. It runs a real SMTP server in-process, so it asserts what actually goes on the wire rather than what a mock was told:

```python
import asyncio
from email import message_from_bytes
from email.policy import default as default_policy

import pytest
from aiosmtpd.controller import Controller

from relaydesk.config import get_settings
from relaydesk.services import mailer


class _Collector:
    def __init__(self) -> None:
        self.messages: list[bytes] = []

    async def handle_DATA(self, server, session, envelope) -> str:  # noqa: N802
        self.messages.append(envelope.content)
        return "250 OK"


@pytest.fixture
def smtp_server(monkeypatch):
    collector = _Collector()
    controller = Controller(collector, hostname="127.0.0.1", port=0)
    controller.start()
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(settings, "smtp_port", controller.port)
    monkeypatch.setattr(settings, "smtp_use_tls", False)
    try:
        yield collector
    finally:
        controller.stop()


async def test_send_delivers_a_multipart_alternative(smtp_server) -> None:
    """HTML-only mail lands in spam folders. Every system email carries a
    text part."""
    await mailer.send(
        to="ada@example.com",
        subject="You have a ticket",
        text_body="Plain words.",
        html_body="<p>Plain words.</p>",
    )

    assert len(smtp_server.messages) == 1
    sent = message_from_bytes(smtp_server.messages[0], policy=default_policy)
    assert sent["To"] == "ada@example.com"
    assert sent["Subject"] == "You have a ticket"
    assert sent.get_content_type() == "multipart/alternative"
    parts = {part.get_content_type() for part in sent.iter_parts()}
    assert parts == {"text/plain", "text/html"}


async def test_system_mail_is_marked_auto_generated(smtp_server) -> None:
    """Without this header, our notification and a customer's vacation
    responder will mail each other until one of them exhausts a quota."""
    await mailer.send(
        to="ada@example.com",
        subject="Hello",
        text_body="Hi",
        headers=mailer.system_headers(),
    )

    sent = message_from_bytes(smtp_server.messages[0], policy=default_policy)
    assert sent["Auto-Submitted"] == "auto-generated"


async def test_a_text_only_message_is_not_multipart(smtp_server) -> None:
    await mailer.send(to="ada@example.com", subject="Hello", text_body="Hi")

    sent = message_from_bytes(smtp_server.messages[0], policy=default_policy)
    assert sent.get_content_type() == "text/plain"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_mailer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.services.mailer'`.

- [ ] **Step 3: Write the mailer**

`apps/api/src/relaydesk/services/mailer.py`:

```python
"""The only module in Relaydesk that speaks SMTP."""

from email.message import EmailMessage

import aiosmtplib

from relaydesk.config import get_settings


def system_headers() -> dict[str, str]:
    """Headers for mail Relaydesk generates itself.

    ``Auto-Submitted: auto-generated`` tells the recipient's mail system not
    to answer this automatically. Sending it is half of the loop prevention
    in this slice; refusing to answer messages that carry it is the other
    half, and lives in the inbound classifier.
    """
    return {"Auto-Submitted": "auto-generated"}


def from_address() -> str:
    settings = get_settings()
    return f"{settings.smtp_from_name} <noreply@{settings.inbound_domain}>"


def build(
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    headers: dict[str, str] | None = None,
    sender: str | None = None,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender or from_address()
    message["To"] = to
    message["Subject"] = subject
    for name, value in (headers or {}).items():
        message[name] = value

    message.set_content(text_body)
    if html_body is not None:
        # Promotes the message to multipart/alternative with the text part
        # first, which is the ordering mail clients expect.
        message.add_alternative(html_body, subtype="html")
    return message


async def send(
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    headers: dict[str, str] | None = None,
    sender: str | None = None,
) -> None:
    settings = get_settings()
    message = build(to, subject, text_body, html_body, headers, sender)
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_use_tls,
    )


async def send_message(message: EmailMessage) -> None:
    """Send an already-built message. Used by the outbound reply path, which
    needs full control of From, Reply-To, and the threading headers."""
    settings = get_settings()
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_use_tls,
    )
```

- [ ] **Step 4: Run the mailer tests**

Run: `docker compose exec api pytest tests/test_mailer.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Write the failing notification test**

Create `apps/api/tests/test_assignment_notifications.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.services import conversations, queue
from tests.factories import make_conversation, make_member, make_workspace


@pytest.fixture
def outbox(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    def record(to: str, subject: str, text_body: str, html_body=None) -> None:
        sent.append({"to": to, "subject": subject, "text": text_body})

    monkeypatch.setattr(queue, "enqueue_system_email", record)
    return sent


async def test_assigning_to_someone_else_emails_them(
    db_session: AsyncSession, outbox: list[dict]
) -> None:
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    other = await make_member(db_session, workspace, email="sara@example.com")
    conversation = await make_conversation(db_session, workspace, subject="Refund")

    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, other.user.id, actor.user
    )

    assert len(outbox) == 1
    assert outbox[0]["to"] == "sara@example.com"
    assert "Refund" in outbox[0]["subject"]


async def test_assigning_to_yourself_emails_nobody(
    db_session: AsyncSession, outbox: list[dict]
) -> None:
    """Picking a ticket up off the queue is the most common assignment there
    is, and mailing yourself about it is noise."""
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    conversation = await make_conversation(db_session, workspace)

    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, actor.user.id, actor.user
    )

    assert outbox == []


async def test_the_preference_is_honoured(
    db_session: AsyncSession, outbox: list[dict]
) -> None:
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    other = await make_member(db_session, workspace, email="sara@example.com")
    other.user.notify_on_assignment = False
    await db_session.flush()
    conversation = await make_conversation(db_session, workspace)

    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, other.user.id, actor.user
    )

    assert outbox == []


async def test_unassigning_emails_nobody(
    db_session: AsyncSession, outbox: list[dict]
) -> None:
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    other = await make_member(db_session, workspace, email="sara@example.com")
    conversation = await make_conversation(db_session, workspace)
    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, other.user.id, actor.user
    )
    outbox.clear()

    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, None, actor.user
    )

    assert outbox == []
```

`make_member` in `tests/factories.py:32` returns a membership; read it and use whatever attribute reaches the `User` row. If it does not expose one, extend the factory to return the user alongside the membership rather than reaching into the session.

- [ ] **Step 6: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_assignment_notifications.py -v`
Expected: FAIL — `queue` has no attribute `enqueue_system_email`.

- [ ] **Step 7: Write the queue seam and the notification**

`apps/api/src/relaydesk/services/queue.py`:

```python
"""The one place service code hands work to Celery.

Kept as a module of plain functions so tests can monkeypatch a single name
instead of standing up a broker, and so services never import Celery
directly — which would make importing any service pull in the worker.
"""


def enqueue_system_email(
    to: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    from relaydesk.worker.tasks.mail import send_system_email

    send_system_email.delay(to, subject, text_body, html_body)
```

`apps/api/src/relaydesk/worker/tasks/mail.py`:

```python
from relaydesk.services import mailer
from relaydesk.worker import bridge
from relaydesk.worker.app import app


@app.task(
    name="relaydesk.send_system_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def send_system_email(
    to: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    bridge.run(
        mailer.send(
            to=to,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            headers=mailer.system_headers(),
        )
    )
```

`apps/api/src/relaydesk/services/notifications.py`:

```python
from relaydesk.config import get_settings
from relaydesk.models.conversation import Conversation
from relaydesk.models.user import User
from relaydesk.services import queue

ASSIGNMENT_TEXT = """\
{actor} assigned a conversation to you.

{subject}
From {customer}

Open it: {url}
"""


def notify_assignment(
    conversation: Conversation, assignee: User, actor: User
) -> None:
    """Fire-and-forget. Never raises into the caller's request: an email that
    fails to enqueue must not fail the assignment itself."""
    if assignee.id == actor.id or not assignee.notify_on_assignment:
        return

    url = f"{get_settings().web_url}/conversations/{conversation.id}"
    queue.enqueue_system_email(
        to=assignee.email,
        subject=f"Assigned to you: {conversation.subject}",
        text_body=ASSIGNMENT_TEXT.format(
            actor=actor.name,
            subject=conversation.subject,
            customer=conversation.contact.name if conversation.contact else "a customer",
            url=url,
        ),
    )
```

- [ ] **Step 8: Wire it into `set_assignee`**

In `apps/api/src/relaydesk/services/conversations.py`, inside `set_assignee`, after `await session.commit()` and the existing `session.refresh(...)` call, add:

```python
    if conversation.assignee is not None:
        notifications.notify_assignment(conversation, conversation.assignee, actor)
```

It must come **after** the commit. Enqueuing before would publish a job for an assignment that a later failure rolls back, and the recipient would get mail about a ticket that was never assigned to them.

- [ ] **Step 9: Run the notification tests**

Run: `docker compose exec api pytest tests/test_assignment_notifications.py -v`
Expected: PASS (4 passed).

- [ ] **Step 10: Add `PATCH /auth/me` for the preference**

In `apps/api/src/relaydesk/api/auth.py`, beside the existing `GET /me` at line 69, add a request model and route. Follow the file's existing schema style — the shared base class that sets `alias_generator=to_camel` is already imported there.

```python
class MePatch(CamelModel):
    name: str | None = None
    notify_on_assignment: bool | None = None


@router.patch("/me", response_model=MeResponse)
async def update_me(payload: MePatch, scope: Scope, session: DbSession) -> MeResponse:
    if payload.name is not None:
        scope.user.name = payload.name.strip()
    if payload.notify_on_assignment is not None:
        scope.user.notify_on_assignment = payload.notify_on_assignment
    await session.commit()
    return await me(scope, session)
```

Replace `CamelModel` with whatever the file's existing base model is actually called — read the top of `api/auth.py` and match it.

Add to `apps/api/tests/test_assignment_notifications.py`:

```python
async def test_patch_me_toggles_the_preference(db_session, client) -> None:
    from tests.factories import sign_in

    workspace = await make_workspace(db_session)
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    token = await sign_in(db_session, member)

    response = await client.patch(
        "/api/auth/me",
        json={"notifyOnAssignment": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["notifyOnAssignment"] is False
```

`MeResponse` must expose `notify_on_assignment` on its user block for this to pass — add it to the response model beside `time_zone` at `api/auth.py:78`.

Read `sign_in` at `tests/factories.py:136` for its exact signature before using it.

- [ ] **Step 11: Verify end to end against GreenMail**

Run:
```bash
docker compose exec api python -c "
from relaydesk.worker.tasks.mail import send_system_email
send_system_email.delay('ada@example.com', 'Hello from Relaydesk', 'It works.')
"
docker compose logs --tail 10 worker
```
Expected: `Task relaydesk.send_system_email[...] succeeded`.

Confirm GreenMail received it:
```bash
docker compose exec api python -c "
import asyncio, aioimaplib
async def main():
    client = aioimaplib.IMAP4(host='greenmail', port=3143)
    await client.wait_hello_from_server()
    await client.login('ada@example.com', 'ada')
    await client.select('INBOX')
    print(await client.search('ALL'))
asyncio.run(main())
"
```
Expected: a search result naming at least one message.

- [ ] **Step 12: Full suite, lint, commit**

Run: `docker compose exec api pytest -q && docker compose exec api ruff check .`
Expected: all pass, ruff clean.

```bash
git add apps/api/src/relaydesk apps/api/tests/test_mailer.py apps/api/tests/test_assignment_notifications.py
git commit -m "feat(api): add the mailer and assignment notification email"
```

---

### Task 5: Scope sessions to a workspace

A prerequisite for Task 6, not a refactor. `services/team.py:84-115` lists four residual risks that made invites unshippable in slice 1. Emailing the token (Task 6) closes two of them — proof of address control, and an admin burning an address they do not own. It does **not** close these two:

- A session outlives the membership it was minted for. Sessions are user-scoped and `auth.active_membership` re-derives the workspace from the user's *current* memberships on every request, so a session survives its membership being deleted and silently re-points at whatever workspace that user joins next.
- Nothing stops one user holding two active memberships. `active_membership` runs a bare `SELECT ... WHERE user_id =` with no `ORDER BY`, so which workspace a login resolves to becomes arbitrary. Invites are the feature that makes this reachable by an ordinary user.

Both are fixed by recording the workspace on the session at the moment it is minted.

**Files:**
- Modify: `apps/api/src/relaydesk/models/session.py`
- Modify: `apps/api/src/relaydesk/services/auth.py`
- Modify: `apps/api/src/relaydesk/api/deps.py`
- Modify: `apps/api/src/relaydesk/api/auth.py`
- Create: `apps/api/migrations/versions/0008_session_workspace.py`
- Test: `apps/api/tests/test_session_scoping.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks in this plan.
- Produces, replacing the current signatures:
  - `Session.workspace_id: uuid.UUID` (not null)
  - `auth.create_session(session, user, membership, user_agent=None, ip=None) -> tuple[str, Session]` — **now takes the membership**
  - `auth.default_membership(session, user) -> Membership` — deterministic pick at login
  - `auth.active_membership(session, user, workspace_id) -> Membership` — **now takes a workspace id**
  - `auth.resolve_session(session, token) -> tuple[User, Session]` — **now returns the row too**

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_session_scoping.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Unauthorized
from relaydesk.models.membership import MembershipStatus
from relaydesk.services import auth
from tests.factories import make_member, make_workspace


async def test_a_session_names_the_workspace_it_was_minted_for(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    member = await make_member(db_session, workspace, email="ada@example.com")

    _token, row = await auth.create_session(db_session, member.user, member)

    assert row.workspace_id == workspace.id


async def test_a_session_dies_with_its_membership(db_session: AsyncSession) -> None:
    """Previously the session survived and silently re-pointed at whatever
    workspace the user joined next — a removed agent's old token becoming a
    live token in someone else's workspace."""
    workspace = await make_workspace(db_session)
    member = await make_member(db_session, workspace, email="ada@example.com")
    token, _row = await auth.create_session(db_session, member.user, member)

    member.status = MembershipStatus.removed
    await db_session.commit()

    user, row = await auth.resolve_session(db_session, token)
    with pytest.raises(Unauthorized):
        await auth.active_membership(db_session, user, row.workspace_id)


async def test_a_second_membership_does_not_move_an_existing_session(
    db_session: AsyncSession,
) -> None:
    """Two active memberships used to make the resolved workspace arbitrary.
    Invites are what put that within reach of an ordinary user."""
    first = await make_workspace(db_session, slug="first")
    second = await make_workspace(db_session, slug="second")
    member = await make_member(db_session, first, email="ada@example.com")
    token, _row = await auth.create_session(db_session, member.user, member)

    await make_member(db_session, second, email="ada@example.com", user=member.user)

    user, row = await auth.resolve_session(db_session, token)
    membership = await auth.active_membership(db_session, user, row.workspace_id)

    assert membership.workspace_id == first.id


async def test_login_picks_the_oldest_membership_deterministically(
    db_session: AsyncSession,
) -> None:
    first = await make_workspace(db_session, slug="first")
    second = await make_workspace(db_session, slug="second")
    member = await make_member(db_session, first, email="ada@example.com")
    await make_member(db_session, second, email="ada@example.com", user=member.user)

    chosen = await auth.default_membership(db_session, member.user)

    assert chosen.workspace_id == first.id
```

`make_member` currently creates its own user. Extend it in `tests/factories.py` to accept an optional `user: User | None = None` and reuse it when given, rather than creating a second user for the same address — the two tests above need one user in two workspaces.

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_session_scoping.py -v`
Expected: FAIL — `create_session() takes 2 positional arguments but 3 were given`.

- [ ] **Step 3: Add the column**

In `models/session.py`, after `user_id`:

```python
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
```

- [ ] **Step 4: Change the three auth functions**

In `services/auth.py`:

```python
async def default_membership(session: AsyncSession, user: User) -> Membership:
    """The membership a fresh login resolves to.

    Ordered so the answer is stable. There is no workspace switcher yet, so a
    user with two memberships always lands in the one they joined first
    rather than in whichever row the planner happened to return.
    """
    membership = await session.scalar(
        sa.select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.active,
        )
        .order_by(Membership.created_at, Membership.id)
        .limit(1)
    )
    if membership is None:
        raise Unauthorized(BAD_CREDENTIALS)
    return membership


async def active_membership(
    session: AsyncSession, user: User, workspace_id: uuid.UUID
) -> Membership:
    """The user's active membership in one specific workspace.

    Scoped by workspace because the session names one. A session must never
    follow its user into a workspace it was not minted for.
    """
    membership = await session.scalar(
        sa.select(Membership).where(
            Membership.user_id == user.id,
            Membership.workspace_id == workspace_id,
            Membership.status == MembershipStatus.active,
        )
    )
    if membership is None:
        raise Unauthorized(BAD_CREDENTIALS)
    return membership
```

`create_session` takes the membership and records it:

```python
async def create_session(
    session: AsyncSession,
    user: User,
    membership: Membership,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, Session]:
    """Return the plaintext token and the stored row. Only the hash persists."""
    settings = get_settings()
    now = datetime.now(UTC)
    token = generate_token()
    row = Session(
        user_id=user.id,
        workspace_id=membership.workspace_id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=settings.session_ttl_days),
        last_seen_at=now,
        user_agent=user_agent[:USER_AGENT_MAX_LENGTH] if user_agent else user_agent,
        ip=ip,
    )
    session.add(row)
    await session.commit()
    return token, row
```

`resolve_session` returns the row alongside the user, so callers can read `workspace_id` without a second query. Update its return type and its single `return` statement.

- [ ] **Step 5: Update the callers**

`create_session` has exactly two callers — confirm with:

```bash
docker compose exec api grep -rn "create_session\|active_membership\|resolve_session" src/
```

Update each: the password login and the Google exchange in `api/auth.py` call `default_membership` first and pass the result; `api/deps.py`'s `Scope` builder takes the `(user, row)` pair from `resolve_session` and passes `row.workspace_id` to `active_membership`. Read `api/deps.py` before editing — `Scope` already carries `workspace_id`, `workspace`, `user`, and `membership`, and this changes only where `workspace_id` comes from.

- [ ] **Step 6: Write migration 0008**

`docker compose exec api alembic revision --autogenerate -m "session workspace"`, renamed to `0008_session_workspace.py` with `revision = "0008"`, `down_revision = "0007"`.

Replace the generated `add_column` — a `NOT NULL` column cannot be added to a table with rows, and there is no sensible default:

```python
    op.add_column(
        "sessions",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Backfill from each session user's active membership.
    op.execute(
        """
        UPDATE sessions SET workspace_id = m.workspace_id
        FROM memberships m
        WHERE m.user_id = sessions.user_id AND m.status = 'active'
        """
    )
    # A session whose user has no active membership could never authenticate
    # anyway; deleting is correct and keeps the column NOT NULL.
    op.execute("DELETE FROM sessions WHERE workspace_id IS NULL")
    op.alter_column("sessions", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_sessions_workspace_id",
        "sessions",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_sessions_workspace_id", "sessions", ["workspace_id"])
```

- [ ] **Step 7: Run the migration and the tests**

Run: `docker compose exec api alembic upgrade head && docker compose exec api pytest tests/test_session_scoping.py -v`
Expected: PASS (4 passed).

- [ ] **Step 8: Run the full suite**

Run: `docker compose exec api pytest -q`
Expected: all pass. Existing auth tests will need their `create_session` calls updated; that is expected churn, not a regression — but any test that changes must still assert the same behaviour it asserted before.

Run: `docker compose exec api ruff check .`

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/relaydesk apps/api/migrations/versions/0008_session_workspace.py apps/api/tests
git commit -m "fix(api): scope sessions to the workspace they were minted for"
```

---

### Task 6: Re-enable invites

Slice 1 disabled invites because acceptance issued a session for an address nobody had proved they controlled. The fix is the delivery channel, not a new check: **the token is mailed to the invited address and returned to nobody.** Possession of it is then proof of control.

**Files:**
- Modify: `apps/api/src/relaydesk/api/team.py` (remove the 503 stubs, add the real routes)
- Modify: `apps/api/src/relaydesk/api/router.py` (mount the public invite router)
- Modify: `apps/api/src/relaydesk/services/team.py` (comment block, `create_invite` mails)
- Modify: `apps/api/src/relaydesk/services/notifications.py` (invite template)
- Modify: `README.md`
- Test: `apps/api/tests/test_invites.py` (modify — it exists and tests the service directly)

**Interfaces:**
- Consumes: `queue.enqueue_system_email` (Task 4), workspace-scoped sessions (Task 5).
- Produces: `POST /api/team/invites -> 202`, `DELETE /api/team/invites/{id} -> 204`, `GET /api/invites/{token}`, `POST /api/invites/{token}/accept`.

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/test_invites.py`:

```python
async def test_creating_an_invite_returns_no_token(
    db_session, client, outbox
) -> None:
    """The whole security property of this feature: the token reaches the
    invited address and nobody else. An inviteUrl in the response would hand
    it straight back to whoever made the request."""
    workspace = await make_workspace(db_session)
    admin = await make_member(db_session, workspace, email="nilesh@example.com", role=Role.admin)
    token = await sign_in(db_session, admin)

    response = await client.post(
        "/api/team/invites",
        json={"email": "sara@example.com", "role": "Agent"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 202
    assert "inviteUrl" not in response.text
    assert "token" not in response.text.lower()

    assert len(outbox) == 1
    assert outbox[0]["to"] == "sara@example.com"
    assert "/invites/" in outbox[0]["text"]


async def test_an_agent_cannot_invite(db_session, client, outbox) -> None:
    workspace = await make_workspace(db_session)
    agent = await make_member(db_session, workspace, email="sara@example.com", role=Role.agent)
    token = await sign_in(db_session, agent)

    response = await client.post(
        "/api/team/invites",
        json={"email": "new@example.com", "role": "Agent"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert outbox == []


async def test_an_invite_can_only_be_accepted_once(db_session, client, outbox) -> None:
    workspace = await make_workspace(db_session)
    admin = await make_member(db_session, workspace, email="nilesh@example.com", role=Role.admin)
    _invite, raw_token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.user.id
    )
    await db_session.commit()

    first = await client.post(
        f"/api/invites/{raw_token}/accept",
        json={"name": "Sara", "password": "correct horse battery staple"},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/invites/{raw_token}/accept",
        json={"name": "Sara", "password": "correct horse battery staple"},
    )
    assert second.status_code == 409


async def test_an_expired_invite_cannot_be_accepted(db_session, client) -> None:
    from datetime import UTC, datetime, timedelta

    workspace = await make_workspace(db_session)
    admin = await make_member(db_session, workspace, email="nilesh@example.com", role=Role.admin)
    invite, raw_token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.user.id
    )
    invite.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        f"/api/invites/{raw_token}/accept",
        json={"name": "Sara", "password": "correct horse battery staple"},
    )

    assert response.status_code == 404


async def test_accepting_lands_in_the_inviting_workspace(
    db_session, client, outbox
) -> None:
    """Task 5 pins the session to a workspace; this proves acceptance mints
    it for the workspace that issued the invite."""
    workspace = await make_workspace(db_session, slug="acme")
    admin = await make_member(db_session, workspace, email="nilesh@example.com", role=Role.admin)
    _invite, raw_token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.user.id
    )
    await db_session.commit()

    accept = await client.post(
        f"/api/invites/{raw_token}/accept",
        json={"name": "Sara", "password": "correct horse battery staple"},
    )
    session_token = accept.json()["token"]

    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {session_token}"}
    )

    assert me.json()["workspace"]["id"] == str(workspace.id)
```

Move the `outbox` fixture from `tests/test_assignment_notifications.py` into `tests/conftest.py` so both modules share it rather than duplicating it.

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_invites.py -v`
Expected: FAIL with 503 on the create route.

- [ ] **Step 3: Add the invite email template**

Append to `services/notifications.py`:

```python
INVITE_TEXT = """\
{inviter} invited you to join {workspace} on Relaydesk.

Accept the invitation: {url}

This link expires in 7 days. If you weren't expecting it, ignore this
message — no account is created until you accept.
"""


def notify_invite(
    email: str, token: str, workspace_name: str, inviter_name: str
) -> None:
    url = f"{get_settings().web_url}/invites/{token}"
    queue.enqueue_system_email(
        to=email,
        subject=f"Join {workspace_name} on Relaydesk",
        text_body=INVITE_TEXT.format(
            inviter=inviter_name, workspace=workspace_name, url=url
        ),
    )
```

The plaintext token appears here and nowhere else — never in a response body, never in a log line.

- [ ] **Step 4: Replace the disabled routes**

In `api/team.py`, delete the `503` stubs and the block comment above them, replacing the comment with a short note recording why this is now safe:

```python
# Invites are enabled because the token is delivered to the invited address
# and returned to nobody. Possession of it is therefore proof of control of
# that address, which is the property slice 1 required before re-enabling.
# Do not add an invite URL to any response body: that hands the token back to
# the caller and reinstates the takeover this replaced.
@router.post("/invites", status_code=status.HTTP_202_ACCEPTED)
async def create_team_invite(
    payload: InviteRequest, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    _invite, token = await team.create_invite(
        session,
        scope.workspace_id,
        payload.email,
        _role_from_label(payload.role),
        scope.user.id,
    )
    await session.commit()
    notifications.notify_invite(
        payload.email, token, scope.workspace.name, scope.user.name
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_invite(
    invite_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    await team.revoke_invite(session, scope.workspace_id, invite_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

`notify_invite` runs after the commit, for the same reason as Task 4 step 8: a mailed invite for a row that rolled back is an invite that cannot be accepted.

- [ ] **Step 5: Make `InviteRequest.role` an enum**

A deferred slice 1 finding, in code this task already touches. In `api/team.py`, change `InviteRequest.role` and `MemberPatch.role` from bare `str` to a `Literal["Admin", "Agent"]` matching the labels `_role_from_label` accepts, so a typo is a 422 rather than a silent fallback.

- [ ] **Step 6: Mount the public invite router**

In `api/router.py`, replace the block comment explaining why the invite router is unmounted with the mount, keeping the reason recorded:

```python
# Public: acceptance is gated on possession of a token that was mailed to
# the invited address. See relaydesk.api.team.
api_router.include_router(invites_router, prefix="/invites", tags=["team"])
```

Create the router in `api/team.py` (or a sibling `api/invites.py` if `team.py` is already long — check its line count and follow the file-size norms in this repo) with the two public routes:

```python
@invites_router.get("/{token}", response_model=InvitePreview)
async def preview_invite(token: str, session: DbSession) -> InvitePreview: ...


@invites_router.post("/{token}/accept", response_model=TokenResponse)
async def accept_invite(
    token: str, payload: AcceptRequest, request: Request, session: DbSession
) -> TokenResponse: ...
```

`accept_invite` calls `team.accept_invite(...)`, then `auth.default_membership(...)`, then `auth.create_session(session, user, membership, ...)` — the Task 5 signature. It returns the same `TokenResponse` shape `POST /auth/login` returns, so the web client's existing sign-in handling works unchanged.

- [ ] **Step 7: Make acceptance single-use**

`team.accept_invite` currently sets `accepted_at`. Delete the row instead, inside the same transaction that creates the membership, so a leaked token in a mail archive is inert rather than merely rejected by a check. Update `read_invite`'s "already accepted" branch and any test that asserts on `accepted_at`.

- [ ] **Step 8: Run the tests**

Run: `docker compose exec api pytest tests/test_invites.py -v`
Expected: PASS.

- [ ] **Step 9: Update the README**

Replace the "Team invites are **not enabled** in this release" paragraph with a short statement that invites are sent by email and require SMTP to be configured, and note that the development stack's GreenMail makes this work out of the box.

- [ ] **Step 10: Full suite, lint, commit**

Run: `docker compose exec api pytest -q && docker compose exec api ruff check .`

```bash
git add apps/api README.md
git commit -m "feat(api): re-enable invites, with the token delivered by email"
```

---

### Task 7: MIME normalization

Bytes to `InboundMessage`. Pure: no database, no network, no settings. This is where hostile input arrives, so it is kept free of I/O specifically to be testable exhaustively.

**Files:**
- Create: `apps/api/src/relaydesk/email_parse/__init__.py`
- Create: `apps/api/src/relaydesk/email_parse/normalize.py`
- Test: `apps/api/tests/test_email_normalize.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ParsedAttachment(filename: str, content_type: str, content: bytes, inline: bool, content_id: str | None)` — frozen dataclass
  - `InboundMessage(message_id, in_reply_to, references, from_email, from_name, to, cc, delivered_to, subject, text_body, html_body, sent_at, headers, attachments)` — frozen dataclass; `references`, `to`, `cc`, `delivered_to`, `attachments` are tuples; `headers` is a `dict[str, str]` with lowercased keys
  - `normalize.parse(raw: bytes) -> InboundMessage`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_email_normalize.py`:

```python
from datetime import UTC, datetime
from email.message import EmailMessage

from relaydesk.email_parse import normalize


def _build(**headers: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = headers.pop("From", "Ada Lovelace <ada@example.com>")
    message["To"] = headers.pop("To", "support@acme.com")
    message["Subject"] = headers.pop("Subject", "Refund please")
    message["Date"] = headers.pop("Date", "Tue, 2 Sep 2026 10:00:00 +0000")
    message["Message-ID"] = headers.pop("Message-ID", "<a1@example.com>")
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_email_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.email_parse'`.

- [ ] **Step 3: Write the normalizer**

Create `apps/api/src/relaydesk/email_parse/__init__.py` (empty) and `apps/api/src/relaydesk/email_parse/normalize.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `docker compose exec api pytest tests/test_email_normalize.py -v`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/email_parse apps/api/tests/test_email_normalize.py
git commit -m "feat(api): normalize inbound MIME to a plain dataclass"
```

---

### Task 8: Classification

Decides what a message *is* before anything is created from it. Also pure.

**Files:**
- Create: `apps/api/src/relaydesk/email_parse/classify.py`
- Test: `apps/api/tests/test_email_classify.py` (create)

**Interfaces:**
- Consumes: `InboundMessage` (Task 7).
- Produces: `Disposition.{normal,bounce,auto_reply,bulk}`, `classify(message: InboundMessage) -> Disposition`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_email_classify.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_email_classify.py -v`
Expected: FAIL — no module `relaydesk.email_parse.classify`.

- [ ] **Step 3: Write the classifier**

```python
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
```

- [ ] **Step 4: Run the tests, lint, commit**

Run: `docker compose exec api pytest tests/test_email_classify.py -v && docker compose exec api ruff check .`
Expected: PASS (7 passed), ruff clean.

```bash
git add apps/api/src/relaydesk/email_parse/classify.py apps/api/tests/test_email_classify.py
git commit -m "feat(api): classify bounces, auto-replies, and bulk mail"
```

---

### Task 9: Channel accounts and ingest addresses

The workspace's address, and the lookup that turns a recipient back into a workspace.

**Address shape:** `<slug>-<token>@<inbound domain>`, and for replies `<slug>-<token>+c<conversation number>@<inbound domain>`.

The conversation tag uses the per-workspace `number`, not the uuid — it is short, human-legible in a mail client, and already scoped to a workspace so it cannot collide across tenants. It is also guessable, which is handled in Task 11: a tagged address only threads when the sender is the conversation's own contact.

**Files:**
- Create: `apps/api/src/relaydesk/services/channel_accounts.py`
- Create: `apps/api/src/relaydesk/api/channels.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Modify: `apps/api/src/relaydesk/services/workspaces.py` (create an account with each workspace)
- Create: `apps/api/migrations/versions/0009_backfill_channel_accounts.py`
- Test: `apps/api/tests/test_channel_accounts.py` (create)

**Interfaces:**
- Consumes: `ChannelAccount` (Task 3), `Settings.inbound_domain` (Task 1).
- Produces:
  - `channel_accounts.address_for(account: ChannelAccount, slug: str, conversation_number: int | None = None) -> str`
  - `channel_accounts.token_from_address(address: str) -> str | None`
  - `channel_accounts.conversation_number_from_address(address: str) -> int | None`
  - `channel_accounts.create(session, workspace_id, display_name) -> ChannelAccount`
  - `channel_accounts.list_for(session, workspace_id) -> list[ChannelAccount]`
  - `channel_accounts.deactivate(session, workspace_id, account_id) -> None`
  - `channel_accounts.find_by_token(session, token) -> ChannelAccount | None`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_channel_accounts.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.services import channel_accounts
from tests.factories import make_member, make_workspace, sign_in


async def test_an_address_is_slug_then_token(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    account = await channel_accounts.create(db_session, workspace.id, "Support")

    address = channel_accounts.address_for(account, "acme")

    assert address == f"acme-{account.ingest_token}@inbound.localhost"


def test_a_reply_address_carries_the_conversation_number() -> None:
    address = "acme-a3f9c2b1d4e5+c142@inbound.localhost"

    assert channel_accounts.token_from_address(address) == "a3f9c2b1d4e5"
    assert channel_accounts.conversation_number_from_address(address) == 142


def test_a_plain_address_has_no_conversation_number() -> None:
    address = "acme-a3f9c2b1d4e5@inbound.localhost"

    assert channel_accounts.token_from_address(address) == "a3f9c2b1d4e5"
    assert channel_accounts.conversation_number_from_address(address) is None


def test_a_slug_containing_dashes_still_resolves() -> None:
    """Split on the last dash, not the first: workspace slugs contain them."""
    address = "acme-support-eu-a3f9c2b1d4e5@inbound.localhost"

    assert channel_accounts.token_from_address(address) == "a3f9c2b1d4e5"


def test_an_unrelated_address_yields_no_token() -> None:
    assert channel_accounts.token_from_address("support@acme.com") is None
    assert channel_accounts.token_from_address("") is None


async def test_tokens_are_not_derived_from_the_slug(db_session: AsyncSession) -> None:
    """A derivable address would let anyone who can guess a workspace name
    post tickets into its queue."""
    first = await make_workspace(db_session, slug="acme")
    second = await make_workspace(db_session, slug="acme-two")
    one = await channel_accounts.create(db_session, first.id, "Support")
    two = await channel_accounts.create(db_session, second.id, "Support")

    assert one.ingest_token != two.ingest_token
    assert len(one.ingest_token) == 12
    assert "acme" not in one.ingest_token


async def test_lookup_by_token_finds_the_workspace(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    account = await channel_accounts.create(db_session, workspace.id, "Support")

    found = await channel_accounts.find_by_token(db_session, account.ingest_token)

    assert found is not None
    assert found.workspace_id == workspace.id


async def test_a_deactivated_account_is_not_found(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    account = await channel_accounts.create(db_session, workspace.id, "Support")
    await channel_accounts.deactivate(db_session, workspace.id, account.id)

    assert await channel_accounts.find_by_token(db_session, account.ingest_token) is None


async def test_another_workspace_cannot_deactivate_your_account(
    db_session: AsyncSession,
) -> None:
    mine = await make_workspace(db_session, slug="acme")
    theirs = await make_workspace(db_session, slug="other")
    account = await channel_accounts.create(db_session, mine.id, "Support")

    with pytest.raises(NotFound):
        await channel_accounts.deactivate(db_session, theirs.id, account.id)


async def test_the_channels_route_lists_addresses(db_session, client) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    await channel_accounts.create(db_session, workspace.id, "Support")
    await db_session.commit()
    token = await sign_in(db_session, member)

    response = await client.get(
        "/api/channels/email", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["address"].endswith("@inbound.localhost")
    assert body[0]["displayName"] == "Support"


async def test_creating_a_channel_requires_admin(db_session, client) -> None:
    from relaydesk.models.membership import Role

    workspace = await make_workspace(db_session, slug="acme")
    agent = await make_member(db_session, workspace, email="sara@example.com", role=Role.agent)
    await db_session.commit()
    token = await sign_in(db_session, agent)

    response = await client.post(
        "/api/channels/email",
        json={"displayName": "Billing"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_channel_accounts.py -v`
Expected: FAIL — no module `relaydesk.services.channel_accounts`.

- [ ] **Step 3: Write the service**

```python
"""A workspace's ingest address, and the lookup that reverses it.

Address shape: ``<slug>-<token>@<inbound domain>``, with an optional
``+c<conversation number>`` tag on replies.

The token is random rather than derived: an address anyone could compute
from a workspace's name would let them post tickets into its queue.
"""

import re
import secrets
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import NotFound
from relaydesk.models.channel_account import ChannelAccount, ChannelAccountKind

TOKEN_BYTES = 6
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{12}$")
_TAG = re.compile(r"\+c(\d+)$")


def new_token() -> str:
    return secrets.token_hex(TOKEN_BYTES)


def address_for(
    account: ChannelAccount, slug: str, conversation_number: int | None = None
) -> str:
    tag = f"+c{conversation_number}" if conversation_number is not None else ""
    return f"{slug}-{account.ingest_token}{tag}@{get_settings().inbound_domain}"


def _local_part(address: str) -> str:
    return (address or "").strip().lower().split("@", 1)[0]


def token_from_address(address: str) -> str | None:
    local = _TAG.sub("", _local_part(address))
    if "-" not in local:
        return None
    # Split on the last dash: workspace slugs may contain dashes, the token
    # never does.
    candidate = local.rsplit("-", 1)[-1]
    return candidate if TOKEN_PATTERN.match(candidate) else None


def conversation_number_from_address(address: str) -> int | None:
    match = _TAG.search(_local_part(address))
    return int(match.group(1)) if match else None


async def create(
    session: AsyncSession, workspace_id: uuid.UUID, display_name: str
) -> ChannelAccount:
    account = ChannelAccount(
        workspace_id=workspace_id,
        kind=ChannelAccountKind.email,
        ingest_token=new_token(),
        display_name=display_name.strip() or "Support",
        active=True,
    )
    session.add(account)
    await session.flush()
    return account


async def list_for(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[ChannelAccount]:
    result = await session.scalars(
        sa.select(ChannelAccount)
        .where(
            ChannelAccount.workspace_id == workspace_id,
            ChannelAccount.active.is_(True),
        )
        .order_by(ChannelAccount.created_at)
    )
    return list(result)


async def deactivate(
    session: AsyncSession, workspace_id: uuid.UUID, account_id: uuid.UUID
) -> None:
    account = await session.scalar(
        sa.select(ChannelAccount).where(
            ChannelAccount.id == account_id,
            ChannelAccount.workspace_id == workspace_id,
        )
    )
    if account is None:
        raise NotFound("That channel does not exist.")
    account.active = False
    await session.flush()


async def find_by_token(session: AsyncSession, token: str) -> ChannelAccount | None:
    if not token or not TOKEN_PATTERN.match(token):
        return None
    return await session.scalar(
        sa.select(ChannelAccount).where(
            ChannelAccount.ingest_token == token,
            ChannelAccount.active.is_(True),
        )
    )
```

Deactivation is a soft delete: mail already forwarded to a removed address keeps arriving for a while, and a hard delete would turn each of those into an unrouted message.

- [ ] **Step 4: Write the router**

`apps/api/src/relaydesk/api/channels.py`, following the response-model and `Scope` conventions in `api/labels.py` (read it first — it is the shortest existing router and the closest match):

```python
class ChannelOut(<the repo's camelCase base model>):
    id: uuid.UUID
    address: str
    display_name: str
    active: bool
    created_at: datetime


class ChannelCreate(<same base>):
    display_name: str = Field(min_length=1, max_length=160)


@router.get("/email", response_model=list[ChannelOut])
async def list_email_channels(scope: Scope, session: DbSession) -> list[ChannelOut]: ...


@router.post("/email", response_model=ChannelOut, status_code=201)
async def create_email_channel(
    payload: ChannelCreate, scope: Scope, session: DbSession
) -> ChannelOut:
    scope.require_admin()
    ...


@router.delete("/email/{channel_id}", status_code=204)
async def delete_email_channel(
    channel_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    ...
```

`address` is computed with `channel_accounts.address_for(account, scope.workspace.slug)` — it is derived, never stored, so renaming a workspace cannot leave a stale address in the database.

Mount it in `api/router.py`: `api_router.include_router(channels_router, prefix="/channels", tags=["channels"])`.

- [ ] **Step 5: Give every workspace an account**

In `services/workspaces.py`, wherever a workspace is created, create a default `"Support"` channel account in the same transaction. Read the file to find the creation function; `cli.py`'s `bootstrap` and `seed` both go through it.

Then migration `0009_backfill_channel_accounts.py` for workspaces that already exist:

```python
def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM workspaces")).fetchall()
    for (workspace_id,) in rows:
        exists = connection.execute(
            sa.text("SELECT 1 FROM channel_accounts WHERE workspace_id = :id"),
            {"id": workspace_id},
        ).first()
        if exists:
            continue
        connection.execute(
            sa.text(
                "INSERT INTO channel_accounts "
                "(id, workspace_id, kind, ingest_token, display_name, active, "
                " created_at, updated_at) "
                "VALUES (:id, :ws, 'email', :token, 'Support', true, now(), now())"
            ),
            {
                "id": str(uuid.uuid4()),
                "ws": workspace_id,
                "token": secrets.token_hex(6),
            },
        )
```

`downgrade()` deletes the rows it created; a plain `DELETE FROM channel_accounts` is correct here because nothing else creates them before this migration.

- [ ] **Step 6: Run the tests, lint, commit**

Run: `docker compose exec api alembic upgrade head && docker compose exec api pytest tests/test_channel_accounts.py -v`
Expected: PASS (11 passed).

Run: `docker compose exec api pytest -q && docker compose exec api ruff check .`

```bash
git add apps/api
git commit -m "feat(api): add workspace ingest addresses and the channels route"
```

---

### Task 10: The IMAP poller

Fetch and persist. No parsing, no routing — that is Task 11's job, in a separate task, so an unparseable message fails alone instead of wedging the poll.

**Files:**
- Create: `apps/api/src/relaydesk/services/imap.py`
- Create: `apps/api/src/relaydesk/worker/tasks/inbound.py`
- Modify: `apps/api/pyproject.toml` (register the `integration` marker)
- Test: `apps/api/tests/test_imap_poll.py` (create)

**Interfaces:**
- Consumes: `RawMessage`, `PollState` (Task 3); `bridge` (Task 2); IMAP settings (Task 1).
- Produces:
  - `imap.Fetched(uid: int, raw: bytes)` — frozen dataclass
  - `imap.MailboxReader` — Protocol with `async def uidvalidity() -> int` and `async def fetch_since(last_uid: int) -> list[Fetched]`
  - `imap.AioImapReader(...)` — the real implementation
  - `imap.store_new(session, mailbox, reader) -> list[uuid.UUID]` — returns the ids of `RawMessage` rows created
  - `worker.tasks.inbound.imap_poll` — Celery task, `name="relaydesk.imap_poll"`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_imap_poll.py`. The poll logic is tested against a fake reader — the IMAP wire protocol is not what this logic is about, and a fake makes the UID bookkeeping testable exhaustively:

```python
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

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

    await imap.store_new(db_session, "INBOX", FakeReader(7, {3: _mail("a"), 9: _mail("b")}))

    state = await db_session.scalar(sa.select(PollState).where(PollState.mailbox == "INBOX"))
    assert state is not None
    assert state.last_uid == 9
    assert state.uidvalidity == 7
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_imap_poll.py -v`
Expected: FAIL — no module `relaydesk.services.imap`.

- [ ] **Step 3: Write the service**

```python
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
                digits = "".join(c for c in text.split("UIDVALIDITY")[1] if c.isdigit())
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
            body = next(
                (line for line in fetched.lines if isinstance(line, bytes) and len(line) > 2),
                None,
            )
            if body:
                results.append(Fetched(uid=uid, raw=body))
        return results
```

`UID last+1:*` is deliberate. IMAP returns the highest UID when the range start exceeds it, so this never returns an empty set on an idle mailbox — hence the `u > last_uid` filter, which is what actually prevents re-fetching the last message on every poll.

- [ ] **Step 4: Write the task**

`apps/api/src/relaydesk/worker/tasks/inbound.py`:

```python
from relaydesk.config import get_settings
from relaydesk.services import imap
from relaydesk.worker import bridge
from relaydesk.worker.app import app


async def _poll() -> int:
    settings = get_settings()
    mailbox = settings.imap_mailbox
    async with imap.AioImapReader(mailbox) as reader:
        async with bridge.session_scope() as session:
            created = await imap.store_new(session, mailbox, reader)

    for raw_message_id in created:
        ingest_message.delay(str(raw_message_id))
    return len(created)


@app.task(name="relaydesk.imap_poll")
def imap_poll() -> int:
    return bridge.run(_poll())
```

`ingest_message` is written in Task 11. Until then, define it as a stub in this same module that logs and returns, so the poller is independently runnable and testable:

```python
@app.task(name="relaydesk.ingest_message")
def ingest_message(raw_message_id: str) -> None:
    """Replaced in Task 11. Until then the poller can be exercised on its
    own without messages disappearing into an unregistered task name."""
    logging.getLogger(__name__).info("ingest pending for %s", raw_message_id)
```

- [ ] **Step 5: Register the integration marker and add one live test**

In `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
markers = ["integration: exercises a live service in docker-compose"]
```

Add to `tests/test_imap_poll.py`:

```python
@pytest.mark.integration
async def test_a_real_round_trip_through_greenmail(db_session: AsyncSession) -> None:
    """The fake reader proves the bookkeeping; this proves the wire protocol.
    Requires the compose stack, so it is marked and excluded by default."""
    from relaydesk.services import mailer

    await mailer.send(
        to=f"{get_settings().imap_username}@localhost",
        subject="Round trip",
        text_body="hello",
    )
    async with imap.AioImapReader("INBOX") as reader:
        created = await imap.store_new(db_session, "INBOX", reader)

    assert created
```

Run the default suite with `-m "not integration"` from now on, and note it in the README's testing section.

- [ ] **Step 6: Run the tests**

Run: `docker compose exec api pytest tests/test_imap_poll.py -v -m "not integration"`
Expected: PASS (5 passed, 1 deselected).

Run: `docker compose exec api pytest tests/test_imap_poll.py -v -m integration`
Expected: PASS (1 passed) with the stack up.

- [ ] **Step 7: Lint and commit**

Run: `docker compose exec api pytest -q -m "not integration" && docker compose exec api ruff check .`

```bash
git add apps/api
git commit -m "feat(api): poll IMAP into a raw message landing zone"
```

---
