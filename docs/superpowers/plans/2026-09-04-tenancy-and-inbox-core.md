# Tenancy & Inbox Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Next.js console's in-memory mock stores with a multi-tenant FastAPI + Postgres backend covering workspaces, users, sessions, team invites, and the full conversation/message/label/activity inbox core.

**Architecture:** Routers handle HTTP, services hold domain logic and never import FastAPI, models handle persistence. Every service function takes an `AsyncSession` and an explicit `workspace_id`. The web app talks to the API only from the server, forwarding an opaque session token as a bearer header, and each mock getter's body is replaced by a fetch so no page or component changes shape.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, Pydantic v2 + pydantic-settings, argon2-cffi, pytest + pytest-asyncio + httpx ASGITransport, Postgres 16. Web: Next.js 16 App Router, React 19, TypeScript 5.8.

**Spec:** `docs/superpowers/specs/2026-09-04-tenancy-and-inbox-core-design.md`

## Global Constraints

- Python `>=3.12,<3.13`. Ruff `target-version = "py312"`, `line-length = 88`, lint rules `["E", "F", "I", "UP", "B"]`. All code must pass `ruff check .`.
- SQLAlchemy 2.0 declarative style: `Mapped[...]` / `mapped_column(...)`. No legacy `Column()` declarations.
- All enums use `sa.Enum(..., native_enum=False)` so they compile to `VARCHAR + CHECK`.
- Python enums subclass `enum.StrEnum` (never `(str, enum.Enum)`, which ruff `UP042` rejects). SQLAlchemy persists the member *name*, and every enum here has `name == value`, so the stored values and `CHECK` constraints are identical either way.
- Every domain table carries `workspace_id` directly, including `messages` and `drafts`.
- Cross-workspace identifiers return **404, never 403**.
- All JSON is camelCase, produced by `alias_generator=to_camel` with `populate_by_name=True`. Python identifiers stay snake_case.
- Services raise `AppError` subclasses and never import `fastapi`.
- Error responses are `{"error": {"code": "...", "message": "..."}}` — for framework errors too. Task 3 registered handlers for `AppError`, `RequestValidationError`, and Starlette's `HTTPException`, so validation failures and unmatched routes use the same envelope. Do not reintroduce FastAPI's default `{"detail": ...}` shape.
- The API is mounted at `/api` (see `main.py`); paths in this plan are written relative to that prefix.
- Web: TypeScript `strict` is on. Imports use the `@/*` path alias. Files under `lib/api/` are server-only.
- Tests run against real Postgres, never SQLite.
- Commit after every task. Conventional Commit prefixes (`feat:`, `test:`, `refactor:`, `docs:`, `chore:`).

## File Structure

**API — created**

| File | Responsibility |
|---|---|
| `src/relaydesk/db/base.py` | `Base`, `UUIDMixin`, `TimestampMixin` |
| `src/relaydesk/errors.py` | `AppError` hierarchy |
| `src/relaydesk/models/__init__.py` | Imports every model so Alembic metadata is complete |
| `src/relaydesk/models/workspace.py` | `Workspace` |
| `src/relaydesk/models/user.py` | `User`, `UserIdentity` |
| `src/relaydesk/models/membership.py` | `Membership`, `Role`, `MembershipStatus` |
| `src/relaydesk/models/session.py` | `Session` |
| `src/relaydesk/models/invite.py` | `Invite` |
| `src/relaydesk/models/contact.py` | `Contact` |
| `src/relaydesk/models/conversation.py` | `Conversation`, `ConversationLabel`, and the four inbox enums |
| `src/relaydesk/models/message.py` | `Message`, `MessageRole` |
| `src/relaydesk/models/label.py` | `Label`, `LabelColor` |
| `src/relaydesk/models/draft.py` | `Draft` |
| `src/relaydesk/models/activity.py` | `ActivityEvent`, `ActivityKind` |
| `src/relaydesk/models/saved_view.py` | `SavedView` |
| `src/relaydesk/security/passwords.py` | argon2id hash + verify |
| `src/relaydesk/security/tokens.py` | Opaque token generation + SHA-256 hashing |
| `src/relaydesk/security/oauth_google.py` | Google code exchange + userinfo |
| `src/relaydesk/services/auth.py` | Credential check, session lifecycle, throttling |
| `src/relaydesk/services/workspaces.py` | Workspace reads, setup tasks |
| `src/relaydesk/services/team.py` | Members, invites, acceptance |
| `src/relaydesk/services/conversations.py` | Inbox reads and every mutation |
| `src/relaydesk/services/labels.py` | Label reads and creation |
| `src/relaydesk/services/views.py` | Saved view reads and filter application |
| `src/relaydesk/schemas/*.py` | Pydantic request/response models, one module per router |
| `src/relaydesk/api/deps.py` | `get_session`, `current_user`, `workspace_scope` |
| `src/relaydesk/api/{auth,workspace,team,conversations,labels,views}.py` | Routers |
| `src/relaydesk/cli.py` | `seed` and `bootstrap` commands |
| `tests/conftest.py` | Test database, migrations, per-test transaction, HTTP client, factories |

**API — modified:** `pyproject.toml`, `config.py`, `main.py`, `db/session.py`, `api/router.py`, `migrations/env.py`, `Dockerfile`.

**Web — created:** `lib/types.ts`, `lib/api/client.ts`, `lib/api/{conversations,workspace,team,labels,views}.ts`, `lib/session.ts`, `lib/session-cookie.ts`, `middleware.ts`, `app/signed-out/route.ts`, `app/(auth)/login/google/callback/route.ts`.

**Web — modified:** `lib/mock/types.ts` (becomes a re-export), `lib/mock/workspace.ts` (reduced to `getPortalSettings`), `lib/mock/settings.ts` (`getTeam` removed), `app/(auth)/login/{page,actions}.tsx`, `app/(console)/layout.tsx`, `app/(console)/conversations/{page.tsx,actions.ts,[id]/page.tsx}`, `app/(console)/settings/{layout,team/page,account/page,billing/page}.tsx`, `app/(console)/user-portal/layout.tsx`, `app/(console)/{analytics,knowledge-base}/page.tsx`, `components/console/sidebar.tsx`, `components/inbox/pickers.tsx`.

**Web — deleted:** `lib/mock/conversations.ts`.

---

### Task 1: Database foundation, first model, and test harness

Establishes the declarative base, wires Alembic to real metadata, creates the `workspaces` table, and stands up a test harness that runs migrations against real Postgres. Everything after this depends on the harness, so it ships with the first model rather than alone.

**Files:**
- Create: `apps/api/src/relaydesk/db/base.py`
- Create: `apps/api/src/relaydesk/models/__init__.py`
- Create: `apps/api/src/relaydesk/models/workspace.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/migrations/versions/0001_workspaces.py` (generated)
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/src/relaydesk/db/session.py`
- Modify: `apps/api/migrations/env.py`
- Test: `apps/api/tests/test_workspace_model.py`

**Interfaces:**
- Produces: `Base`, `UUIDMixin` (`id: Mapped[uuid.UUID]`), `TimestampMixin` (`created_at`, `updated_at`); `Workspace(name, slug, monogram, timezone, conversation_seq, plan, trial_days_left, tickets_this_period, projected_tickets)`; `get_session() -> AsyncIterator[AsyncSession]`; pytest fixtures `db_session: AsyncSession`, `client: AsyncClient`.

- [ ] **Step 1: Add dependencies**

In `apps/api/pyproject.toml`, add to `dependencies`:

```toml
    "argon2-cffi>=23.1,<26",
    "email-validator>=2.2,<3",
    "httpx>=0.28,<1",
```

Move `httpx` out of `[dependency-groups].dev` (it is now a runtime dependency) and add to that group:

```toml
    "pytest-asyncio>=0.25,<1",
```

Add to the `[tool.pytest.ini_options]` block:

```toml
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

Both loop scopes are required. With only the fixture scope set, tests default to
a function-scoped loop and fail against the session-scoped engine with "attached
to a different loop".

Then run `uv lock` so `uv.lock` matches.

- [ ] **Step 2: Write the declarative base**

