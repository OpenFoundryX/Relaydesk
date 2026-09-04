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