Create `apps/api/src/relaydesk/db/base.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every Relaydesk model."""


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

- [ ] **Step 3: Write the Workspace model**

Create `apps/api/src/relaydesk/models/workspace.py`:

```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Workspace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    monogram: Mapped[str] = mapped_column(String(4), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    conversation_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Placeholder billing fields the console reads. Slice 7 replaces the source.
    plan: Mapped[str] = mapped_column(String(32), default="Starter", nullable=False)
    trial_days_left: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tickets_this_period: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    projected_tickets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

Create `apps/api/src/relaydesk/models/__init__.py`:

```python
"""SQLAlchemy models.

Every model must be imported here so ``Base.metadata`` is complete when
Alembic autogenerates a migration.
"""

from relaydesk.db.base import Base
from relaydesk.models.workspace import Workspace

__all__ = ["Base", "Workspace"]
```

- [ ] **Step 4: Add the session dependency**

Append to `apps/api/src/relaydesk/db/session.py`:

```python
from collections.abc import AsyncIterator


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
```

Move the `AsyncIterator` import to the top of the file with the other imports so ruff's `I` rule passes.

- [ ] **Step 5: Wire Alembic to real metadata**

In `apps/api/migrations/env.py`, replace `target_metadata = None` with:

```python
from relaydesk.models import Base  # noqa: F401  (imports every model)

target_metadata = Base.metadata
```

and replace the URL line so tests can override it:

```python
config.set_main_option(
    "sqlalchemy.url",
    config.attributes.get("sqlalchemy_url") or get_settings().database_url,
)
```

This override matters: without it, `env.py` always points at the development database and the test suite would migrate the wrong one.

- [ ] **Step 6: Write the test harness**

Create `apps/api/tests/conftest.py`:

```python
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import asyncpg
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from relaydesk.config import get_settings
from relaydesk.db.session import get_session
from relaydesk.main import app

API_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE = "relaydesk_test"


def _test_url() -> str:
    url = sa.engine.make_url(get_settings().database_url)
    # str(URL) masks the password as "***"; render it for real or asyncpg
    # rejects the connection.
    return url.set(database=TEST_DATABASE).render_as_string(hide_password=False)


async def _recreate_database() -> None:
    url = sa.engine.make_url(get_settings().database_url)
    connection = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port or 5432,
        database="postgres",
    )
    try:
        await connection.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)')
        await connection.execute(f'CREATE DATABASE "{TEST_DATABASE}"')
    finally:
        await connection.close()


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[str]:
    """Drop, recreate, and migrate the test database once per session.

    Running Alembic rather than ``create_all`` means the migrations
    themselves are what the suite exercises.
    """
    import asyncio

    asyncio.run(_recreate_database())

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.attributes["sqlalchemy_url"] = _test_url()
    command.upgrade(config, "head")

    yield _test_url()


@pytest.fixture(scope="session")
async def engine(migrated_database: str):
    engine = create_async_engine(migrated_database, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    """A session whose writes are rolled back after each test.

    ``join_transaction_mode="create_savepoint"`` lets service code call
    ``commit()`` normally while the outer transaction still rolls back.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
```

- [ ] **Step 7: Write the failing test**

Create `apps/api/tests/test_workspace_model.py`:

```python
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import Workspace


async def test_workspace_persists_with_defaults(db_session: AsyncSession) -> None:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    db_session.add(workspace)
    await db_session.commit()

    stored = await db_session.scalar(sa.select(Workspace).where(Workspace.slug == "chronon"))

    assert stored is not None
    assert stored.id is not None
    assert stored.conversation_seq == 0
    assert stored.timezone == "UTC"
    assert stored.created_at is not None


async def test_workspace_slug_is_unique(db_session: AsyncSession) -> None:
    db_session.add(Workspace(name="A", slug="dup", monogram="A"))
    await db_session.commit()

    db_session.add(Workspace(name="B", slug="dup", monogram="B"))
    try:
        await db_session.commit()
    except sa.exc.IntegrityError:
        return
    raise AssertionError("expected a unique-constraint violation on workspaces.slug")
```

- [ ] **Step 8: Run the tests to verify they fail**

Run: `docker compose exec api pytest tests/test_workspace_model.py -v`
Expected: FAIL — the `workspaces` table does not exist yet, because no migration has been generated.

- [ ] **Step 9: Generate and review the migration**

Run: `docker compose exec api alembic revision --autogenerate -m "workspaces"`

Rename the generated file to `apps/api/migrations/versions/0001_workspaces.py` and set `revision = "0001"`, `down_revision = None`. Read the generated `upgrade()` and confirm it creates `workspaces` with the unique constraint on `slug` — autogenerate output is a draft, not an answer, and reviewing it here is what keeps later migrations trustworthy.

- [ ] **Step 10: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/ -v`
Expected: PASS, including the two pre-existing tests in `test_main.py`.

- [ ] **Step 11: Lint and commit**

```bash
docker compose exec api ruff check .
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/src/relaydesk apps/api/migrations apps/api/tests
git commit -m "feat(api): add declarative base, workspace model, and test harness"
```

---

### Task 2: Users, memberships, and credential verification

Adds the identity tables and the pure-domain half of authentication: verifying a password and enforcing lockout. No HTTP yet, so this task is entirely service-level.

**Files:**
- Create: `apps/api/src/relaydesk/models/user.py`
- Create: `apps/api/src/relaydesk/models/membership.py`
- Create: `apps/api/src/relaydesk/security/passwords.py`
- Create: `apps/api/src/relaydesk/errors.py`
- Create: `apps/api/src/relaydesk/services/auth.py`
- Create: `apps/api/migrations/versions/0002_identity.py` (generated)
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Modify: `apps/api/src/relaydesk/config.py`
- Test: `apps/api/tests/test_auth_service.py`

**Interfaces:**
- Consumes: `Base`, `UUIDMixin`, `TimestampMixin`, `Workspace`, `db_session` fixture.
- Produces: `User`, `UserIdentity`, `Membership`, `Role`, `MembershipStatus`; `hash_password(raw) -> str`, `verify_password(raw, hashed) -> bool`; `AppError`, `NotFound`, `Unauthorized`, `Forbidden`, `Conflict`, `Invalid`; `services.auth.authenticate(session, email, password) -> User`.

- [ ] **Step 1: Write the error hierarchy**

Create `apps/api/src/relaydesk/errors.py`:

```python
class AppError(Exception):
    """Base for domain errors. Services raise these; routers map them."""

    code = "error"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Invalid(AppError):
    code = "invalid"
    status_code = 422


class Unauthorized(AppError):
    code = "unauthorized"
    status_code = 401


class Forbidden(AppError):
    code = "forbidden"
    status_code = 403


class NotFound(AppError):
    code = "not_found"
    status_code = 404


class Conflict(AppError):
    code = "conflict"
    status_code = 409
```

- [ ] **Step 2: Write password hashing**

Create `apps/api/src/relaydesk/security/passwords.py`:

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_hasher = PasswordHasher()


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
```

Create an empty `apps/api/src/relaydesk/security/__init__.py` containing `"""Password, token, and OAuth primitives."""` and an empty `apps/api/src/relaydesk/services/__init__.py` containing `"""Domain services."""`.

- [ ] **Step 3: Write the identity models**

Create `apps/api/src/relaydesk/models/user.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monogram: Mapped[str] = mapped_column(String(4), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserIdentity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_account_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
```

`CITEXT` requires the extension. Add this as the first statement of the Task 2 migration's `upgrade()`:

```python
op.execute("CREATE EXTENSION IF NOT EXISTS citext")
```

Create `apps/api/src/relaydesk/models/membership.py`:

```python
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Role(enum.StrEnum):
    admin = "admin"
    agent = "agent"


class MembershipStatus(enum.StrEnum):
    active = "active"
    invited = "invited"


class Membership(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=16), default=Role.agent, nullable=False
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, native_enum=False, length=16),
        default=MembershipStatus.active,
        nullable=False,
    )
```

Update `apps/api/src/relaydesk/models/__init__.py` to import and export `User`, `UserIdentity`, `Membership`, `Role`, `MembershipStatus` alongside `Workspace`.

- [ ] **Step 4: Add auth settings**

In `apps/api/src/relaydesk/config.py`, add these fields to `Settings`:

```python
    session_ttl_days: int = 30
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    google_client_id: str = ""
    google_client_secret: str = ""
    web_url: str = "http://localhost:3000"
```

Add the matching keys to `.env.example` and to the `api` service's `environment:` block in `docker-compose.yml`:

```
SESSION_TTL_DAYS=30
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
WEB_URL=http://localhost:3000
```

- [ ] **Step 5: Write the failing test**

Create `apps/api/tests/test_auth_service.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Unauthorized
from relaydesk.models import User
from relaydesk.security.passwords import hash_password
from relaydesk.services import auth


async def make_user(session: AsyncSession, password: str | None = "correct-horse") -> User:
    user = User(
        email="agent@relaydesk.dev",
        name="Sara Duval",
        monogram="SD",
        password_hash=hash_password(password) if password else None,
    )
    session.add(user)
    await session.commit()
    return user


async def test_authenticate_returns_user_for_correct_password(db_session: AsyncSession) -> None:
    user = await make_user(db_session)

    result = await auth.authenticate(db_session, "agent@relaydesk.dev", "correct-horse")

    assert result.id == user.id
    assert result.failed_login_count == 0


async def test_authenticate_is_case_insensitive_on_email(db_session: AsyncSession) -> None:
    await make_user(db_session)

    result = await auth.authenticate(db_session, "AGENT@Relaydesk.dev", "correct-horse")

    assert result.email == "agent@relaydesk.dev"


async def test_wrong_password_raises_and_increments_the_counter(db_session: AsyncSession) -> None:
    user = await make_user(db_session)

    with pytest.raises(Unauthorized):
        await auth.authenticate(db_session, "agent@relaydesk.dev", "wrong")

    await db_session.refresh(user)
    assert user.failed_login_count == 1


async def test_unknown_email_raises_the_same_error(db_session: AsyncSession) -> None:
    with pytest.raises(Unauthorized):
        await auth.authenticate(db_session, "nobody@relaydesk.dev", "whatever")


async def test_password_only_account_without_hash_cannot_log_in(db_session: AsyncSession) -> None:
    await make_user(db_session, password=None)

    with pytest.raises(Unauthorized):
        await auth.authenticate(db_session, "agent@relaydesk.dev", "anything")


async def test_lockout_after_max_attempts(db_session: AsyncSession) -> None:
    user = await make_user(db_session)

    for _ in range(5):
        with pytest.raises(Unauthorized):
            await auth.authenticate(db_session, "agent@relaydesk.dev", "wrong")

    await db_session.refresh(user)
    assert user.locked_until is not None

    # Even the correct password is refused while the lockout stands.
    with pytest.raises(Unauthorized):
        await auth.authenticate(db_session, "agent@relaydesk.dev", "correct-horse")


async def test_expired_lockout_allows_login_and_resets_counter(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    user.failed_login_count = 5
    user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    result = await auth.authenticate(db_session, "agent@relaydesk.dev", "correct-horse")

    assert result.failed_login_count == 0
    assert result.locked_until is None
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_auth_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.services.auth'`.

- [ ] **Step 7: Implement the service**

Create `apps/api/src/relaydesk/services/auth.py`:

```python
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Unauthorized
from relaydesk.models import User
from relaydesk.security.passwords import verify_password

BAD_CREDENTIALS = "Email or password is incorrect."


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, enforcing an attempt lockout.

    Every failure raises the same message, so the endpoint cannot be used to
    discover which addresses have accounts.
    """
    settings = get_settings()
    user = await session.scalar(sa.select(User).where(User.email == email))
    if user is None:
        raise Unauthorized(BAD_CREDENTIALS)

    now = datetime.now(UTC)
    if user.locked_until is not None:
        if user.locked_until > now:
            raise Unauthorized(BAD_CREDENTIALS)
        user.failed_login_count = 0
        user.locked_until = None

    if user.password_hash is None or not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
        await session.commit()
        raise Unauthorized(BAD_CREDENTIALS)

    user.failed_login_count = 0
    user.locked_until = None
    await session.commit()
    return user
```

- [ ] **Step 8: Generate the migration**

Run: `docker compose exec api alembic revision --autogenerate -m "identity"`

Rename to `apps/api/migrations/versions/0002_identity.py`, set `revision = "0002"` and `down_revision = "0001"`, and add `op.execute("CREATE EXTENSION IF NOT EXISTS citext")` as the first line of `upgrade()`. Autogenerate does not know about extensions, so this line will be missing and the migration will fail without it.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/ -v`
Expected: PASS — all seven auth tests plus the earlier ones.

- [ ] **Step 10: Lint and commit**

```bash
docker compose exec api ruff check .
git add apps/api
git commit -m "feat(api): add users, memberships, and credential verification"
```

---

### Task 3: Sessions and the auth endpoints

Adds session tokens, the request dependencies every later router uses, the error handlers, and the first three HTTP endpoints.

**Files:**
- Create: `apps/api/src/relaydesk/models/session.py`
- Create: `apps/api/src/relaydesk/security/tokens.py`
- Create: `apps/api/src/relaydesk/schemas/base.py`
- Create: `apps/api/src/relaydesk/schemas/auth.py`
- Create: `apps/api/src/relaydesk/api/deps.py`
- Create: `apps/api/src/relaydesk/api/auth.py`
- Create: `apps/api/migrations/versions/0003_sessions.py` (generated)
- Modify: `apps/api/src/relaydesk/services/auth.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Modify: `apps/api/src/relaydesk/main.py`
- Test: `apps/api/tests/test_auth_api.py`

**Interfaces:**
- Consumes: `authenticate`, `User`, `Membership`, `Workspace`, `AppError`.
- Produces: `Session` model; `generate_token() -> str`, `hash_token(token) -> str`; `CamelModel` base schema; `services.auth.create_session(session, user, user_agent, ip) -> tuple[str, Session]`, `resolve_session(session, token) -> User`, `revoke_session(session, token) -> None`; deps `get_db`, `current_user`, `WorkspaceScope(user, membership, workspace)`, `workspace_scope`.

- [ ] **Step 1: Write token helpers**

Create `apps/api/src/relaydesk/security/tokens.py`:

```python
import hashlib
import secrets


def generate_token() -> str:
    """A 256-bit URL-safe token. Only its hash is ever stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
```

- [ ] **Step 2: Write the Session model**

Create `apps/api/src/relaydesk/models/session.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Session(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Export it from `models/__init__.py`.

- [ ] **Step 3: Write the camelCase schema base**

Create `apps/api/src/relaydesk/schemas/base.py`:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Every request and response schema inherits this.

    Python stays snake_case; the wire format is camelCase, matching the
    console's TypeScript types field for field.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
```

Create `apps/api/src/relaydesk/schemas/__init__.py` containing `"""Request and response schemas."""`.

- [ ] **Step 4: Write the failing test**

Create `apps/api/tests/test_auth_api.py`:

```python
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import Membership, MembershipStatus, Role, Session, User, Workspace
from relaydesk.security.passwords import hash_password


async def seed_member(session: AsyncSession) -> tuple[Workspace, User]:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    user = User(
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        monogram="NP",
        password_hash=hash_password("correct-horse"),
    )
    session.add_all([workspace, user])
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await session.commit()
    return workspace, user


async def test_login_returns_a_token(client: AsyncClient, db_session: AsyncSession) -> None:
    await seed_member(db_session)

    response = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["expiresAt"]


async def test_login_stores_only_the_token_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)

    response = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )
    token = response.json()["token"]

    stored = await db_session.scalars(sa.select(Session))
    hashes = [row.token_hash for row in stored]
    assert hashes
    assert token not in hashes


async def test_login_with_a_bad_password_returns_the_error_envelope(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)

    response = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "nope"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "unauthorized", "message": "Email or password is incorrect."}
    }


async def test_me_returns_user_workspace_and_membership(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)
    login = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )
    token = login.json()["token"]

    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["name"] == "Nilesh Pant"
    assert body["user"]["monogram"] == "NP"
    assert body["workspace"]["name"] == "Chronon"
    assert body["membership"]["role"] == "admin"


async def test_me_without_a_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_logout_invalidates_the_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)
    login = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert (await client.post("/api/auth/logout", headers=headers)).status_code == 204
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401


async def test_a_user_without_an_active_membership_cannot_log_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = User(
        email="orphan@relaydesk.dev",
        name="Orphan",
        monogram="OR",
        password_hash=hash_password("correct-horse"),
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "orphan@relaydesk.dev", "password": "correct-horse"},
    )

    assert response.status_code == 401
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_auth_api.py -v`
Expected: FAIL — every request 404s, because no auth router is mounted.

- [ ] **Step 6: Extend the auth service with session lifecycle**

Append to `apps/api/src/relaydesk/services/auth.py`:

```python
from relaydesk.models import Membership, MembershipStatus, Session
from relaydesk.security.tokens import generate_token, hash_token

LAST_SEEN_INTERVAL = timedelta(hours=1)


async def active_membership(session: AsyncSession, user: User) -> Membership:
    membership = await session.scalar(
        sa.select(Membership).where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.active,
        )
    )
    if membership is None:
        raise Unauthorized(BAD_CREDENTIALS)
    return membership


async def create_session(
    session: AsyncSession,
    user: User,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, Session]:
    """Return the plaintext token and the stored row. Only the hash persists."""
    settings = get_settings()
    now = datetime.now(UTC)
    token = generate_token()
    row = Session(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=settings.session_ttl_days),
        last_seen_at=now,
        user_agent=user_agent,
        ip=ip,
    )
    session.add(row)
    await session.commit()
    return token, row


async def resolve_session(session: AsyncSession, token: str) -> User:
    now = datetime.now(UTC)
    row = await session.scalar(
        sa.select(Session).where(Session.token_hash == hash_token(token))
    )
    if row is None or row.expires_at <= now:
        raise Unauthorized("Session is invalid or has expired.")

    if now - row.last_seen_at > LAST_SEEN_INTERVAL:
        row.last_seen_at = now
        await session.commit()

    user = await session.get(User, row.user_id)
    if user is None:
        raise Unauthorized("Session is invalid or has expired.")
    return user


async def revoke_session(session: AsyncSession, token: str) -> None:
    await session.execute(
        sa.delete(Session).where(Session.token_hash == hash_token(token))
    )
    await session.commit()
```

Move the new imports to the top of the file so ruff's import rule passes.

- [ ] **Step 7: Write the request dependencies**

Create `apps/api/src/relaydesk/api/deps.py`:

```python
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.db.session import get_session
from relaydesk.errors import Unauthorized
from relaydesk.models import Membership, Role, User, Workspace
from relaydesk.services import auth

DbSession = Annotated[AsyncSession, Depends(get_session)]


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Authentication required.")
    return authorization[7:].strip()


async def current_user(
    session: DbSession, token: Annotated[str, Depends(bearer_token)]
) -> User:
    return await auth.resolve_session(session, token)


@dataclass(slots=True)
class WorkspaceScope:
    """Resolved tenant context. Every workspace-scoped route depends on this."""

    user: User
    membership: Membership
    workspace: Workspace

    @property
    def workspace_id(self):
        return self.workspace.id

    def require_admin(self) -> None:
        from relaydesk.errors import Forbidden

        if self.membership.role is not Role.admin:
            raise Forbidden("This action requires an admin.")


async def workspace_scope(
    session: DbSession, user: Annotated[User, Depends(current_user)]
) -> WorkspaceScope:
    membership = await auth.active_membership(session, user)
    workspace = await session.get(Workspace, membership.workspace_id)
    if workspace is None:
        raise Unauthorized("Workspace is unavailable.")
    return WorkspaceScope(user=user, membership=membership, workspace=workspace)


Scope = Annotated[WorkspaceScope, Depends(workspace_scope)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
```

- [ ] **Step 8: Write the auth schemas and router**

Create `apps/api/src/relaydesk/schemas/auth.py`:

```python
from datetime import datetime

from pydantic import EmailStr

from relaydesk.schemas.base import CamelModel


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class TokenResponse(CamelModel):
    token: str
    expires_at: datetime


class UserOut(CamelModel):
    id: str
    name: str
    email: str
    monogram: str
    time_zone: str


class WorkspaceOut(CamelModel):
    id: str
    name: str
    monogram: str
    plan: str
    trial_days_left: int
    seats: int
    tickets_this_period: int
    projected_tickets: int


class MembershipOut(CamelModel):
    role: str


class MeResponse(CamelModel):
    user: UserOut
    workspace: WorkspaceOut
    membership: MembershipOut
```

`time_zone` (rather than `timezone`) is deliberate: it serializes to `timeZone`, which is what `currentUser` in `lib/mock/workspace.ts` exposes.

Create `apps/api/src/relaydesk/api/auth.py`:

```python
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, Response, status

from relaydesk.api.deps import DbSession, Scope, bearer_token, client_ip
from relaydesk.models import Membership, MembershipStatus
from relaydesk.schemas.auth import (
    LoginRequest,
    MembershipOut,
    MeResponse,
    TokenResponse,
    UserOut,
    WorkspaceOut,
)
from relaydesk.services import auth

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: DbSession,
    ip: Annotated[str | None, Depends(client_ip)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    user = await auth.authenticate(session, payload.email, payload.password)
    await auth.active_membership(session, user)
    token, row = await auth.create_session(session, user, user_agent=user_agent, ip=ip)
    return TokenResponse(token=token, expires_at=row.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session: DbSession, token: Annotated[str, Depends(bearer_token)]
) -> Response:
    await auth.revoke_session(session, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(scope: Scope, session: DbSession) -> MeResponse:
    seats = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Membership)
        .where(
            Membership.workspace_id == scope.workspace_id,
            Membership.status == MembershipStatus.active,
        )
    )
    return MeResponse(
        user=UserOut(
            id=str(scope.user.id),
            name=scope.user.name,
            email=scope.user.email,
            monogram=scope.user.monogram,
            time_zone=scope.user.timezone,
        ),
        workspace=WorkspaceOut(
            id=str(scope.workspace.id),
            name=scope.workspace.name,
            monogram=scope.workspace.monogram,
            plan=scope.workspace.plan,
            trial_days_left=scope.workspace.trial_days_left,
            seats=seats or 0,
            tickets_this_period=scope.workspace.tickets_this_period,
            projected_tickets=scope.workspace.projected_tickets,
        ),
        membership=MembershipOut(role=scope.membership.role.value),
    )
```

- [ ] **Step 9: Mount the router and register error handlers**

In `apps/api/src/relaydesk/api/router.py`, add:

```python
from relaydesk.api.auth import router as auth_router

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
```

In `apps/api/src/relaydesk/main.py`, add after the middleware block:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

from relaydesk.errors import AppError


@app.exception_handler(AppError)
async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )
```

- [ ] **Step 10: Generate the migration and run the tests**

```bash
docker compose exec api alembic revision --autogenerate -m "sessions"
```

Rename to `0003_sessions.py`, set `revision = "0003"`, `down_revision = "0002"`.

Run: `docker compose exec api pytest tests/ -v`
Expected: PASS — all seven auth API tests.

- [ ] **Step 11: Lint and commit**

```bash
docker compose exec api ruff check .
git add apps/api
git commit -m "feat(api): add sessions and the auth endpoints"
```

---

> **Note on the web tasks (4, 6, 8, 9, 10).** The web app has no test runner and
> this slice does not add one — that is its own decision, not a rider on this
> plan. Web tasks are therefore verified by `pnpm lint`, `pnpm build`, and the
> explicit browser check written into each task. Do not skip the browser check;
> it is the only thing standing in for a test there.

---

### Task 4: Web session plumbing and real login

The first end-to-end vertical: a real credential exchange, a real cookie, and a console that redirects when you are not signed in. Placed before the remaining API work so the seam is proven early rather than assumed nine tasks later.

**Files:**
- Create: `apps/web/lib/types.ts` (moved from `lib/mock/types.ts`)
- Create: `apps/web/lib/session.ts`
- Create: `apps/web/lib/api/client.ts`
- Create: `apps/web/lib/api/workspace.ts`
- Create: `apps/web/middleware.ts`
- Modify: `apps/web/lib/mock/types.ts` (reduced to a re-export)
- Modify: `apps/web/lib/mock/workspace.ts` (reduced to `getPortalSettings`)
- Modify: `apps/web/app/(auth)/login/actions.ts`
- Modify: `apps/web/app/(auth)/login/page.tsx`
- Modify: `apps/web/app/(console)/layout.tsx`
- Modify: `apps/web/app/(console)/settings/layout.tsx`
- Modify: `apps/web/app/(console)/settings/{team,account,billing}/page.tsx`
- Modify: `apps/web/app/(console)/user-portal/layout.tsx`
- Modify: `apps/web/app/(console)/{analytics,knowledge-base}/page.tsx`
- Modify: `apps/web/app/(console)/conversations/page.tsx`
- Modify: `apps/web/app/(console)/conversations/[id]/page.tsx`
- Modify: `apps/web/package.json`

**Interfaces:**
- Consumes: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`.
- Produces: `apiFetch<T>(path, init?) -> Promise<T>`, `ApiError`; `getSessionToken()`, `setSessionCookie(token, expiresAt)`, `clearSessionCookie()`; `getWorkspace() -> Promise<Workspace>`, `getCurrentUser() -> Promise<CurrentUser>`.

- [ ] **Step 1: Add the server-only guard package**

In `apps/web`, run `pnpm add server-only`. It makes a build fail loudly if a file under `lib/api/` is ever imported into a client component, which is the mistake that would leak the session token into the browser bundle.

- [ ] **Step 2: Move the type file and leave a re-export**

```bash
git mv apps/web/lib/mock/types.ts apps/web/lib/types.ts
```

Then create `apps/web/lib/mock/types.ts` with exactly:

```typescript
/** @deprecated Import from "@/lib/types". Kept so the remaining mock stores compile. */
export * from "../types";
```

Add these to `apps/web/lib/types.ts`:

```typescript
export interface SavedView {
  id: string;
  name: string;
  count: number;
}

export interface Workspace {
  id: string;
  name: string;
  monogram: string;
  plan: string;
  trialDaysLeft: number;
  seats: number;
  ticketsThisPeriod: number;
  projectedTickets: number;
}

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  monogram: string;
  timeZone: string;
}

/** Display order for statuses. A fixed enumeration, not data. */
export const statuses: ConversationStatus[] = [
  "open",
  "pending",
  "resolved",
  "on_hold",
  "ignored",
  "trash",
];
```

- [ ] **Step 3: Write the session cookie helpers**

Create `apps/web/lib/session.ts`:

```typescript
import "server-only";

import { cookies } from "next/headers";

export const SESSION_COOKIE = "rd_session";

export async function getSessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

export async function setSessionCookie(token: string, expiresAt: string): Promise<void> {
  const store = await cookies();
  store.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: new Date(expiresAt),
  });
}

export async function clearSessionCookie(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
}
```

- [ ] **Step 4: Write the API client**

Create `apps/web/lib/api/client.ts`:

```typescript
import "server-only";

import { redirect } from "next/navigation";

import { getSessionToken } from "@/lib/session";

const apiUrl = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Options = RequestInit & { auth?: boolean };

/**
 * Server-side fetch against the Relaydesk API.
 *
 * Attaches the session token as a bearer header. A 401 on an authenticated
 * call means the session died underneath us, so we send the user to /login
 * rather than surfacing a raw error inside a console screen.
 */
export async function apiFetch<T>(path: string, options: Options = {}): Promise<T> {
  const { auth = true, headers, ...init } = options;
  const token = auth ? await getSessionToken() : null;

  const response = await fetch(`${apiUrl}/api${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (response.status === 204) return undefined as T;

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const code = body?.error?.code ?? "error";
    const message = body?.error?.message ?? `Request failed with ${response.status}`;
    if (response.status === 401 && auth) redirect("/login");
    throw new ApiError(response.status, code, message);
  }

  return (await response.json()) as T;
}
```

`API_URL` is read first so the browser-facing `NEXT_PUBLIC_API_URL` (`http://localhost:8000`) can differ from the in-container address the Next server uses (`http://api:8000`).

Add to `docker-compose.yml` under the `web` service's `environment:`, and to `.env.example`:

```
API_URL=http://api:8000
```

- [ ] **Step 5: Write the workspace API module**

Create `apps/web/lib/api/workspace.ts`:

```typescript
import "server-only";

import { apiFetch } from "@/lib/api/client";
import type { CurrentUser, Workspace } from "@/lib/types";

interface MeResponse {
  user: CurrentUser;
  workspace: Workspace;
  membership: { role: "admin" | "agent" };
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/auth/me");
}

export async function getWorkspace(): Promise<Workspace> {
  return (await getMe()).workspace;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return (await getMe()).user;
}
```

- [ ] **Step 6: Reduce the workspace mock**

Edit `apps/web/lib/mock/workspace.ts` to delete the `workspace` constant, the `currentUser` constant, `setupTasks`, and `getSetupTasks`, keeping only the `portal` constant and `getPortalSettings`. Update its import line to `import type { PortalSettings } from "../types";`.

`getSetupTasks` moves to the API in Task 6; until then, the console layout uses a local constant (Step 8).

- [ ] **Step 7: Rewrite the login action**

Replace `apps/web/app/(auth)/login/actions.ts` with:

```typescript
"use server";

import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api/client";
import { clearSessionCookie, setSessionCookie } from "@/lib/session";

interface TokenResponse {
  token: string;
  expiresAt: string;
}

export async function signIn(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  let token: TokenResponse;
  try {
    token = await apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password }),
    });
  } catch (error) {
    if (error instanceof ApiError) redirect("/login?error=1");
    throw error;
  }

  await setSessionCookie(token.token, token.expiresAt);
  redirect("/conversations?status=open");
}

export async function signOut() {
  await apiFetch<void>("/auth/logout", { method: "POST" }).catch(() => undefined);
  await clearSessionCookie();
  redirect("/login");
}
```

`redirect` throws, so it must sit outside the `try` block or the framework's control-flow exception gets swallowed by the `catch`. That is why the token is assigned and the redirect happens after.

- [ ] **Step 8: Show the login error and await the getters**

In `apps/web/app/(auth)/login/page.tsx`, accept search params and render a message above the email form when `error` is set. Add to the component signature:

```typescript
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
```

and immediately before the email `<form action={signIn}>`:

```tsx
{error ? (
  <p
    role="alert"
    className="mb-4 rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
  >
    Email or password is incorrect.
  </p>
) : null}
```

Both `<form>` elements currently call `signIn` with no arguments; change them to `<form action={signIn}>` passing the form data — the action signature above already takes `FormData`, which is what Next passes. Leave the Google form pointing at `signIn` for now; Task 5 gives it its own
action. Until then, clicking it submits an empty email and password and lands
back on `/login?error=1` — harmless, and the error banner makes it obvious
rather than silent.

In each of the ten files listed under **Files**, replace the synchronous imports with awaited calls. For example, in `app/(console)/layout.tsx`:

```typescript
import { getCurrentUser, getWorkspace } from "@/lib/api/workspace";
```

```typescript
  const [statusCounts, draftCount, labels, workspace, currentUser] = await Promise.all([
    getStatusCounts(),
    getDraftCount(),
    getLabels(),
    getWorkspace(),
    getCurrentUser(),
  ]);
```

and add a local constant in that file for the setup checklist until Task 6 replaces it:

```typescript
/** Replaced by GET /workspace/setup-tasks in Task 6. */
const setupTasks: SetupTask[] = [];
```

Apply the same await-the-getter change in `settings/layout.tsx`, `settings/team/page.tsx`, `settings/account/page.tsx`, `settings/billing/page.tsx`, `user-portal/layout.tsx`, `analytics/page.tsx`, `knowledge-base/page.tsx`, `conversations/page.tsx`, and `conversations/[id]/page.tsx`. All of these are already `async` server components except `settings/layout.tsx` and `user-portal/layout.tsx`, which must be made `async`.

- [ ] **Step 9: Add the middleware**

Create `apps/web/middleware.ts`:

```typescript
import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session";

const PROTECTED = [
  "/conversations",
  "/analytics",
  "/knowledge-base",
  "/notifications",
  "/settings",
  "/user-portal",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const signedIn = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  if (!signedIn && PROTECTED.some((prefix) => pathname.startsWith(prefix))) {
    const login = new URL("/login", request.url);
    return NextResponse.redirect(login);
  }

  if (signedIn && pathname === "/login") {
    return NextResponse.redirect(new URL("/conversations?status=open", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/conversations/:path*", "/analytics/:path*", "/knowledge-base/:path*",
            "/notifications/:path*", "/settings/:path*", "/user-portal/:path*", "/login"],
};
```

Importing `SESSION_COOKIE` from `lib/session.ts` would pull `server-only` into the middleware runtime. Move the constant into its own file `apps/web/lib/session-cookie.ts` (`export const SESSION_COOKIE = "rd_session";`), import it from both `lib/session.ts` and `middleware.ts`, and delete the original declaration.

The middleware gate tests only whether the cookie **exists**, which on its own
creates an unrecoverable loop: a cookie that is present but no longer valid
server-side makes the console 401, `apiFetch` redirects to `/login`, and the
middleware bounces it straight back. Break it with a route handler that clears
the rejected cookie — `apiFetch`'s 401 branch redirects to `/signed-out`, not
`/login`. It must be a route handler: `apiFetch` runs during Server Component
render, where Next throws `Cookies can only be modified in a Server Action or
Route Handler`, so clearing the cookie inline is not an option.

Create `apps/web/app/signed-out/route.ts`:

```typescript
import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

export async function GET(request: NextRequest) {
  const response = NextResponse.redirect(new URL("/login?expired=1", request.url));
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
```

`/signed-out` must not appear in `PROTECTED` or in the middleware `matcher`, so it
passes through untouched. The login page reads `expired` alongside `error` and shows
a distinct message for it — someone bounced here by a revoked session has done
nothing wrong and must not be told their password was incorrect.

- [ ] **Step 10: Seed a user by hand and verify in the browser**

```bash
docker compose exec api python -c "
import asyncio
from relaydesk.db.session import async_session_factory
from relaydesk.models import Membership, MembershipStatus, Role, User, Workspace
from relaydesk.security.passwords import hash_password

async def main():
    async with async_session_factory() as s:
        w = Workspace(name='Chronon', slug='chronon', monogram='CH', plan='Starter', trial_days_left=6)
        u = User(email='nilesh@relaydesk.dev', name='Nilesh Pant', monogram='NP',
                 password_hash=hash_password('relaydesk'))
        s.add_all([w, u]); await s.flush()
        s.add(Membership(workspace_id=w.id, user_id=u.id, role=Role.admin,
                         status=MembershipStatus.active))
        await s.commit()

asyncio.run(main())
"
```

Then check, in a browser:

1. Visit `http://localhost:3000/conversations` while signed out — you are redirected to `/login`.
2. Sign in with `nilesh@relaydesk.dev` / `relaydesk` — you land on the inbox, and the top bar shows "Chronon" and "Nilesh Pant" from the database rather than the mock.
3. Sign in with the wrong password — you stay on `/login` and see the error message.
4. Delete the `rd_session` cookie in devtools and reload — you are redirected to `/login`.

- [ ] **Step 11: Lint, build, and commit**

```bash
docker compose exec web pnpm lint
docker compose exec web pnpm build
git add apps/web docker-compose.yml .env.example
git commit -m "feat(web): authenticate against the API and gate the console"
```

---

### Task 5: Google OAuth

**Files:**
- Create: `apps/api/src/relaydesk/security/oauth_google.py`
- Create: `apps/web/app/(auth)/login/google/callback/route.ts`
- Modify: `apps/api/src/relaydesk/services/auth.py`
- Modify: `apps/api/src/relaydesk/schemas/auth.py`
- Modify: `apps/api/src/relaydesk/api/auth.py`
- Modify: `apps/web/app/(auth)/login/actions.ts`
- Modify: `apps/web/app/(auth)/login/page.tsx`
- Test: `apps/api/tests/test_google_oauth.py`

**Interfaces:**
- Consumes: `create_session`, `active_membership`, `User`, `UserIdentity`.
- Produces: `exchange_code(code, redirect_uri) -> GoogleProfile(sub, email, name, email_verified)`; `services.auth.login_with_google(session, profile) -> User`; `GET /auth/google/url`, `POST /auth/google/exchange`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_google_oauth.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Unauthorized
from relaydesk.models import (
    Membership,
    MembershipStatus,
    Role,
    User,
    UserIdentity,
    Workspace,
)
from relaydesk.security.oauth_google import GoogleProfile
from relaydesk.services import auth


async def seed_member(session: AsyncSession, email: str) -> User:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    user = User(email=email, name="Nilesh Pant", monogram="NP")
    session.add_all([workspace, user])
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await session.commit()
    return user


async def test_google_login_links_an_existing_member(db_session: AsyncSession) -> None:
    user = await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123", email="nilesh@relaydesk.dev", name="Nilesh Pant", email_verified=True
    )

    result = await auth.login_with_google(db_session, profile)

    assert result.id == user.id
    identity = await db_session.scalar(
        UserIdentity.__table__.select().where(UserIdentity.provider_account_id == "google-123")
    )
    assert identity is not None


async def test_google_login_is_idempotent(db_session: AsyncSession) -> None:
    await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123", email="nilesh@relaydesk.dev", name="Nilesh Pant", email_verified=True
    )

    first = await auth.login_with_google(db_session, profile)
    second = await auth.login_with_google(db_session, profile)

    assert first.id == second.id


async def test_unknown_email_is_rejected(db_session: AsyncSession) -> None:
    profile = GoogleProfile(
        sub="google-999", email="stranger@example.com", name="Stranger", email_verified=True
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)


async def test_unverified_email_is_rejected(db_session: AsyncSession) -> None:
    await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123", email="nilesh@relaydesk.dev", name="Nilesh", email_verified=False
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)


async def test_member_without_active_membership_is_rejected(db_session: AsyncSession) -> None:
    user = User(email="orphan@relaydesk.dev", name="Orphan", monogram="OR")
    db_session.add(user)
    await db_session.commit()
    profile = GoogleProfile(
        sub="google-777", email="orphan@relaydesk.dev", name="Orphan", email_verified=True
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_google_oauth.py -v`
Expected: FAIL — `No module named 'relaydesk.security.oauth_google'`.

- [ ] **Step 3: Implement the Google client**

Create `apps/api/src/relaydesk/security/oauth_google.py`:

```python
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from relaydesk.config import get_settings
from relaydesk.errors import Unauthorized

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    sub: str
    email: str
    name: str
    email_verified: bool


def authorization_url(redirect_uri: str, state: str) -> str:
    settings = get_settings()
    if not settings.google_client_id:
        raise Unauthorized("Google sign-in is not configured.")
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return f"{AUTH_ENDPOINT}?{query}"


async def exchange_code(code: str, redirect_uri: str) -> GoogleProfile:
    """Swap an authorization code for the user's profile.

    The userinfo call is a server-to-server request over TLS, so the
    ``id_token`` needs no JWKS verification and we need no JWT library.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as http:
        token_response = await http.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code != 200:
            raise Unauthorized("Google sign-in failed.")
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise Unauthorized("Google sign-in failed.")

        profile_response = await http.get(
            USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}
        )
        if profile_response.status_code != 200:
            raise Unauthorized("Google sign-in failed.")

    body = profile_response.json()
    return GoogleProfile(
        sub=str(body["sub"]),
        email=str(body.get("email", "")),
        name=str(body.get("name") or body.get("email", "")),
        email_verified=bool(body.get("email_verified")),
    )
```

- [ ] **Step 4: Implement the service function**

Append to `apps/api/src/relaydesk/services/auth.py`:

```python
async def login_with_google(session: AsyncSession, profile: GoogleProfile) -> User:
    """Log in an existing member through Google.

    There is no self-serve signup, so an address without an active
    membership is refused rather than provisioned.
    """
    if not profile.email_verified or not profile.email:
        raise Unauthorized("Google did not confirm this email address.")

    user = await session.scalar(sa.select(User).where(User.email == profile.email))
    if user is None:
        raise Unauthorized("No Relaydesk account matches this Google address.")

    await active_membership(session, user)

    identity = await session.scalar(
        sa.select(UserIdentity).where(
            UserIdentity.provider == "google",
            UserIdentity.provider_account_id == profile.sub,
        )
    )
    if identity is None:
        session.add(
            UserIdentity(
                user_id=user.id, provider="google", provider_account_id=profile.sub
            )
        )
        await session.commit()
    return user
```

Add `UserIdentity` to the model import and `from relaydesk.security.oauth_google import GoogleProfile` at the top of the file.

- [ ] **Step 5: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_google_oauth.py -v`
Expected: PASS — five tests.

- [ ] **Step 6: Add the endpoints**

Add to `apps/api/src/relaydesk/schemas/auth.py`:

```python
class GoogleUrlResponse(CamelModel):
    url: str
    state: str


class GoogleExchangeRequest(CamelModel):
    code: str
    redirect_uri: str
```

Add to `apps/api/src/relaydesk/api/auth.py`:

```python
@router.get("/google/url", response_model=GoogleUrlResponse)
async def google_url(redirect_uri: str) -> GoogleUrlResponse:
    state = generate_token()
    return GoogleUrlResponse(url=authorization_url(redirect_uri, state), state=state)


@router.post("/google/exchange", response_model=TokenResponse)
async def google_exchange(
    payload: GoogleExchangeRequest,
    session: DbSession,
    ip: Annotated[str | None, Depends(client_ip)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    profile = await exchange_code(payload.code, payload.redirect_uri)
    user = await auth.login_with_google(session, profile)
    token, row = await auth.create_session(session, user, user_agent=user_agent, ip=ip)
    return TokenResponse(token=token, expires_at=row.expires_at)
```

with the matching imports for `authorization_url`, `exchange_code`, `generate_token`, and the two new schemas.

- [ ] **Step 7: Wire the web side**

Add to `apps/web/app/(auth)/login/actions.ts`:

```typescript
export async function signInWithGoogle() {
  const redirectUri = `${process.env.NEXT_PUBLIC_WEB_URL ?? "http://localhost:3000"}/login/google/callback`;
  const { url, state } = await apiFetch<{ url: string; state: string }>(
    `/auth/google/url?redirectUri=${encodeURIComponent(redirectUri)}`,
    { auth: false },
  );

  const store = await cookies();
  store.set("rd_oauth_state", state, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 600,
  });

  redirect(url);
}
```

with `import { cookies } from "next/headers";` at the top. Change the Google `<form action={signIn}>` in `login/page.tsx` to `<form action={signInWithGoogle}>`.

Create `apps/web/app/(auth)/login/google/callback/route.ts`:

```typescript
import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { apiFetch } from "@/lib/api/client";
import { setSessionCookie } from "@/lib/session";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");

  const store = await cookies();
  const expected = store.get("rd_oauth_state")?.value;
  store.delete("rd_oauth_state");

  // A missing or mismatched state means this callback did not originate
  // from our own redirect, so it is a CSRF attempt and gets no session.
  if (!code || !state || !expected || state !== expected) {
    return NextResponse.redirect(new URL("/login?error=1", request.url));
  }

  const redirectUri = new URL("/login/google/callback", request.url).toString();
  try {
    const token = await apiFetch<{ token: string; expiresAt: string }>(
      "/auth/google/exchange",
      {
        method: "POST",
        auth: false,
        body: JSON.stringify({ code, redirectUri }),
      },
    );
    await setSessionCookie(token.token, token.expiresAt);
  } catch {
    return NextResponse.redirect(new URL("/login?error=1", request.url));
  }

  return NextResponse.redirect(new URL("/conversations?status=open", request.url));
}
```

Add `NEXT_PUBLIC_WEB_URL=http://localhost:3000` to `.env.example` and to the `web` service environment in `docker-compose.yml`.

- [ ] **Step 8: Document the setup and verify**

Add a "Google sign-in (optional)" subsection to `README.md` under Start, stating that `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` must be set and that the authorized redirect URI to register in the Google Cloud console is `http://localhost:3000/login/google/callback`.

Verify: with no `GOOGLE_CLIENT_ID` set, clicking "Continue with Google" returns you to `/login?error=1` rather than crashing. With credentials configured, the round trip signs you in.

- [ ] **Step 9: Lint and commit**

```bash
docker compose exec api ruff check . && docker compose exec api pytest tests/ -v
docker compose exec web pnpm lint && docker compose exec web pnpm build
git add apps/api apps/web README.md .env.example docker-compose.yml
git commit -m "feat: add Google sign-in for existing members"
```

---

### Task 6: Team, invites, and setup tasks

**Files:**
- Create: `apps/api/src/relaydesk/models/invite.py`
- Create: `apps/api/src/relaydesk/services/team.py`
- Modify: `apps/api/src/relaydesk/services/workspaces.py` (created in Task 3; **append** to it)
- Create: `apps/api/src/relaydesk/schemas/team.py`
- Create: `apps/api/src/relaydesk/schemas/workspace.py`
- Create: `apps/api/src/relaydesk/api/team.py`
- Create: `apps/api/src/relaydesk/api/workspace.py`
- Create: `apps/api/migrations/versions/0004_invites.py` (generated)
- Create: `apps/web/lib/api/team.ts`
- Modify: `apps/api/src/relaydesk/api/router.py`, `models/__init__.py`
- Modify: `apps/web/lib/mock/settings.ts` (remove `getTeam` and the `teamMembers` constant)
- Modify: `apps/web/app/(console)/settings/team/page.tsx`, `app/(console)/layout.tsx`
- Test: `apps/api/tests/test_team_api.py`

**Interfaces:**
- Consumes: `Scope`, `DbSession`, `Membership`, `Role`, `MembershipStatus`, `User`, `hash_password`, `generate_token`, `hash_token`.
- Produces: `Invite` model; `services.team.list_members(session, workspace_id) -> list[TeamMember]`, `create_invite(session, workspace_id, email, role, invited_by) -> tuple[Invite, str]`, `accept_invite(session, token, name, password) -> User`; `services.workspaces.setup_tasks(session, workspace_id) -> list[SetupTask]`; `getTeam()` in `lib/api/team.ts`.

- [ ] **Step 1: Write the Invite model**

Create `apps/api/src/relaydesk/models/invite.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin
from relaydesk.models.membership import Role


class Invite(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invites"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=16), default=Role.agent, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

Export it from `models/__init__.py`, generate migration `0004_invites.py` (`revision = "0004"`, `down_revision = "0003"`).

- [ ] **Step 2: Write the failing test**

Create `apps/api/tests/test_team_api.py`:

```python
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import Membership, MembershipStatus, Role, User, Workspace
from relaydesk.security.passwords import hash_password


async def sign_in(client: AsyncClient, session: AsyncSession, role: Role = Role.admin) -> dict:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    user = User(
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        monogram="NP",
        password_hash=hash_password("relaydesk"),
    )
    session.add_all([workspace, user])
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=role,
            status=MembershipStatus.active,
        )
    )
    await session.commit()

    response = await client.post(
        "/api/auth/login", json={"email": "nilesh@relaydesk.dev", "password": "relaydesk"}
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def test_team_lists_the_signed_in_member(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    response = await client.get("/api/team", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Nilesh Pant"
    assert body[0]["role"] == "Admin"
    assert body[0]["status"] == "active"


async def test_admin_can_create_an_invite(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    response = await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "Agent"},
    )

    assert response.status_code == 201
    assert "/invite/" in response.json()["inviteUrl"]


async def test_an_invited_member_shows_as_invited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "Agent"},
    )

    body = (await client.get("/api/team", headers=headers)).json()

    invited = [entry for entry in body if entry["email"] == "sara@relaydesk.dev"]
    assert invited and invited[0]["status"] == "invited"


async def test_an_agent_cannot_create_an_invite(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session, role=Role.agent)

    response = await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "Agent"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_accepting_an_invite_creates_a_working_login(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    invite_url = (
        await client.post(
            "/api/team/invites",
            headers=headers,
            json={"email": "sara@relaydesk.dev", "role": "Agent"},
        )
    ).json()["inviteUrl"]
    token = invite_url.rsplit("/", 1)[-1]

    accepted = await client.post(
        f"/api/invites/{token}/accept",
        json={"name": "Sara Duval", "password": "another-horse"},
    )
    assert accepted.status_code == 200

    login = await client.post(
        "/api/auth/login",
        json={"email": "sara@relaydesk.dev", "password": "another-horse"},
    )
    assert login.status_code == 200


async def test_an_invite_cannot_be_accepted_twice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    invite_url = (
        await client.post(
            "/api/team/invites",
            headers=headers,
            json={"email": "sara@relaydesk.dev", "role": "Agent"},
        )
    ).json()["inviteUrl"]
    token = invite_url.rsplit("/", 1)[-1]
    payload = {"name": "Sara Duval", "password": "another-horse"}

    assert (await client.post(f"/api/invites/{token}/accept", json=payload)).status_code == 200
    second = await client.post(f"/api/invites/{token}/accept", json=payload)

    assert second.status_code == 409


async def test_setup_tasks_reflect_real_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    body = (await client.get("/api/workspace/setup-tasks", headers=headers)).json()

    by_id = {task["id"]: task for task in body}
    assert by_id["team"]["done"] is False  # only one member so far
    assert by_id["channel"]["done"] is False  # no channels until slice 2
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_team_api.py -v`
Expected: FAIL — every route 404s.

- [ ] **Step 4: Implement the team service**

Create `apps/api/src/relaydesk/services/team.py`:

```python
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, NotFound
from relaydesk.models import Invite, Membership, MembershipStatus, Role, User
from relaydesk.security.passwords import hash_password
from relaydesk.security.tokens import generate_token, hash_token

INVITE_TTL = timedelta(days=14)
ROLE_LABEL = {Role.admin: "Admin", Role.agent: "Agent"}


@dataclass(slots=True)
class TeamMember:
    id: str
    name: str
    email: str
    role: str
    status: str


def monogram_for(name: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


async def list_members(session: AsyncSession, workspace_id: uuid.UUID) -> list[TeamMember]:
    """Active members plus outstanding invites, which the console shows together."""
    rows = await session.execute(
        sa.select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(User.name)
    )
    members = [
        TeamMember(
            id=str(membership.id),
            name=user.name,
            email=user.email,
            role=ROLE_LABEL[membership.role],
            status=membership.status.value,
        )
        for membership, user in rows
    ]

    pending = await session.scalars(
        sa.select(Invite).where(
            Invite.workspace_id == workspace_id, Invite.accepted_at.is_(None)
        )
    )
    members.extend(
        TeamMember(
            id=str(invite.id),
            name=invite.email.split("@")[0],
            email=invite.email,
            role=ROLE_LABEL[invite.role],
            status="invited",
        )
        for invite in pending
    )
    return members


async def create_invite(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    email: str,
    role: Role,
    invited_by: uuid.UUID,
) -> tuple[Invite, str]:
    existing = await session.scalar(
        sa.select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id, User.email == email)
    )
    if existing is not None:
        raise Conflict("That address is already on the team.")

    token = generate_token()
    invite = Invite(
        workspace_id=workspace_id,
        email=email,
        role=role,
        token_hash=hash_token(token),
        invited_by=invited_by,
        expires_at=datetime.now(UTC) + INVITE_TTL,
    )
    session.add(invite)
    await session.commit()
    return invite, token


async def revoke_invite(session: AsyncSession, workspace_id: uuid.UUID, invite_id: uuid.UUID) -> None:
    invite = await session.scalar(
        sa.select(Invite).where(Invite.id == invite_id, Invite.workspace_id == workspace_id)
    )
    if invite is None:
        raise NotFound("Invite not found.")
    await session.delete(invite)
    await session.commit()


async def read_invite(session: AsyncSession, token: str) -> Invite:
    invite = await session.scalar(
        sa.select(Invite).where(Invite.token_hash == hash_token(token))
    )
    if invite is None or invite.expires_at <= datetime.now(UTC):
        raise NotFound("This invite is not valid.")
    if invite.accepted_at is not None:
        raise Conflict("This invite has already been accepted.")
    return invite


async def accept_invite(session: AsyncSession, token: str, name: str, password: str) -> User:
    invite = await read_invite(session, token)

    user = await session.scalar(sa.select(User).where(User.email == invite.email))
    if user is None:
        user = User(
            email=invite.email,
            name=name,
            monogram=monogram_for(name),
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()
    elif user.password_hash is None:
        user.password_hash = hash_password(password)

    session.add(
        Membership(
            workspace_id=invite.workspace_id,
            user_id=user.id,
            role=invite.role,
            status=MembershipStatus.active,
        )
    )
    invite.accepted_at = datetime.now(UTC)
    await session.commit()
    return user
```

- [ ] **Step 5: Extend the workspace service**

`apps/api/src/relaydesk/services/workspaces.py` already exists — Task 3 created it
with `active_seat_count(session, workspace_id) -> int` when the seats query was moved
out of the auth router. **Append** to that module; do not overwrite it, and leave
`active_seat_count` in place, since `GET /auth/me` calls it.

Add to `apps/api/src/relaydesk/services/workspaces.py`:

```python
import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import Membership, MembershipStatus


@dataclass(slots=True)
class SetupTask:
    id: str
    label: str
    href: str
    done: bool


async def setup_tasks(session: AsyncSession, workspace_id: uuid.UUID) -> list[SetupTask]:
    """The sidebar checklist, computed rather than stored.

    Tasks whose subsystem does not exist yet report ``done: False``; their
    slices flip them by making the underlying count real.
    """
    from relaydesk.models import Label

    members = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Membership)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.status == MembershipStatus.active,
        )
    )
    labels = await session.scalar(
        sa.select(sa.func.count()).select_from(Label).where(Label.workspace_id == workspace_id)
    )

    return [
        SetupTask("channel", "Connect a channel", "/settings/channels", False),
        SetupTask("team", "Invite your team", "/settings/team", (members or 0) > 1),
        SetupTask("integrations", "Connect an integration", "/settings/integrations", False),
        SetupTask("labels", "Create your first label", "/conversations", (labels or 0) > 0),
        SetupTask("portal", "Launch your user portal", "/user-portal/general", False),
        SetupTask("triage", "Turn on AI triage", "/settings/ai-triage", False),
        SetupTask("billing", "Choose a plan", "/settings/billing", False),
    ]
```

The `Label` import is local because `Label` is introduced in Task 7; until then the count query is the only thing referencing it. **If executing tasks strictly in order, complete Task 7 before running this function** — or temporarily hardcode `labels = 0` and restore the query in Task 7. The test in Step 2 does not assert on the label task, so either path keeps the suite green.

- [ ] **Step 6: Add the schemas and routers**

Create `apps/api/src/relaydesk/schemas/team.py`:

```python
from pydantic import EmailStr

from relaydesk.schemas.base import CamelModel


class TeamMemberOut(CamelModel):
    id: str
    name: str
    email: str
    role: str
    status: str


class InviteRequest(CamelModel):
    email: EmailStr
    role: str = "Agent"


class InviteCreated(CamelModel):
    id: str
    invite_url: str


class InvitePreview(CamelModel):
    workspace_name: str
    email: str
    role: str


class AcceptInviteRequest(CamelModel):
    name: str
    password: str
```

Create `apps/api/src/relaydesk/schemas/workspace.py`:

```python
from relaydesk.schemas.base import CamelModel


class SetupTaskOut(CamelModel):
    id: str
    label: str
    href: str
    done: bool


class WorkspacePatch(CamelModel):
    name: str | None = None
    timezone: str | None = None
```

Create `apps/api/src/relaydesk/api/team.py` with `GET /team`, `POST /team/invites` (201), `DELETE /team/invites/{id}` (204), `PATCH /team/members/{id}`, `DELETE /team/members/{id}`, all calling `scope.require_admin()` except the list; plus a separate public router for `GET /invites/{token}` and `POST /invites/{token}/accept`. Build the invite URL as `f"{get_settings().web_url}/invite/{token}"`. Map the request's `"Admin"`/`"Agent"` strings to `Role` with `Role.admin if payload.role == "Admin" else Role.agent`.

Create `apps/api/src/relaydesk/api/workspace.py` with `GET /workspace` (reusing `WorkspaceOut` from `schemas/auth.py`), `PATCH /workspace` (admin only), and `GET /workspace/setup-tasks`.

Mount all three in `api/router.py`:

```python
api_router.include_router(workspace_router, prefix="/workspace", tags=["workspace"])
api_router.include_router(team_router, prefix="/team", tags=["team"])
api_router.include_router(invite_router, prefix="/invites", tags=["team"])
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/ -v`
Expected: PASS — seven team tests plus everything earlier.

- [ ] **Step 8: Rewire the web team page**

Create `apps/web/lib/api/team.ts`:

```typescript
import "server-only";

import { apiFetch } from "@/lib/api/client";
import type { SetupTask, TeamMember } from "@/lib/types";

export async function getTeam(): Promise<TeamMember[]> {
  return apiFetch<TeamMember[]>("/team");
}

export async function getSetupTasks(): Promise<SetupTask[]> {
  return apiFetch<SetupTask[]>("/workspace/setup-tasks");
}
```

In `apps/web/lib/mock/settings.ts`, delete the `teamMembers` constant and the `getTeam` function. In `app/(console)/settings/team/page.tsx` and `app/(console)/conversations/page.tsx` and `app/(console)/conversations/[id]/page.tsx`, change `import { getTeam } from "@/lib/mock/settings"` to `import { getTeam } from "@/lib/api/team"`. In `app/(console)/layout.tsx`, replace the local `setupTasks` constant added in Task 4 with `getSetupTasks()` from `@/lib/api/team` in the existing `Promise.all`.

- [ ] **Step 9: Verify in the browser**

1. Sign in, open Settings → Team. Your own account is the only row, marked Admin / active.
2. Invite `sara@relaydesk.dev` as an Agent. The row appears with status "invited".
3. Confirm the setup checklist in the sidebar now shows "Invite your team" as incomplete with one member, and complete once a second membership exists.

- [ ] **Step 10: Lint and commit**

```bash
docker compose exec api ruff check . && docker compose exec api pytest tests/ -v
docker compose exec web pnpm lint && docker compose exec web pnpm build
git add apps/api apps/web
git commit -m "feat: add team management, invites, and computed setup tasks"
```

---

### Task 7: Inbox models and read endpoints

The largest task. Adds every remaining table and the read half of the inbox API, including the tenant-isolation suite.

**Files:**
- Create: `apps/api/src/relaydesk/models/{contact,label,conversation,message,draft,activity,saved_view}.py`
- Create: `apps/api/src/relaydesk/services/{conversations,labels}.py`
- Create: `apps/api/src/relaydesk/schemas/conversation.py`
- Create: `apps/api/src/relaydesk/api/{conversations,labels}.py`
- Create: `apps/api/migrations/versions/0005_inbox.py` (generated)
- Modify: `apps/api/src/relaydesk/models/__init__.py`, `api/router.py`, `services/workspaces.py`
- Test: `apps/api/tests/factories.py`, `apps/api/tests/test_conversations_read.py`, `apps/api/tests/test_tenant_isolation.py`

**Interfaces:**
- Consumes: `Scope`, `DbSession`, `Workspace`, `User`, `Base` mixins.
- Produces: `Contact`, `Label`, `LabelColor`, `Conversation`, `ConversationLabel`, `Channel`, `ConversationStatus`, `Priority`, `SummaryState`, `Message`, `MessageRole`, `Draft`, `ActivityEvent`, `ActivityKind`, `SavedView`; `services.conversations.{list_conversations, get_conversation, list_messages, get_draft, list_activity, status_counts, draft_count}`; `services.labels.{list_labels, create_label}`; `conversation_out(conversation, tz)`.

- [ ] **Step 1: Write the inbox models**

Create `apps/api/src/relaydesk/models/contact.py`:

```python
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Contact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("workspace_id", "email"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
```

Create `apps/api/src/relaydesk/models/label.py`:

```python
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class LabelColor(enum.StrEnum):
    citron = "citron"
    slate = "slate"
    amber = "amber"
    rose = "rose"
    sky = "sky"


class Label(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[LabelColor] = mapped_column(
        Enum(LabelColor, native_enum=False, length=16),
        default=LabelColor.slate,
        nullable=False,
    )
```

Create `apps/api/src/relaydesk/models/conversation.py`:

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Channel(enum.StrEnum):
    email = "email"
    discord = "discord"
    portal = "portal"
    api = "api"


class ConversationStatus(enum.StrEnum):
    open = "open"
    pending = "pending"
    resolved = "resolved"
    on_hold = "on_hold"
    ignored = "ignored"
    trash = "trash"


class Priority(enum.StrEnum):
    urgent = "urgent"
    high = "high"
    medium = "medium"
    low = "low"


class SummaryState(enum.StrEnum):
    none = "none"
    ready = "ready"
    failed = "failed"


class ConversationLabel(Base):
    __tablename__ = "conversation_labels"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True
    )


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "number"),
        Index("ix_conversations_inbox", "workspace_id", "status", "last_message_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(400), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("contacts.id", ondelete="RESTRICT"), nullable=False
    )
    channel: Mapped[Channel] = mapped_column(
        Enum(Channel, native_enum=False, length=16), nullable=False
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, native_enum=False, length=16),
        default=ConversationStatus.open,
        nullable=False,
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=False, length=16), default=Priority.medium, nullable=False
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    preview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    unread: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_state: Mapped[SummaryState] = mapped_column(
        Enum(SummaryState, native_enum=False, length=16),
        default=SummaryState.none,
        nullable=False,
    )

    contact = relationship("Contact", lazy="selectin")
    assignee = relationship("User", lazy="selectin")
    labels = relationship("Label", secondary="conversation_labels", lazy="selectin")
    draft = relationship(
        "Draft", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )
```

Create `apps/api/src/relaydesk/models/message.py`:

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class MessageRole(enum.StrEnum):
    customer = "customer"
    agent = "agent"
    ai = "ai"


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_thread", "conversation_id", "sent_at"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, native_enum=False, length=16), nullable=False
    )
    author_name: Mapped[str] = mapped_column(String(160), nullable=False)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    to_address: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Create `apps/api/src/relaydesk/models/draft.py`:

```python
import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Draft(UUIDMixin, TimestampMixin, Base):
    """An AI-written reply awaiting an agent. Nothing writes these until slice 4."""

    __tablename__ = "drafts"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
```

Create `apps/api/src/relaydesk/models/activity.py`:

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class ActivityKind(enum.StrEnum):
    created = "created"
    status = "status"
    priority = "priority"
    assignee = "assignee"
    label = "label"
    reply = "reply"


class ActivityEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "activity_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[ActivityKind] = mapped_column(
        Enum(ActivityKind, native_enum=False, length=16), nullable=False
    )
    verb: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Create `apps/api/src/relaydesk/models/saved_view.py`:

```python
import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class SavedView(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "saved_views"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

Export every new name from `models/__init__.py`, then generate `0005_inbox.py` (`revision = "0005"`, `down_revision = "0004"`).

- [ ] **Step 2: Write the test factories**

Create `apps/api/tests/factories.py`:

```python
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import (
    Channel,
    Contact,
    Conversation,
    ConversationStatus,
    Draft,
    Label,
    Membership,
    MembershipStatus,
    Message,
    MessageRole,
    Priority,
    Role,
    User,
    Workspace,
)
from relaydesk.security.passwords import hash_password


async def make_workspace(session: AsyncSession, slug: str = "chronon") -> Workspace:
    workspace = Workspace(name=slug.title(), slug=slug, monogram=slug[:2].upper())
    session.add(workspace)
    await session.flush()
    return workspace


async def make_member(
    session: AsyncSession,
    workspace: Workspace,
    email: str = "nilesh@relaydesk.dev",
    name: str = "Nilesh Pant",
    role: Role = Role.admin,
    password: str = "relaydesk",
) -> User:
    user = User(
        email=email, name=name, monogram="".join(p[0] for p in name.split()[:2]).upper(),
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=role,
            status=MembershipStatus.active,
        )
    )
    await session.flush()
    return user


async def make_conversation(
    session: AsyncSession,
    workspace: Workspace,
    *,
    subject: str = "Checkout fails with a 402",
    status: ConversationStatus = ConversationStatus.open,
    priority: Priority = Priority.urgent,
    assignee: User | None = None,
    minutes_ago: int = 12,
    with_draft: bool = False,
    contact_email: str = "priya@northwind.io",
    contact_name: str = "Priya Raman",
) -> Conversation:
    # Contacts are unique per (workspace, email), so reuse one when it exists.
    # Several tests create two conversations in one workspace.
    contact = await session.scalar(
        sa.select(Contact).where(
            Contact.workspace_id == workspace.id, Contact.email == contact_email
        )
    )
    if contact is None:
        contact = Contact(workspace_id=workspace.id, email=contact_email, name=contact_name)
        session.add(contact)
        await session.flush()

    workspace.conversation_seq += 1
    sent_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    conversation = Conversation(
        workspace_id=workspace.id,
        number=workspace.conversation_seq,
        subject=subject,
        contact_id=contact.id,
        channel=Channel.email,
        status=status,
        priority=priority,
        assignee_id=assignee.id if assignee else None,
        preview="Every time I switch to annual billing the payment step returns a 402.",
        last_message_at=sent_at,
    )
    session.add(conversation)
    await session.flush()

    session.add(
        Message(
            workspace_id=workspace.id,
            conversation_id=conversation.id,
            role=MessageRole.customer,
            author_name=contact.name,
            to_address="support@chronon.co",
            body=conversation.preview,
            sent_at=sent_at,
        )
    )
    if with_draft:
        session.add(
            Draft(
                workspace_id=workspace.id,
                conversation_id=conversation.id,
                body="Hi Priya,\n\nSorry about that.",
            )
        )
    await session.commit()
    return conversation


async def make_label(
    session: AsyncSession, workspace: Workspace, name: str = "Billing"
) -> Label:
    label = Label(workspace_id=workspace.id, name=name)
    session.add(label)
    await session.commit()
    return label


async def sign_in(client, session: AsyncSession, user_email: str, password: str = "relaydesk") -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": user_email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}
```

- [ ] **Step 3: Write the failing read tests**

Create `apps/api/tests/test_conversations_read.py`:

```python
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ConversationStatus
from tests.factories import (
    make_conversation,
    make_label,
    make_member,
    make_workspace,
    sign_in,
)


async def test_list_returns_the_console_shape(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, assignee=user, with_draft=True)
    headers = await sign_in(client, db_session, user.email)

    response = await client.get("/api/conversations?status=open", headers=headers)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["subject"] == "Checkout fails with a 402"
    assert item["customerName"] == "Priya Raman"
    assert item["customerEmail"] == "priya@northwind.io"
    assert item["channel"] == "email"
    assert item["status"] == "open"
    assert item["priority"] == "urgent"
    assert item["assignee"] == "Nilesh Pant"
    assert item["assigneeId"] == str(user.id)
    assert item["hasDraft"] is True
    assert item["summaryState"] == "none"
    assert item["summary"] is None
    assert item["number"] == 1
    assert item["age"] == "12m"
    assert item["labelIds"] == []


async def test_list_filters_by_status(client: AsyncClient, db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace)
    await make_conversation(db_session, workspace, status=ConversationStatus.resolved)
    headers = await sign_in(client, db_session, user.email)

    open_items = (await client.get("/api/conversations?status=open", headers=headers)).json()
    resolved = (await client.get("/api/conversations?status=resolved", headers=headers)).json()

    assert len(open_items["items"]) == 1
    assert len(resolved["items"]) == 1


async def test_counts_cover_every_status_and_drafts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, with_draft=True)
    await make_conversation(db_session, workspace, status=ConversationStatus.pending)
    headers = await sign_in(client, db_session, user.email)

    body = (await client.get("/api/conversations/counts", headers=headers)).json()

    counts = {entry["status"]: entry["count"] for entry in body["statuses"]}
    assert counts["open"] == 1
    assert counts["pending"] == 1
    assert counts["trash"] == 0
    assert body["drafts"] == 1


async def test_detail_messages_activity_and_draft(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace, with_draft=True)
    headers = await sign_in(client, db_session, user.email)
    base = f"/api/conversations/{conversation.id}"

    detail = await client.get(base, headers=headers)
    messages = await client.get(f"{base}/messages", headers=headers)
    draft = await client.get(f"{base}/draft", headers=headers)
    activity = await client.get(f"{base}/activity", headers=headers)

    assert detail.status_code == 200
    assert messages.json()[0]["role"] == "customer"
    assert messages.json()[0]["author"] == "Priya Raman"
    assert draft.json()["body"].startswith("Hi Priya")
    assert activity.status_code == 200


async def test_missing_draft_is_a_404(client: AsyncClient, db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    headers = await sign_in(client, db_session, user.email)

    response = await client.get(f"/api/conversations/{conversation.id}/draft", headers=headers)

    assert response.status_code == 404


async def test_labels_are_listed_and_created(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_label(db_session, workspace)
    headers = await sign_in(client, db_session, user.email)

    listed = (await client.get("/api/labels", headers=headers)).json()
    created = await client.post("/api/labels", headers=headers, json={"name": "Bug"})

    assert [entry["name"] for entry in listed] == ["Billing"]
    assert created.status_code == 201
    assert created.json()["color"] in {"citron", "slate", "amber", "rose", "sky"}


async def test_creating_a_duplicate_label_returns_the_existing_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    label = await make_label(db_session, workspace)
    headers = await sign_in(client, db_session, user.email)

    response = await client.post("/api/labels", headers=headers, json={"name": "billing"})

    assert response.status_code == 201
    assert response.json()["id"] == str(label.id)
```

Create `apps/api/tests/test_tenant_isolation.py`:

```python
"""Cross-workspace access must be indistinguishable from nonexistence.

This is the failure mode with the worst consequences and the least chance
of being noticed by hand, so every workspace-scoped route is checked.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_conversation, make_label, make_member, make_workspace, sign_in


@pytest.fixture
async def two_workspaces(client: AsyncClient, db_session: AsyncSession):
    mine = await make_workspace(db_session, slug="chronon")
    theirs = await make_workspace(db_session, slug="northwind")
    me = await make_member(db_session, mine, email="me@relaydesk.dev", name="Me Myself")
    await make_member(db_session, theirs, email="them@northwind.io", name="Them Other")
    foreign = await make_conversation(db_session, theirs)
    foreign_label = await make_label(db_session, theirs, name="TheirLabel")
    headers = await sign_in(client, db_session, me.email)
    return headers, foreign, foreign_label


async def test_foreign_conversation_is_not_listed(client, two_workspaces) -> None:
    headers, _, _ = two_workspaces

    body = (await client.get("/api/conversations?status=open", headers=headers)).json()

    assert body["items"] == []


@pytest.mark.parametrize(
    "suffix", ["", "/messages", "/draft", "/activity"]
)
async def test_foreign_conversation_reads_return_404(client, two_workspaces, suffix) -> None:
    headers, foreign, _ = two_workspaces

    response = await client.get(f"/api/conversations/{foreign.id}{suffix}", headers=headers)

    assert response.status_code == 404


async def test_foreign_label_is_not_listed(client, two_workspaces) -> None:
    headers, _, _ = two_workspaces

    body = (await client.get("/api/labels", headers=headers)).json()

    assert body == []


async def test_counts_exclude_other_workspaces(client, two_workspaces) -> None:
    headers, _, _ = two_workspaces

    body = (await client.get("/api/conversations/counts", headers=headers)).json()

    assert all(entry["count"] == 0 for entry in body["statuses"])
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `docker compose exec api pytest tests/test_conversations_read.py tests/test_tenant_isolation.py -v`
Expected: FAIL — the conversation routes do not exist.

- [ ] **Step 5: Write the presentation helpers and schemas**

Create `apps/api/src/relaydesk/schemas/conversation.py`:

```python
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from relaydesk.models import ActivityEvent, Conversation, Message
from relaydesk.schemas.base import CamelModel


def humanize_age(moment: datetime, now: datetime | None = None) -> str:
    """The list's compact age column: "now", "12m", "3h", "2d"."""
    now = now or datetime.now(UTC)
    seconds = max(int((now - moment).total_seconds()), 0)
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def calendar_date(moment: datetime, timezone: str) -> str:
    """The short calendar label, e.g. "Sep 4", in the workspace's timezone."""
    local = moment.astimezone(ZoneInfo(timezone))
    return f"{local:%b} {local.day}"


class ConversationOut(CamelModel):
    id: str
    number: int
    subject: str
    preview: str
    customer_name: str
    customer_email: str
    channel: str
    status: str
    priority: str
    age: str
    date: str
    assignee: str | None
    assignee_id: str | None
    label_ids: list[str]
    has_draft: bool
    unread: bool
    summary: str | None
    summary_state: str


class ConversationPage(CamelModel):
    items: list[ConversationOut]
    next_cursor: str | None = None


class StatusCountOut(CamelModel):
    status: str
    count: int


class CountsResponse(CamelModel):
    statuses: list[StatusCountOut]
    drafts: int


class MessageOut(CamelModel):
    id: str
    author: str
    to: str
    role: str
    body: str
    sent_at: str


class DraftOut(CamelModel):
    body: str


class ActivityEventOut(CamelModel):
    id: str
    conversation_id: str
    actor: str
    kind: str
    verb: str
    value: str
    status: str | None = None
    at: str


class LabelOut(CamelModel):
    id: str
    name: str
    color: str


def conversation_out(conversation: Conversation, timezone: str) -> ConversationOut:
    return ConversationOut(
        id=str(conversation.id),
        number=conversation.number,
        subject=conversation.subject,
        preview=conversation.preview,
        customer_name=conversation.contact.name,
        customer_email=conversation.contact.email,
        channel=conversation.channel.value,
        status=conversation.status.value,
        priority=conversation.priority.value,
        age=humanize_age(conversation.last_message_at),
        date=calendar_date(conversation.last_message_at, timezone),
        assignee=conversation.assignee.name if conversation.assignee else None,
        assignee_id=str(conversation.assignee_id) if conversation.assignee_id else None,
        label_ids=[str(label.id) for label in conversation.labels],
        has_draft=conversation.draft is not None,
        unread=conversation.unread,
        summary=conversation.summary,
        summary_state=conversation.summary_state.value,
    )


def message_out(message: Message, timezone: str) -> MessageOut:
    local = message.sent_at.astimezone(ZoneInfo(timezone))
    return MessageOut(
        id=str(message.id),
        author=message.author_name,
        to=message.to_address,
        role=message.role.value,
        body=message.body,
        sent_at=f"{local:%b} {local.day}, {local:%-I:%M %p}",
    )


def activity_out(event: ActivityEvent, timezone: str) -> ActivityEventOut:
    local = event.at.astimezone(ZoneInfo(timezone))
    return ActivityEventOut(
        id=str(event.id),
        conversation_id=str(event.conversation_id),
        actor=event.actor_name,
        kind=event.kind.value,
        verb=event.verb,
        value=event.value,
        status=event.status,
        at=f"{local:%b} {local.day}, {local:%-I:%M %p}",
    )
```

- [ ] **Step 6: Write the read services**

Create `apps/api/src/relaydesk/services/conversations.py`:

```python
import base64
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models import (
    ActivityEvent,
    Conversation,
    ConversationLabel,
    ConversationStatus,
    Draft,
    Message,
)

DEFAULT_LIMIT = 50


def encode_cursor(conversation: Conversation) -> str:
    raw = f"{conversation.last_message_at.isoformat()}|{conversation.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    moment, identifier = raw.split("|", 1)
    return datetime.fromisoformat(moment), uuid.UUID(identifier)


async def list_conversations(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    status: ConversationStatus | None = None,
    label_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    has_draft: bool | None = None,
    include_trash: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[Conversation], str | None]:
    """Keyset-paginated inbox list, newest first.

    Ordering by ``(last_message_at, id)`` makes the cursor stable even when
    two conversations share a timestamp.
    """
    query = sa.select(Conversation).where(Conversation.workspace_id == workspace_id)

    if status is not None:
        query = query.where(Conversation.status == status)
    elif not include_trash:
        query = query.where(Conversation.status != ConversationStatus.trash)

    if label_id is not None:
        query = query.join(
            ConversationLabel, ConversationLabel.conversation_id == Conversation.id
        ).where(ConversationLabel.label_id == label_id)
    if assignee_id is not None:
        query = query.where(Conversation.assignee_id == assignee_id)
    if has_draft:
        query = query.join(Draft, Draft.conversation_id == Conversation.id)

    if cursor:
        moment, identifier = decode_cursor(cursor)
        query = query.where(
            sa.tuple_(Conversation.last_message_at, Conversation.id) < (moment, identifier)
        )

    query = query.order_by(
        Conversation.last_message_at.desc(), Conversation.id.desc()
    ).limit(limit + 1)

    rows = list(await session.scalars(query))
    next_cursor = encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return rows[:limit], next_cursor


async def get_conversation(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    """Cross-workspace ids raise NotFound, never Forbidden."""
    conversation = await session.scalar(
        sa.select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    if conversation is None:
        raise NotFound("Conversation not found.")
    return conversation


async def list_messages(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[Message]:
    await get_conversation(session, workspace_id, conversation_id)
    return list(
        await session.scalars(
            sa.select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sent_at)
        )
    )


async def get_draft(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> Draft:
    await get_conversation(session, workspace_id, conversation_id)
    draft = await session.scalar(
        sa.select(Draft).where(Draft.conversation_id == conversation_id)
    )
    if draft is None:
        raise NotFound("No draft for this conversation.")
    return draft


async def list_activity(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[ActivityEvent]:
    await get_conversation(session, workspace_id, conversation_id)
    return list(
        await session.scalars(
            sa.select(ActivityEvent)
            .where(ActivityEvent.conversation_id == conversation_id)
            .order_by(ActivityEvent.at.desc())
        )
    )


async def status_counts(
    session: AsyncSession, workspace_id: uuid.UUID
) -> dict[ConversationStatus, int]:
    rows = await session.execute(
        sa.select(Conversation.status, sa.func.count())
        .where(Conversation.workspace_id == workspace_id)
        .group_by(Conversation.status)
    )
    counted = dict(rows.all())
    return {status: counted.get(status, 0) for status in ConversationStatus}


async def draft_count(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            sa.select(sa.func.count())
            .select_from(Draft)
            .join(Conversation, Conversation.id == Draft.conversation_id)
            .where(
                Draft.workspace_id == workspace_id,
                Conversation.status != ConversationStatus.trash,
            )
        )
    ) or 0
```

Create `apps/api/src/relaydesk/services/labels.py`:

```python
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models import Label, LabelColor

PALETTE = [
    LabelColor.citron,
    LabelColor.slate,
    LabelColor.amber,
    LabelColor.rose,
    LabelColor.sky,
]


async def list_labels(session: AsyncSession, workspace_id: uuid.UUID) -> list[Label]:
    return list(
        await session.scalars(
            sa.select(Label).where(Label.workspace_id == workspace_id).order_by(Label.name)
        )
    )


async def create_label(session: AsyncSession, workspace_id: uuid.UUID, name: str) -> Label:
    """Idempotent by name, so a double submit returns the existing label."""
    trimmed = name.strip()
    if not trimmed:
        raise Invalid("A label needs a name.")

    existing = await session.scalar(
        sa.select(Label).where(
            Label.workspace_id == workspace_id,
            sa.func.lower(Label.name) == trimmed.lower(),
        )
    )
    if existing is not None:
        return existing

    count = await session.scalar(
        sa.select(sa.func.count()).select_from(Label).where(Label.workspace_id == workspace_id)
    )
    label = Label(
        workspace_id=workspace_id, name=trimmed, color=PALETTE[(count or 0) % len(PALETTE)]
    )
    session.add(label)
    await session.commit()
    return label
```

- [ ] **Step 7: Write the read routers**

Create `apps/api/src/relaydesk/api/conversations.py` with `GET ""`, `GET "/counts"`, `GET "/{conversation_id}"`, `GET "/{conversation_id}/messages"`, `GET "/{conversation_id}/draft"`, and `GET "/{conversation_id}/activity"`. Each takes `scope: Scope` and `session: DbSession`, calls the matching service, and maps through the `*_out` helpers using `scope.workspace.timezone`.

The list route accepts two pseudo-statuses the sidebar uses, which are not
`ConversationStatus` members and must be translated before the service call:

```python
@router.get("", response_model=ConversationPage)
async def list_route(
    scope: Scope,
    session: DbSession,
    status: str | None = None,
    label_id: uuid.UUID | None = Query(None, alias="labelId"),
    assignee_id: uuid.UUID | None = Query(None, alias="assigneeId"),
    view_id: uuid.UUID | None = Query(None, alias="viewId"),
    limit: int = 50,
    cursor: str | None = None,
) -> ConversationPage:
    # "all" and "drafts" are sidebar filters, not stored statuses.
    real_status = None
    has_draft = None
    if status == "drafts":
        has_draft = True
    elif status and status != "all":
        real_status = ConversationStatus(status)

    rows, next_cursor = await conversations.list_conversations(
        session,
        scope.workspace_id,
        status=real_status,
        label_id=label_id,
        assignee_id=assignee_id,
        has_draft=has_draft,
        limit=limit,
        cursor=cursor,
    )
    return ConversationPage(
        items=[conversation_out(row, scope.workspace.timezone) for row in rows],
        next_cursor=next_cursor,
    )
```

An unrecognised status string raises `ValueError` from the enum call; add
`except ValueError: raise Invalid(f"Unknown status {status!r}.")` around it so the
client gets a 422 rather than a 500.

Declare `/counts` **before** `/{conversation_id}` in the module; FastAPI matches in declaration order and would otherwise treat `counts` as an id.

Create `apps/api/src/relaydesk/api/labels.py` with `GET ""` and `POST ""` (status 201).

Mount both in `api/router.py`:

```python
api_router.include_router(conversations_router, prefix="/conversations", tags=["inbox"])
api_router.include_router(labels_router, prefix="/labels", tags=["inbox"])
```

- [ ] **Step 8: Restore the label count in setup tasks**

Now that `Label` exists, move the local `from relaydesk.models import Label` in `services/workspaces.py` to the top of the file with the other model imports.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/ -v`
Expected: PASS — seven read tests, seven isolation tests, and everything earlier.

- [ ] **Step 10: Lint and commit**

```bash
docker compose exec api ruff check .
git add apps/api
git commit -m "feat(api): add inbox models and read endpoints"
```

---

### Task 8: Rewire the console reads

**Files:**
- Create: `apps/web/lib/api/conversations.ts`
- Create: `apps/web/lib/api/labels.ts`
- Modify: `apps/web/app/(console)/layout.tsx`
- Modify: `apps/web/app/(console)/conversations/page.tsx`
- Modify: `apps/web/app/(console)/conversations/[id]/page.tsx`
- Modify: `apps/web/lib/types.ts`
- Delete: `apps/web/lib/mock/conversations.ts`

**Interfaces:**
- Consumes: `GET /conversations`, `/conversations/counts`, `/conversations/{id}`, `/messages`, `/draft`, `/activity`, `GET /labels`.
- Produces: `getConversations(filters?)`, `getConversation(id)`, `getMessages(id)`, `getDraft(id)`, `getActivity(id)`, `getStatusCounts()`, `getDraftCount()`, `getLabels()`.

- [ ] **Step 1: Add `assigneeId` to the Conversation type**

In `apps/web/lib/types.ts`, add to `Conversation`, directly beneath `assignee`:

```typescript
  /** Stable id for mutations; `assignee` stays the display name. */
  assigneeId: string | null;
```

- [ ] **Step 2: Write the conversations API module**

Create `apps/web/lib/api/conversations.ts`:

```typescript
import "server-only";

import { ApiError, apiFetch } from "@/lib/api/client";
import type {
  ActivityEvent,
  Conversation,
  ConversationStatus,
  Message,
  StatusCount,
} from "@/lib/types";

interface Page<T> {
  items: T[];
  nextCursor: string | null;
}

export interface ConversationFilters {
  status?: ConversationStatus | "all" | "drafts";
  labelId?: string;
  assigneeId?: string;
  viewId?: string;
}

export async function getConversations(
  filters: ConversationFilters = {},
): Promise<Conversation[]> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) query.set(key, value);
  }
  const suffix = query.size > 0 ? `?${query}` : "";
  const page = await apiFetch<Page<Conversation>>(`/conversations${suffix}`);
  return page.items;
}

export async function getConversation(id: string): Promise<Conversation | null> {
  try {
    return await apiFetch<Conversation>(`/conversations/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getMessages(id: string): Promise<Message[]> {
  return apiFetch<Message[]>(`/conversations/${id}/messages`);
}

export async function getDraft(id: string): Promise<string | null> {
  try {
    const draft = await apiFetch<{ body: string }>(`/conversations/${id}/draft`);
    return draft.body;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getActivity(id: string): Promise<ActivityEvent[]> {
  return apiFetch<ActivityEvent[]>(`/conversations/${id}/activity`);
}

export async function getStatusCounts(): Promise<StatusCount[]> {
  const counts = await apiFetch<{ statuses: StatusCount[]; drafts: number }>(
    "/conversations/counts",
  );
  return counts.statuses;
}

export async function getDraftCount(): Promise<number> {
  const counts = await apiFetch<{ statuses: StatusCount[]; drafts: number }>(
    "/conversations/counts",
  );
  return counts.drafts;
}
```

`getDraft` and `getConversation` translate a 404 into `null` because that is the contract the pages already expect — `getConversation` feeds `notFound()`, and `getDraft` feeds a nullable prop.

Create `apps/web/lib/api/labels.ts`:

```typescript
import "server-only";

import { apiFetch } from "@/lib/api/client";
import type { Label } from "@/lib/types";

export async function getLabels(): Promise<Label[]> {
  return apiFetch<Label[]>("/labels");
}

export async function createLabel(name: string): Promise<Label> {
  return apiFetch<Label>("/labels", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}
```

- [ ] **Step 3: Move filtering to the server in the conversations page**

In `apps/web/app/(console)/conversations/page.tsx`, replace the mock imports and the in-memory filtering. The whole data-loading block becomes:

```typescript
import { getConversations } from "@/lib/api/conversations";
import { getLabels } from "@/lib/api/labels";
import { getTeam } from "@/lib/api/team";
import { getViews } from "@/lib/api/views";
import { statuses } from "@/lib/types";
```

```typescript
  const { status = "open", view, label } = await searchParams;

  const [labels, team, views] = await Promise.all([getLabels(), getTeam(), getViews()]);

  let conversations: Conversation[];
  let title: string;
  let icon: React.ReactNode = null;

  if (view) {
    conversations = await getConversations({ viewId: view });
    title = views.find((entry) => entry.id === view)?.name ?? "View";
  } else if (label) {
    conversations = await getConversations({ labelId: label });
    title = labels.find((entry) => entry.id === label)?.name ?? "Label";
  } else if (isStatus(status)) {
    conversations = await getConversations({ status });
    title = statusMeta[status].label;
    icon = <StatusIcon status={status} className="size-4" />;
  } else if (status === "drafts") {
    conversations = await getConversations({ status: "drafts" });
    title = virtualTitles.drafts;
  } else {
    conversations = await getConversations({ status: "all" });
    title = virtualTitles.all;
  }
```

Delete the `viewFilters` constant and the `currentUser` import — that logic moves to the API in Task 10. `getViews` is created in Task 10; until then, stub `apps/web/lib/api/views.ts` with `export async function getViews(): Promise<SavedView[]> { return []; }` so this task builds on its own.

- [ ] **Step 4: Rewire the detail page and layout**

In `apps/web/app/(console)/conversations/[id]/page.tsx`, change the import block from `@/lib/mock/conversations` to `@/lib/api/conversations`, and the `getLabels` import to `@/lib/api/labels`. Change the siblings call to `getConversations({ status: conversation.status })`.

In `apps/web/app/(console)/layout.tsx`, change `getStatusCounts`, `getDraftCount` to come from `@/lib/api/conversations` and `getLabels` from `@/lib/api/labels`.

- [ ] **Step 5: Delete the mock store**

```bash
git rm apps/web/lib/mock/conversations.ts
```

Then run `grep -rn "lib/mock/conversations" apps/web/app apps/web/components` and confirm the only remaining hit is `components/console/sidebar.tsx` importing `savedViews` — Task 10 removes it. Until then, replace that import with a local `const savedViews: SavedView[] = [];` inside `sidebar.tsx` so the build passes.

- [ ] **Step 6: Verify in the browser**

Insert one conversation by hand:

```bash
docker compose exec api python -c "
import asyncio
from relaydesk.db.session import async_session_factory
from tests.factories import make_conversation
import sqlalchemy as sa
from relaydesk.models import Workspace

async def main():
    async with async_session_factory() as s:
        w = await s.scalar(sa.select(Workspace))
        await make_conversation(s, w, with_draft=True)

asyncio.run(main())
"
```

Then check: the inbox lists that conversation with the customer's name, an age like `2m`, and a draft indicator; the sidebar counts show 1 open; clicking through shows the thread and the AI draft in the composer; the details sidebar renders with an empty activity list and no summary.

- [ ] **Step 7: Lint, build, and commit**

```bash
docker compose exec web pnpm lint && docker compose exec web pnpm build
git add apps/web
git commit -m "feat(web): read the inbox from the API"
```

---

### Task 9: Inbox mutations

**Files:**
- Modify: `apps/api/src/relaydesk/services/conversations.py`
- Modify: `apps/api/src/relaydesk/api/conversations.py`
- Modify: `apps/api/src/relaydesk/schemas/conversation.py`
- Modify: `apps/web/app/(console)/conversations/actions.ts`
- Modify: `apps/web/components/inbox/pickers.tsx`
- Test: `apps/api/tests/test_conversation_mutations.py`

**Interfaces:**
- Consumes: `get_conversation`, `Conversation`, `ActivityEvent`, `Message`, `Draft`, `Label`.
- Produces: `services.conversations.{set_status, set_priority, set_assignee, add_label, remove_label, add_reply, discard_draft}`, each returning the updated `Conversation` and recording an `ActivityEvent`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_conversation_mutations.py`:

```python
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_conversation, make_label, make_member, make_workspace, sign_in


async def setup(client: AsyncClient, session: AsyncSession):
    workspace = await make_workspace(session)
    user = await make_member(session, workspace)
    conversation = await make_conversation(session, workspace, with_draft=True)
    headers = await sign_in(client, session, user.email)
    return workspace, user, conversation, headers


async def test_status_change_records_activity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, conversation, headers = await setup(client, db_session)

    response = await client.patch(
        f"/api/conversations/{conversation.id}", headers=headers, json={"status": "resolved"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"

    activity = (
        await client.get(f"/api/conversations/{conversation.id}/activity", headers=headers)
    ).json()
    assert activity[0]["kind"] == "status"
    assert activity[0]["verb"] == "marked this as"
    assert activity[0]["value"] == "Resolved"
    assert activity[0]["status"] == "resolved"
    assert activity[0]["actor"] == "Nilesh Pant"


async def test_setting_the_same_status_records_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, conversation, headers = await setup(client, db_session)

    await client.patch(
        f"/api/conversations/{conversation.id}", headers=headers, json={"status": "open"}
    )

    activity = (
        await client.get(f"/api/conversations/{conversation.id}/activity", headers=headers)
    ).json()
    assert activity == []


async def test_priority_and_assignee_changes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, user, conversation, headers = await setup(client, db_session)

    await client.patch(
        f"/api/conversations/{conversation.id}", headers=headers, json={"priority": "low"}
    )
    assigned = await client.patch(
        f"/api/conversations/{conversation.id}",
        headers=headers,
        json={"assigneeId": str(user.id)},
    )

    assert assigned.json()["assignee"] == "Nilesh Pant"
    assert assigned.json()["assigneeId"] == str(user.id)

    activity = (
        await client.get(f"/api/conversations/{conversation.id}/activity", headers=headers)
    ).json()
    kinds = [event["kind"] for event in activity]
    assert "assignee" in kinds and "priority" in kinds


async def test_unassigning_records_the_right_verb(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, user, conversation, headers = await setup(client, db_session)
    await client.patch(
        f"/api/conversations/{conversation.id}",
        headers=headers,
        json={"assigneeId": str(user.id)},
    )

    await client.patch(
        f"/api/conversations/{conversation.id}", headers=headers, json={"assigneeId": None}
    )

    activity = (
        await client.get(f"/api/conversations/{conversation.id}/activity", headers=headers)
    ).json()
    assert activity[0]["verb"] == "unassigned this from"
    assert activity[0]["value"] == "Nilesh Pant"


async def test_labels_attach_and_detach_idempotently(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace, _, conversation, headers = await setup(client, db_session)
    label = await make_label(db_session, workspace)
    path = f"/api/conversations/{conversation.id}/labels/{label.id}"

    assert (await client.put(path, headers=headers)).status_code == 200
    assert (await client.put(path, headers=headers)).status_code == 200
    detail = (await client.get(f"/api/conversations/{conversation.id}", headers=headers)).json()
    assert detail["labelIds"] == [str(label.id)]

    assert (await client.delete(path, headers=headers)).status_code == 200
    detail = (await client.get(f"/api/conversations/{conversation.id}", headers=headers)).json()
    assert detail["labelIds"] == []


async def test_reply_appends_a_message_and_clears_the_draft(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, conversation, headers = await setup(client, db_session)

    response = await client.post(
        f"/api/conversations/{conversation.id}/replies",
        headers=headers,
        json={"body": "On it — checking now.", "resolve": True},
    )

    assert response.status_code == 201
    messages = (
        await client.get(f"/api/conversations/{conversation.id}/messages", headers=headers)
    ).json()
    assert messages[-1]["body"] == "On it — checking now."
    assert messages[-1]["role"] == "agent"
    assert messages[-1]["author"] == "Nilesh Pant"

    detail = (await client.get(f"/api/conversations/{conversation.id}", headers=headers)).json()
    assert detail["hasDraft"] is False
    assert detail["status"] == "resolved"
    assert detail["unread"] is False
    assert detail["preview"] == "On it — checking now."


async def test_discarding_a_draft(client: AsyncClient, db_session: AsyncSession) -> None:
    _, _, conversation, headers = await setup(client, db_session)

    response = await client.delete(
        f"/api/conversations/{conversation.id}/draft", headers=headers
    )

    assert response.status_code == 204
    detail = (await client.get(f"/api/conversations/{conversation.id}", headers=headers)).json()
    assert detail["hasDraft"] is False


async def test_bulk_status_change(client: AsyncClient, db_session: AsyncSession) -> None:
    workspace, _, first, headers = await setup(client, db_session)
    second = await make_conversation(db_session, workspace)

    response = await client.post(
        "/api/conversations/bulk-status",
        headers=headers,
        json={"ids": [str(first.id), str(second.id)], "status": "trash"},
    )

    assert response.status_code == 204
    counts = (await client.get("/api/conversations/counts", headers=headers)).json()
    by_status = {entry["status"]: entry["count"] for entry in counts["statuses"]}
    assert by_status["trash"] == 2


async def test_mutating_a_foreign_conversation_is_a_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, _, headers = await setup(client, db_session)
    other = await make_workspace(db_session, slug="northwind")
    await make_member(db_session, other, email="them@northwind.io", name="Them Other")
    foreign = await make_conversation(db_session, other)

    response = await client.patch(
        f"/api/conversations/{foreign.id}", headers=headers, json={"status": "resolved"}
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_conversation_mutations.py -v`
Expected: FAIL — 405 Method Not Allowed, since only GET routes exist.

- [ ] **Step 3: Implement the mutation services**

Append to `apps/api/src/relaydesk/services/conversations.py`:

```python
STATUS_LABEL = {
    ConversationStatus.open: "Open",
    ConversationStatus.pending: "Pending",
    ConversationStatus.resolved: "Resolved",
    ConversationStatus.on_hold: "On hold",
    ConversationStatus.ignored: "Ignored",
    ConversationStatus.trash: "Trash",
}
PRIORITY_LABEL = {
    Priority.urgent: "Urgent",
    Priority.high: "High",
    Priority.medium: "Medium",
    Priority.low: "Low",
}


def record(
    session: AsyncSession,
    conversation: Conversation,
    actor: User,
    kind: ActivityKind,
    verb: str,
    value: str,
    status: str | None = None,
) -> None:
    """Append to the conversation's history.

    Every mutation calls this, so the detail panel's timeline is a
    consequence of the change rather than a second thing to remember.
    """
    session.add(
        ActivityEvent(
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            actor_user_id=actor.id,
            actor_name=actor.name,
            kind=kind,
            verb=verb,
            value=value,
            status=status,
            at=datetime.now(UTC),
        )
    )


async def set_status(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    status: ConversationStatus,
    actor: User,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    if conversation.status is status:
        return conversation
    conversation.status = status
    conversation.unread = False
    record(
        session, conversation, actor, ActivityKind.status,
        "marked this as", STATUS_LABEL[status], status.value,
    )
    await session.commit()
    return conversation


async def set_priority(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    priority: Priority,
    actor: User,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    if conversation.priority is priority:
        return conversation
    conversation.priority = priority
    record(
        session, conversation, actor, ActivityKind.priority,
        "set priority to", PRIORITY_LABEL[priority],
    )
    await session.commit()
    return conversation


async def set_assignee(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    assignee_id: uuid.UUID | None,
    actor: User,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    if conversation.assignee_id == assignee_id:
        return conversation

    previous = conversation.assignee.name if conversation.assignee else None
    if assignee_id is None:
        verb, value = "unassigned this from", previous or "everyone"
    else:
        assignee = await session.get(User, assignee_id)
        if assignee is None:
            raise NotFound("That team member does not exist.")
        verb, value = "assigned this to", assignee.name

    conversation.assignee_id = assignee_id
    record(session, conversation, actor, ActivityKind.assignee, verb, value)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def add_label(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    label_id: uuid.UUID,
    actor: User,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    label = await session.scalar(
        sa.select(Label).where(Label.id == label_id, Label.workspace_id == workspace_id)
    )
    if label is None:
        raise NotFound("Label not found.")
    if any(existing.id == label.id for existing in conversation.labels):
        return conversation

    session.add(ConversationLabel(conversation_id=conversation.id, label_id=label.id))
    record(session, conversation, actor, ActivityKind.label, "added label", label.name)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def remove_label(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    label_id: uuid.UUID,
    actor: User,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    label = await session.scalar(
        sa.select(Label).where(Label.id == label_id, Label.workspace_id == workspace_id)
    )
    if label is None:
        raise NotFound("Label not found.")
    if not any(existing.id == label.id for existing in conversation.labels):
        return conversation

    await session.execute(
        sa.delete(ConversationLabel).where(
            ConversationLabel.conversation_id == conversation.id,
            ConversationLabel.label_id == label.id,
        )
    )
    record(session, conversation, actor, ActivityKind.label, "removed label", label.name)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def add_reply(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: str,
    actor: User,
) -> Conversation:
    """Append an agent reply, updating the denormalized list fields."""
    conversation = await get_conversation(session, workspace_id, conversation_id)
    trimmed = body.strip()
    if not trimmed:
        raise Invalid("A reply needs a body.")

    now = datetime.now(UTC)
    session.add(
        Message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            role=MessageRole.agent,
            author_name=actor.name,
            author_user_id=actor.id,
            to_address=conversation.contact.email,
            body=trimmed,
            sent_at=now,
        )
    )
    conversation.preview = trimmed
    conversation.last_message_at = now
    conversation.unread = False

    await session.execute(
        sa.delete(Draft).where(Draft.conversation_id == conversation.id)
    )
    record(
        session, conversation, actor, ActivityKind.reply,
        "replied to", conversation.contact.name,
    )
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def discard_draft(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> None:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    await session.execute(sa.delete(Draft).where(Draft.conversation_id == conversation.id))
    await session.commit()
```

Add the imports these need at the top of the file: `from datetime import UTC, datetime`, and `ActivityKind`, `Label`, `MessageRole`, `Priority`, `User` from `relaydesk.models`, plus `Invalid` from `relaydesk.errors`.

Note the `session.refresh(conversation)` after label and assignee changes: the `selectin` relationships are already loaded, so without a refresh the response would serialize the pre-change value.

- [ ] **Step 4: Add the mutation routes**

Add to `apps/api/src/relaydesk/schemas/conversation.py`:

```python
class ConversationPatch(CamelModel):
    status: str | None = None
    priority: str | None = None
    assignee_id: str | None = None


class BulkStatusRequest(CamelModel):
    ids: list[str]
    status: str


class ReplyRequest(CamelModel):
    body: str
    resolve: bool = False


class LabelCreate(CamelModel):
    name: str
```

`ConversationPatch` cannot distinguish "assigneeId omitted" from "assigneeId set to null" with a plain `str | None`. Use `model_fields_set` in the route to tell them apart:

```python
@router.patch("/{conversation_id}", response_model=ConversationOut)
async def patch_conversation(
    conversation_id: uuid.UUID, payload: ConversationPatch, scope: Scope, session: DbSession
) -> ConversationOut:
    conversation = None
    if payload.status is not None:
        conversation = await conversations.set_status(
            session, scope.workspace_id, conversation_id,
            ConversationStatus(payload.status), scope.user,
        )
    if payload.priority is not None:
        conversation = await conversations.set_priority(
            session, scope.workspace_id, conversation_id,
            Priority(payload.priority), scope.user,
        )
    if "assignee_id" in payload.model_fields_set:
        assignee_id = uuid.UUID(payload.assignee_id) if payload.assignee_id else None
        conversation = await conversations.set_assignee(
            session, scope.workspace_id, conversation_id, assignee_id, scope.user
        )
    if conversation is None:
        conversation = await conversations.get_conversation(
            session, scope.workspace_id, conversation_id
        )
    return conversation_out(conversation, scope.workspace.timezone)
```

Add `POST /bulk-status` (204, looping `set_status`), `POST /{id}/replies` (201, calling `add_reply` then `set_status` to resolved when `resolve` is true), `DELETE /{id}/draft` (204), and `PUT` / `DELETE /{id}/labels/{label_id}` (200, returning the updated conversation).

Declare `/bulk-status` before `/{conversation_id}` for the same reason as `/counts`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/ -v`
Expected: PASS — nine mutation tests plus everything earlier.

- [ ] **Step 6: Rewire the server actions**

Replace the body of `apps/web/app/(console)/conversations/actions.ts`:

```typescript
"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api/client";
import { createLabel } from "@/lib/api/labels";
import type { ConversationStatus, Label, Priority } from "@/lib/types";

/** Every mutation touches sidebar counts too, so the whole console refreshes. */
function refresh() {
  revalidatePath("/", "layout");
}

export async function setStatusAction(id: string, status: ConversationStatus) {
  await apiFetch(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
  refresh();
}

export async function setStatusBulkAction(ids: string[], status: ConversationStatus) {
  await apiFetch("/conversations/bulk-status", {
    method: "POST",
    body: JSON.stringify({ ids, status }),
  });
  refresh();
}

export async function setPriorityAction(id: string, priority: Priority) {
  await apiFetch(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ priority }) });
  refresh();
}

export async function setAssigneeAction(id: string, assigneeId: string | null) {
  await apiFetch(`/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ assigneeId }),
  });
  refresh();
}

export async function addLabelAction(id: string, labelId: string) {
  await apiFetch(`/conversations/${id}/labels/${labelId}`, { method: "PUT" });
  refresh();
}

export async function removeLabelAction(id: string, labelId: string) {
  await apiFetch(`/conversations/${id}/labels/${labelId}`, { method: "DELETE" });
  refresh();
}

export async function createLabelAction(
  name: string,
  conversationId?: string,
): Promise<Label> {
  const label = await createLabel(name);
  if (conversationId) {
    await apiFetch(`/conversations/${conversationId}/labels/${label.id}`, { method: "PUT" });
  }
  refresh();
  return label;
}

export async function sendReplyAction(id: string, body: string, resolve: boolean) {
  const trimmed = body.trim();
  if (trimmed) {
    await apiFetch(`/conversations/${id}/replies`, {
      method: "POST",
      body: JSON.stringify({ body: trimmed, resolve }),
    });
  } else if (resolve) {
    await apiFetch(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "resolved" }),
    });
  }
  refresh();
}

export async function discardDraftAction(id: string) {
  await apiFetch(`/conversations/${id}/draft`, { method: "DELETE" });
  refresh();
}

/** No-op until slice 4 gives the agent a summarizer. */
export async function generateSummaryAction(_id: string) {
  return;
}
```

- [ ] **Step 7: Update the pickers to use ids**

`toggleLabelAction` is gone — split into `addLabelAction` / `removeLabelAction` so a retry is idempotent. In `apps/web/components/inbox/pickers.tsx`:

- Change the import to bring in `addLabelAction` and `removeLabelAction` instead of `toggleLabelAction`.
- In `LabelPicker`, change `onSelect={(id) => start(() => toggleLabelAction(conversationId, id))}` to:

```tsx
      onSelect={(id) =>
        start(() =>
          labelIds.includes(id)
            ? removeLabelAction(conversationId, id)
            : addLabelAction(conversationId, id),
        )
      }
```

using the `labelIds` prop the component already receives to decide the direction.

- In `AssigneePicker`, change the props to accept `assigneeId: string | null` alongside `assignee`, then change the two lines inside `team.map`:

```tsx
          id: member.id,
          ...
          selected: member.id === assigneeId,
```

Selecting by id rather than by display name is the point: two teammates can share a name, and an id cannot be ambiguous.

- Update `AssigneePicker`'s call sites in `components/inbox/conversation-header.tsx` and `components/inbox/details-sidebar.tsx` to pass `assigneeId={conversation.assigneeId}` in addition to the existing `assignee` prop.

- [ ] **Step 8: Verify in the browser**

With the conversation seeded in Task 8: change its status from the row's hover action and confirm the sidebar count moves; set a priority and an assignee from the details sidebar and confirm both appear in the activity timeline with the right wording; add and remove a label; send a reply with "Resolve" checked and confirm the message appears in the thread, the draft disappears, and the ticket moves to Resolved.

- [ ] **Step 9: Lint and commit**

```bash
docker compose exec api ruff check . && docker compose exec api pytest tests/ -v
docker compose exec web pnpm lint && docker compose exec web pnpm build
git add apps/api apps/web
git commit -m "feat: add inbox mutations with activity history"
```

---

### Task 10: Saved views

The sidebar's three views are hardcoded in the mock. They become stored filter definitions the API applies, so the list query stays on the server.

**Files:**
- Create: `apps/api/src/relaydesk/services/views.py`
- Create: `apps/api/src/relaydesk/api/views.py`
- Modify: `apps/api/src/relaydesk/api/{router,conversations}.py`
- Modify: `apps/web/lib/api/views.ts` (replacing the Task 8 stub)
- Modify: `apps/web/app/(console)/layout.tsx`, `apps/web/components/console/sidebar.tsx`
- Test: `apps/api/tests/test_saved_views.py`

**Interfaces:**
- Consumes: `SavedView`, `list_conversations`, `Scope`.
- Produces: `services.views.{list_views, get_view, apply_view}`; `GET /views -> [{id, name, count}]`; `getViews()` in `lib/api/views.ts`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_saved_views.py`:

```python
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ConversationStatus, Priority, SavedView
from tests.factories import make_conversation, make_member, make_workspace, sign_in


async def test_views_report_their_counts(client: AsyncClient, db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, priority=Priority.urgent)
    await make_conversation(db_session, workspace, assignee=user, priority=Priority.low)
    await make_conversation(db_session, workspace, status=ConversationStatus.pending)
    db_session.add_all(
        [
            SavedView(
                workspace_id=workspace.id,
                name="Urgent & unassigned",
                filters={"priority": "urgent", "assignee": "unassigned", "status": "open"},
                position=0,
            ),
            SavedView(
                workspace_id=workspace.id,
                name="Assigned to me",
                filters={"assignee": "me"},
                position=1,
            ),
            SavedView(
                workspace_id=workspace.id,
                name="Waiting on customer",
                filters={"status": "pending"},
                position=2,
            ),
        ]
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    body = (await client.get("/api/views", headers=headers)).json()

    counts = {entry["name"]: entry["count"] for entry in body}
    assert counts["Urgent & unassigned"] == 1
    assert counts["Assigned to me"] == 1
    assert counts["Waiting on customer"] == 1


async def test_listing_by_view_applies_its_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, priority=Priority.urgent)
    await make_conversation(db_session, workspace, assignee=user, priority=Priority.low)
    view = SavedView(
        workspace_id=workspace.id,
        name="Urgent & unassigned",
        filters={"priority": "urgent", "assignee": "unassigned", "status": "open"},
    )
    db_session.add(view)
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    body = (await client.get(f"/api/conversations?viewId={view.id}", headers=headers)).json()

    assert len(body["items"]) == 1
    assert body["items"][0]["priority"] == "urgent"


async def test_a_foreign_view_is_a_404(client: AsyncClient, db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    other = await make_workspace(db_session, slug="northwind")
    view = SavedView(workspace_id=other.id, name="Theirs", filters={})
    db_session.add(view)
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    response = await client.get(f"/api/conversations?viewId={view.id}", headers=headers)

    assert response.status_code == 404
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_saved_views.py -v`
Expected: FAIL — `GET /api/views` 404s.

- [ ] **Step 3: Implement the views service**

Create `apps/api/src/relaydesk/services/views.py`:

```python
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models import Conversation, ConversationStatus, Priority, SavedView, User


async def list_views(session: AsyncSession, workspace_id: uuid.UUID) -> list[SavedView]:
    return list(
        await session.scalars(
            sa.select(SavedView)
            .where(SavedView.workspace_id == workspace_id)
            .order_by(SavedView.position, SavedView.name)
        )
    )


async def get_view(
    session: AsyncSession, workspace_id: uuid.UUID, view_id: uuid.UUID
) -> SavedView:
    view = await session.scalar(
        sa.select(SavedView).where(
            SavedView.id == view_id, SavedView.workspace_id == workspace_id
        )
    )
    if view is None:
        raise NotFound("View not found.")
    return view


def apply_view(query: sa.Select, view: SavedView, viewer: User) -> sa.Select:
    """Narrow a conversation query by a stored filter definition.

    Filters are a small closed vocabulary rather than arbitrary SQL, so a
    stored view can never widen its own scope beyond the workspace.
    """
    filters = view.filters or {}

    status = filters.get("status")
    if status:
        query = query.where(Conversation.status == ConversationStatus(status))
    else:
        query = query.where(Conversation.status != ConversationStatus.trash)

    priority = filters.get("priority")
    if priority:
        query = query.where(Conversation.priority == Priority(priority))

    assignee = filters.get("assignee")
    if assignee == "unassigned":
        query = query.where(Conversation.assignee_id.is_(None))
    elif assignee == "me":
        query = query.where(Conversation.assignee_id == viewer.id)

    return query


async def count_for_view(
    session: AsyncSession, workspace_id: uuid.UUID, view: SavedView, viewer: User
) -> int:
    query = sa.select(Conversation.id).where(Conversation.workspace_id == workspace_id)
    query = apply_view(query, view, viewer)
    return (
        await session.scalar(sa.select(sa.func.count()).select_from(query.subquery()))
    ) or 0
```

- [ ] **Step 4: Wire the view filter into the list endpoint**

In `services/conversations.py`, add a `view: SavedView | None = None` and `viewer: User | None = None` parameter to `list_conversations`, and immediately after the base `query` is built:

```python
    if view is not None and viewer is not None:
        from relaydesk.services.views import apply_view

        query = apply_view(query, view, viewer)
```

The import is local to avoid a cycle: `views.py` already imports nothing from `conversations.py`, but keeping it inside the function documents that the dependency runs one way only.

In `api/conversations.py`, when the request carries `viewId`, resolve it with `views.get_view` first (which raises `NotFound` for a foreign id) and pass it through.

- [ ] **Step 5: Add the views router**

Create `apps/api/src/relaydesk/api/views.py`:

```python
from fastapi import APIRouter

from relaydesk.api.deps import DbSession, Scope
from relaydesk.schemas.base import CamelModel
from relaydesk.services import views

router = APIRouter()


class SavedViewOut(CamelModel):
    id: str
    name: str
    count: int


@router.get("", response_model=list[SavedViewOut])
async def list_saved_views(scope: Scope, session: DbSession) -> list[SavedViewOut]:
    rows = await views.list_views(session, scope.workspace_id)
    return [
        SavedViewOut(
            id=str(view.id),
            name=view.name,
            count=await views.count_for_view(session, scope.workspace_id, view, scope.user),
        )
        for view in rows
    ]
```

Mount it: `api_router.include_router(views_router, prefix="/views", tags=["inbox"])`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/ -v`
Expected: PASS — three view tests plus everything earlier.

- [ ] **Step 7: Replace the web stub and pass views as a prop**

Replace `apps/web/lib/api/views.ts`:

```typescript
import "server-only";

import { apiFetch } from "@/lib/api/client";
import type { SavedView } from "@/lib/types";

export async function getViews(): Promise<SavedView[]> {
  return apiFetch<SavedView[]>("/views");
}
```

In `apps/web/components/console/sidebar.tsx`, delete the local `savedViews` constant added in Task 8 and add `savedViews` to the component's props:

```typescript
export function Sidebar({
  statusCounts,
  draftCount,
  setupTasks,
  labels,
  savedViews,
}: {
  statusCounts: StatusCount[];
  draftCount: number;
  setupTasks: SetupTask[];
  labels: Label[];
  savedViews: SavedView[];
}) {
```

The sidebar is a client component and cannot await, which is exactly why this arrives as a prop rather than an import.

In `apps/web/app/(console)/layout.tsx`, add `getViews()` to the `Promise.all` and pass `savedViews={savedViews}` to `<Sidebar />`.

- [ ] **Step 8: Verify and commit**

In the browser: the sidebar's saved views render with live counts, and clicking one filters the list. Then:

```bash
docker compose exec api ruff check . && docker compose exec api pytest tests/ -v
docker compose exec web pnpm lint && docker compose exec web pnpm build
git add apps/api apps/web
git commit -m "feat: add saved views backed by stored filters"
```

---

### Task 11: Seed, bootstrap, and documentation

Closes the slice: a fresh clone shows a populated console, a self-hoster has a supported way to create their first workspace, and migrations run on container start.

**Files:**
- Create: `apps/api/src/relaydesk/cli.py`
- Create: `apps/api/tests/test_cli.py`
- Modify: `apps/api/pyproject.toml`, `apps/api/Dockerfile`
- Modify: `Makefile`, `README.md`, `.env.example`
- Test: `apps/api/tests/test_cli.py`

**Interfaces:**
- Consumes: every model, `hash_password`.
- Produces: `seed(session) -> None`, `bootstrap(session, workspace_name, admin_email, admin_name, admin_password) -> None`; console script `relaydesk`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_cli.py`:

```python
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.cli import bootstrap, seed
from relaydesk.models import Conversation, Label, Membership, SavedView, User, Workspace


async def test_seed_creates_a_demo_workspace(db_session: AsyncSession) -> None:
    await seed(db_session)

    workspace = await db_session.scalar(sa.select(Workspace).where(Workspace.slug == "chronon"))
    conversations = (await db_session.scalars(sa.select(Conversation))).all()
    labels = (await db_session.scalars(sa.select(Label))).all()
    views = (await db_session.scalars(sa.select(SavedView))).all()

    assert workspace is not None
    assert len(conversations) == 11
    assert len(labels) == 4
    assert len(views) == 3
    assert workspace.conversation_seq == 11


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed(db_session)
    await seed(db_session)

    workspaces = (await db_session.scalars(sa.select(Workspace))).all()
    conversations = (await db_session.scalars(sa.select(Conversation))).all()

    assert len(workspaces) == 1
    assert len(conversations) == 11


async def test_bootstrap_creates_a_workspace_and_admin(db_session: AsyncSession) -> None:
    await bootstrap(
        db_session,
        workspace_name="Acme Support",
        admin_email="owner@acme.com",
        admin_name="Ada Owner",
        admin_password="a-real-password",
    )

    user = await db_session.scalar(sa.select(User).where(User.email == "owner@acme.com"))
    membership = await db_session.scalar(sa.select(Membership))
    conversations = (await db_session.scalars(sa.select(Conversation))).all()

    assert user is not None and user.password_hash is not None
    assert membership is not None and membership.role.value == "admin"
    assert conversations == []


async def test_bootstrap_refuses_to_run_twice(db_session: AsyncSession) -> None:
    kwargs = dict(
        workspace_name="Acme Support",
        admin_email="owner@acme.com",
        admin_name="Ada Owner",
        admin_password="a-real-password",
    )
    await bootstrap(db_session, **kwargs)

    from relaydesk.errors import Conflict

    try:
        await bootstrap(db_session, **kwargs)
    except Conflict:
        return
    raise AssertionError("expected bootstrap to refuse a second workspace")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_cli.py -v`
Expected: FAIL — `No module named 'relaydesk.cli'`.

- [ ] **Step 3: Implement the CLI**

Create `apps/api/src/relaydesk/cli.py`. It exposes two async functions plus an `argparse` entry point:

```python
"""Operational commands.

``seed`` fills a development database with the demo workspace the console
was designed against. ``bootstrap`` is what a self-hoster runs once to
create their real workspace and first admin.
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.db.session import async_session_factory
from relaydesk.errors import Conflict
from relaydesk.models import (
    Channel,
    Contact,
    Conversation,
    ConversationLabel,
    ConversationStatus,
    Draft,
    Label,
    LabelColor,
    Membership,
    MembershipStatus,
    Message,
    MessageRole,
    Priority,
    Role,
    SavedView,
    User,
    Workspace,
)
from relaydesk.security.passwords import hash_password
```

Define the demo data as a module-level list. The first nine rows are the ones
`lib/mock/conversations.ts` held, verbatim, so the seeded console matches the
design the frontend was built against; the last two exist only so the `ignored`
and `trash` sidebar counts are non-zero, which the mock never covered.

```python
# (subject, preview, contact_name, contact_email, channel, status, priority,
#  assignee: "admin" | "agent" | None, label_names, has_draft, minutes_ago)
DEMO_CONVERSATIONS = [
    ("Checkout fails with a 402 on annual plans",
     "Hey — every time I try to switch our workspace to annual billing the payment "
     "step returns a 402. Card works fine elsewhere.",
     "Priya Raman", "priya@northwind.io", Channel.email, ConversationStatus.open,
     Priority.urgent, None, ["Billing", "Bug"], True, 12),
    ("How do I invite a read-only teammate?",
     "We want our finance lead to see invoices but not touch tickets. Is there a viewer role?",
     "Marcus Webb", "marcus@lattice-labs.com", Channel.portal, ConversationStatus.open,
     Priority.medium, "admin", ["Onboarding"], True, 48),
    ("Discord bot stopped creating tickets last night",
     "Our forum channel was quiet in Relaydesk since about 23:00 UTC but there are "
     "definitely new threads.",
     "Ida Okonkwo", "ida@parsecgg.com", Channel.discord, ConversationStatus.open,
     Priority.high, "agent", ["Bug"], False, 180),
    ("Request: bulk export of resolved tickets",
     "Would love a CSV export so we can run our own reporting on resolution times.",
     "Tomas Lind", "tomas@heliossoft.se", Channel.email, ConversationStatus.open,
     Priority.low, None, ["Feature request"], False, 300),
    ("Refund for duplicate October charge",
     "We were billed twice on 3 Oct. Invoice numbers are INV-2291 and INV-2292.",
     "Grace Whitfield", "grace@bellcurve.app", Channel.email, ConversationStatus.pending,
     Priority.high, "admin", ["Billing"], False, 1440),
    ("SAML metadata URL is rejected",
     "Okta gives us a metadata URL, but the field seems to want raw XML.",
     "Devon Ruiz", "devon@quorumhq.com", Channel.api, ConversationStatus.pending,
     Priority.medium, "agent", [], True, 1500),
    ("Thanks — webhook signing sorted",
     "Rotating the secret did it. Appreciate the quick turnaround.",
     "Aiko Tanaka", "aiko@driftline.jp", Channel.email, ConversationStatus.resolved,
     Priority.low, "admin", [], False, 2880),
    ("Password reset email never arrives",
     "Three of our users tried the reset link this morning and nothing landed, "
     "spam folder included.",
     "Owen Pryce", "owen@caldera.dev", Channel.portal, ConversationStatus.resolved,
     Priority.medium, "agent", ["Bug"], False, 4320),
    ("Waiting on legal review of the DPA",
     "Our counsel is reviewing the data processing agreement. Nothing needed from "
     "you until they come back.",
     "Helena Marsh", "helena@ridgeway.co", Channel.email, ConversationStatus.on_hold,
     Priority.low, "admin", [], False, 8640),
    ("Partnership opportunity for your team",
     "I help SaaS companies triple their pipeline. Do you have 15 minutes this week?",
     "Dana Voss", "dana@growthmail.biz", Channel.email, ConversationStatus.ignored,
     Priority.low, None, [], False, 5760),
    ("test test test",
     "ignore this, testing the form",
     "Sam Rowe", "sam@example.com", Channel.portal, ConversationStatus.trash,
     Priority.low, None, [], False, 11520),
]
```

```python
async def seed(session: AsyncSession) -> None:
    """Idempotent: re-running leaves exactly one demo workspace."""
    existing = await session.scalar(sa.select(Workspace).where(Workspace.slug == "chronon"))
    if existing is not None:
        return

    workspace = Workspace(
        name="Chronon", slug="chronon", monogram="CH", timezone="Asia/Kolkata",
        plan="Starter", trial_days_left=6, tickets_this_period=412, projected_tickets=480,
    )
    session.add(workspace)
    await session.flush()

    admin = User(
        email="nilesh@relaydesk.dev", name="Nilesh Pant", monogram="NP",
        timezone="Asia/Kolkata", password_hash=hash_password("relaydesk"),
    )
    agent = User(
        email="sara@relaydesk.dev", name="Sara Duval", monogram="SD",
        password_hash=hash_password("relaydesk"),
    )
    session.add_all([admin, agent])
    await session.flush()
    session.add_all(
        [
            Membership(workspace_id=workspace.id, user_id=admin.id, role=Role.admin,
                       status=MembershipStatus.active),
            Membership(workspace_id=workspace.id, user_id=agent.id, role=Role.agent,
                       status=MembershipStatus.active),
        ]
    )

    labels = {
        name: Label(workspace_id=workspace.id, name=name, color=color)
        for name, color in [
            ("Billing", LabelColor.amber),
            ("Bug", LabelColor.rose),
            ("Onboarding", LabelColor.citron),
            ("Feature request", LabelColor.sky),
        ]
    }
    session.add_all(labels.values())

    session.add_all(
        [
            SavedView(workspace_id=workspace.id, name="Urgent & unassigned", position=0,
                      filters={"priority": "urgent", "assignee": "unassigned", "status": "open"}),
            SavedView(workspace_id=workspace.id, name="Assigned to me", position=1,
                      filters={"assignee": "me"}),
            SavedView(workspace_id=workspace.id, name="Waiting on customer", position=2,
                      filters={"status": "pending"}),
        ]
    )
    await session.flush()

    people = {"admin": admin, "agent": agent, None: None}
    now = datetime.now(UTC)

    for (
        subject, preview, contact_name, contact_email, channel, status, priority,
        assignee_key, label_names, has_draft, minutes_ago,
    ) in DEMO_CONVERSATIONS:
        contact = Contact(
            workspace_id=workspace.id, email=contact_email, name=contact_name
        )
        session.add(contact)
        await session.flush()

        workspace.conversation_seq += 1
        sent_at = now - timedelta(minutes=minutes_ago)
        assignee = people[assignee_key]
        conversation = Conversation(
            workspace_id=workspace.id,
            number=workspace.conversation_seq,
            subject=subject,
            contact_id=contact.id,
            channel=channel,
            status=status,
            priority=priority,
            assignee_id=assignee.id if assignee else None,
            preview=preview,
            last_message_at=sent_at,
            unread=status is ConversationStatus.open,
        )
        session.add(conversation)
        await session.flush()

        session.add(
            Message(
                workspace_id=workspace.id,
                conversation_id=conversation.id,
                role=MessageRole.customer,
                author_name=contact_name,
                to_address="support@chronon.co",
                body=preview,
                sent_at=sent_at,
            )
        )
        for label_name in label_names:
            session.add(
                ConversationLabel(
                    conversation_id=conversation.id, label_id=labels[label_name].id
                )
            )
        if has_draft:
            first_name = contact_name.split()[0]
            session.add(
                Draft(
                    workspace_id=workspace.id,
                    conversation_id=conversation.id,
                    body=(
                        f"Hi {first_name},\n\nSorry to hear you're running into "
                        "trouble. Could you share a bit more detail so I can look "
                        "into this?\n\nThanks,\nRelaydesk Support"
                    ),
                )
            )

    await session.commit()


async def bootstrap(
    session: AsyncSession,
    workspace_name: str,
    admin_email: str,
    admin_name: str,
    admin_password: str,
) -> None:
    """Create the first workspace and its admin. Refuses if one exists."""
    existing = await session.scalar(sa.select(Workspace).limit(1))
    if existing is not None:
        raise Conflict("A workspace already exists; bootstrap is a one-time command.")

    slug = "".join(c if c.isalnum() else "-" for c in workspace_name.lower()).strip("-")
    workspace = Workspace(
        name=workspace_name,
        slug=slug or "workspace",
        monogram="".join(part[0] for part in workspace_name.split()[:2]).upper() or "WS",
    )
    user = User(
        email=admin_email,
        name=admin_name,
        monogram="".join(part[0] for part in admin_name.split()[:2]).upper() or "AD",
        password_hash=hash_password(admin_password),
    )
    session.add_all([workspace, user])
    await session.flush()
    session.add(
        Membership(workspace_id=workspace.id, user_id=user.id, role=Role.admin,
                   status=MembershipStatus.active)
    )
    await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(prog="relaydesk")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="Fill the database with demo data")
    boot = commands.add_parser("bootstrap", help="Create the first workspace and admin")
    boot.add_argument("--workspace", required=True)
    boot.add_argument("--email", required=True)
    boot.add_argument("--name", required=True)
    boot.add_argument("--password", required=True)
    args = parser.parse_args()

    async def run() -> None:
        async with async_session_factory() as session:
            if args.command == "seed":
                await seed(session)
            else:
                await bootstrap(
                    session,
                    workspace_name=args.workspace,
                    admin_email=args.email,
                    admin_name=args.name,
                    admin_password=args.password,
                )

    asyncio.run(run())


if __name__ == "__main__":
    main()
```

Register the console script in `apps/api/pyproject.toml`:

```toml
[project.scripts]
relaydesk = "relaydesk.cli:main"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/ -v`
Expected: PASS — four CLI tests plus everything earlier.

- [ ] **Step 5: Run migrations on container start**

Replace the `CMD` line in `apps/api/Dockerfile`:

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn relaydesk.main:app --host 0.0.0.0 --port 8000 --reload"]
```

Add to the `Makefile`:

```make
.PHONY: dev down logs clean seed migrate revision

seed:
	docker compose exec api relaydesk seed

migrate:
	docker compose exec api alembic upgrade head

revision:
	docker compose exec api alembic revision --autogenerate -m "$(m)"
```

- [ ] **Step 6: Update the README**

Replace the "Project status" paragraph, which currently says product functionality has not been implemented, with an accurate description: workspaces, sign-in, team invites, and the ticket inbox are implemented; channels, AI, knowledge base, analytics, and billing are not yet.

Add a "Demo data" section after Start:

````markdown
## Demo data

```sh
make seed
```

Seeds a demo workspace with two users, four labels, and eleven tickets across
every status. Sign in as `nilesh@relaydesk.dev` with the password `relaydesk`.

## Self-hosting your own workspace

```sh
docker compose exec api relaydesk bootstrap \
  --workspace "Acme Support" \
  --email you@acme.com \
  --name "Your Name" \
  --password "a-strong-password"
```
````

Also add `make migrate` and `make revision m="..."` to the Development commands list.

- [ ] **Step 7: End-to-end verification from a clean slate**

```bash
make clean
make dev          # wait for the stack to come up
make seed
```

Then in a browser: sign in as `nilesh@relaydesk.dev` / `relaydesk`; confirm the inbox shows eleven tickets across every status, the sidebar counts and saved-view counts are non-zero, two tickets show a draft indicator, the details sidebar shows an empty summary with no error, Settings → Team lists both users, and signing out returns you to `/login` and blocks `/conversations`.

- [ ] **Step 8: Commit**

```bash
docker compose exec api ruff check . && docker compose exec api pytest tests/ -v
docker compose exec web pnpm lint && docker compose exec web pnpm build
git add apps/api Makefile README.md .env.example
git commit -m "feat: add seed and bootstrap commands, run migrations on start"
```

---

## Definition of done

- `docker compose exec api pytest` is green, including `test_tenant_isolation.py`.
- `docker compose exec api ruff check .` is clean.
- `docker compose exec web pnpm lint` and `pnpm build` are clean.
- A clean `make clean && make dev && make seed` produces a console that looks like the mock-driven one did, backed entirely by Postgres.
- `grep -rn "lib/mock/conversations" apps/web` returns nothing.
- The only remaining files under `apps/web/lib/mock/` are `types.ts` (a re-export), `workspace.ts` (only `getPortalSettings`), `settings.ts` (without `getTeam`), `analytics.ts`, and `knowledge-base.ts` — all belonging to later slices.
