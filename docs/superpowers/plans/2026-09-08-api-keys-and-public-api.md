# API keys & the public v1 API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a workspace mint a scoped API key and drive its own inbox from outside the console through a stable, versioned public API at `/v1`.

**Architecture:** A key is a machine principal owned by the workspace, resolved by a dependency that is entirely separate from the console's session-based `WorkspaceScope`. Both surfaces meet only at the service layer, through a new `Actor` value object that replaces the `User` argument the conversation services take today. The public surface gets its own router and its own snake_case schemas so the console's response shapes never become a third-party contract.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async, `asyncpg`), Alembic, Pydantic v2, pytest (`asyncio_mode = "auto"`), Postgres 16, Next.js App Router (React Server Components + server actions).

**Spec:** `docs/superpowers/specs/2026-09-08-api-keys-and-public-api-design.md`

## Global Constraints

Every task's requirements implicitly include this section. Values are copied verbatim from the spec.

- **One token prefix, `rd_`.** No `rd_live_` / `rd_test_` split (spec D9). Both `apps/web/lib/mock/settings.ts` and `apps/web/components/settings/code-sample.tsx` are corrected to match.
- **v1 mounts at `/v1`, not `/api/v1`** (spec D7). `/api` stays the console's private surface.
- **v1 schemas are snake_case.** They do **not** inherit `CamelModel` (spec D6). No derived display fields (`age`, `date`, `has_draft`). Timestamps are ISO-8601 with an offset.
- **`WorkspaceScope` is not modified** (spec D2). `workspace_scope` stays session-only, `WorkspaceScope.user` stays non-null.
- **Six scopes, closed set** (spec D5): `conversations:read`, `conversations:write`, `messages:write`, `contacts:read`, `labels:read`, `labels:write`. A write scope does not imply its read scope.
- **Error envelope unchanged:** `{"error": {"code": ..., "message": ...}}`.
- **Cross-workspace access answers `404`, never `403`.** Slice-1 isolation contract.
- **Rate limit:** `api_key_rate_limit_per_minute`, default `120`, in `config.Settings`.
- **`metadata` cap:** 8192 bytes serialised, 50 top-level keys, enforced at the schema edge.
- **Migrations are sequential, zero-padded, starting at `0015`.** One `revision`/`down_revision` chain, no branches. Every migration carries a prose docstring explaining *why*, matching `0012_rate_limits.py` and `0014_password_resets.py`.
- **Python 3.12**, ruff `select = ["E", "F", "I", "UP", "B"]`, line length 88.
- **All commands run inside the compose stack.** Tests: `docker compose exec api pytest -m "not integration"`. Lint: `docker compose exec api ruff check .`. Web: `docker compose exec web pnpm lint` and `docker compose exec web pnpm build`.

## File Structure

**API — created**

| File | Responsibility |
|---|---|
| `apps/api/src/relaydesk/models/api_key.py` | `ApiKey` model and the `ApiKeyScope` enum |
| `apps/api/src/relaydesk/models/api_usage.py` | `ApiKeyUsage`, the per-key fixed-window counter |
| `apps/api/src/relaydesk/services/api_keys.py` | Mint, resolve, list, revoke. The only place a token is generated or hashed |
| `apps/api/src/relaydesk/services/api_usage.py` | Charge one call against a key's window; sweep old windows |
| `apps/api/src/relaydesk/services/actors.py` | `Actor` — the principal a service attributes a change to |
| `apps/api/src/relaydesk/api/v1/__init__.py` | Package marker |
| `apps/api/src/relaydesk/api/v1/deps.py` | Key authentication, scope enforcement, rate-limit charge and headers |
| `apps/api/src/relaydesk/api/v1/router.py` | Assembles the v1 router |
| `apps/api/src/relaydesk/api/v1/conversations.py` | Conversation and message endpoints |
| `apps/api/src/relaydesk/api/v1/labels.py` | Label endpoints |
| `apps/api/src/relaydesk/api/v1/contacts.py` | Contact endpoints |
| `apps/api/src/relaydesk/api/api_keys.py` | Console-side key management (session-authenticated, admin only) |
| `apps/api/src/relaydesk/schemas/v1.py` | Every public request and response shape |
| `apps/api/src/relaydesk/schemas/api_key.py` | Console-side key schemas |
| `apps/api/migrations/versions/0015_api_keys.py` | `api_keys` table |
| `apps/api/migrations/versions/0016_actor_api_keys.py` | `actor_api_key_id` / `author_api_key_id` columns |
| `apps/api/migrations/versions/0017_api_key_usage.py` | `api_key_usage` table |
| `apps/api/migrations/versions/0018_conversation_external_id.py` | `conversations.external_id` and `conversations.metadata` |

**API — modified**

| File | Change |
|---|---|
| `models/__init__.py` | Register the new models |
| `models/activity.py` | `actor_api_key_id` column |
| `models/message.py` | `author_api_key_id` column |
| `services/conversations.py` | `actor: User` → `actor: Actor` |
| `services/notifications.py` | `notify_assignment` takes an `Actor` |
| `api/conversations.py` | Wrap `scope.user` in `Actor.for_user` |
| `api/router.py` | Mount the console key router |
| `errors.py` | `AppError` carries optional response headers |
| `main.py` | Mount `/v1`; pass error headers through |
| `config.py` | `api_key_rate_limit_per_minute` |
| `worker/app.py`, `worker/tasks/ratelimit.py` | Sweep old usage windows |

**Web — modified**

| File | Change |
|---|---|
| `apps/web/lib/api/api-keys.ts` (create) | Typed calls to `/api/api-keys` |
| `apps/web/app/(console)/settings/api-keys/actions.ts` (create) | Server actions for create and revoke |
| `apps/web/app/(console)/settings/api-keys/page.tsx` | Read real keys instead of the mock |
| `apps/web/components/settings/api-key-dialog.tsx` | Scope picker; show the secret once |
| `apps/web/components/settings/api-key-actions.tsx` (create) | Per-row revoke control |
| `apps/web/components/settings/code-sample.tsx` | `rd_live_` → `rd_` |
| `apps/web/lib/types.ts` | Extend `ApiKey`; add `ApiKeyScope` |
| `apps/web/lib/mock/settings.ts` | Drop `apiKeys` and `getApiKeys` |

---

### Task 1: The `ApiKey` model

**Files:**
- Create: `apps/api/src/relaydesk/models/api_key.py`
- Create: `apps/api/migrations/versions/0015_api_keys.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Test: `apps/api/tests/test_api_key_model.py`

**Interfaces:**
- Consumes: `relaydesk.db.base.Base`, `UUIDMixin`, `TimestampMixin`; `tests.factories.make_workspace`, `make_member`.
- Produces: `relaydesk.models.ApiKey` with columns `workspace_id`, `name`, `prefix`, `token_hash`, `scopes: list[str]`, `created_by_user_id`, `last_used_at`, `expires_at`, `revoked_at`; and `relaydesk.models.ApiKeyScope`, a `StrEnum` whose members are `conversations_read`, `conversations_write`, `messages_write`, `contacts_read`, `labels_read`, `labels_write` with `resource:action` values.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_api_key_model.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.models import ApiKey, ApiKeyScope
from tests.factories import make_member, make_workspace


async def test_a_key_round_trips_its_scopes(db_session) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    key = ApiKey(
        workspace_id=workspace.id,
        name="Production ingest",
        prefix="rd_7f2a",
        token_hash="a" * 64,
        scopes=[
            ApiKeyScope.conversations_read.value,
            ApiKeyScope.messages_write.value,
        ],
        created_by_user_id=user.id,
    )
    db_session.add(key)
    await db_session.commit()

    stored = await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))

    assert stored.scopes == ["conversations:read", "messages:write"]
    assert stored.revoked_at is None
    assert stored.expires_at is None
    assert stored.last_used_at is None


async def test_two_keys_cannot_share_a_token_hash(db_session) -> None:
    workspace = await make_workspace(db_session)
    db_session.add(
        ApiKey(
            workspace_id=workspace.id,
            name="First",
            prefix="rd_1111",
            token_hash="b" * 64,
            scopes=[],
        )
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                ApiKey(
                    workspace_id=workspace.id,
                    name="Second",
                    prefix="rd_2222",
                    token_hash="b" * 64,
                    scopes=[],
                )
            )
            await db_session.flush()


async def test_an_expiry_is_stored_with_its_offset(db_session) -> None:
    workspace = await make_workspace(db_session)
    expires = datetime.now(UTC) + timedelta(days=30)
    key = ApiKey(
        workspace_id=workspace.id,
        name="Temporary",
        prefix="rd_3333",
        token_hash="c" * 64,
        scopes=[ApiKeyScope.conversations_read.value],
        expires_at=expires,
    )
    db_session.add(key)
    await db_session.commit()

    stored = await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))

    assert stored.expires_at.tzinfo is not None
    assert abs((stored.expires_at - expires).total_seconds()) < 1


def test_the_scope_set_is_exactly_the_six_the_spec_names() -> None:
    assert {scope.value for scope in ApiKeyScope} == {
        "conversations:read",
        "conversations:write",
        "messages:write",
        "contacts:read",
        "labels:read",
        "labels:write",
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_api_key_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'ApiKey' from 'relaydesk.models'`

- [ ] **Step 3: Write the model**

Create `apps/api/src/relaydesk/models/api_key.py`:

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class ApiKeyScope(enum.StrEnum):
    """What a key is allowed to do. A closed set; see spec D5.

    ``messages_write`` is deliberately not folded into
    ``conversations_write``: changing a status is internal bookkeeping,
    while sending a reply puts mail in a customer's inbox under the
    workspace's name. A triage integration should be able to hold the first
    without the second, and that is only expressible as a separate grant.
    """

    conversations_read = "conversations:read"
    conversations_write = "conversations:write"
    messages_write = "messages:write"
    contacts_read = "contacts:read"
    labels_read = "labels:read"
    labels_write = "labels:write"


class ApiKey(UUIDMixin, TimestampMixin, Base):
    """A machine principal belonging to a workspace, not to a user.

    Only ``token_hash`` persists; the plaintext exists once, in the response
    to the request that created it. ``prefix`` is display-only -- it is what
    the settings list shows so a human can tell two keys apart, and it is
    ``rd_`` plus the first four characters of the secret. Four characters of
    a 43-character token narrow nothing.

    ``created_by_user_id`` is ``SET NULL`` rather than ``CASCADE``: the key
    belongs to the workspace and must outlive the person who minted it (spec
    D1). Revocation sets ``revoked_at`` rather than deleting the row, so
    ``activity_events.actor_api_key_id`` keeps resolving to a name.
    """

    __tablename__ = "api_keys"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # A plain text array of ``ApiKeyScope`` values rather than an array of a
    # database enum. Every other enum column here is
    # ``Enum(..., native_enum=False, create_constraint=True)``, which is a
    # CHECK constraint over a scalar column and has no array equivalent that
    # Alembic autogenerates cleanly. Validation therefore lives at the
    # Pydantic edge and in ``services.api_keys.mint``, which is the only
    # writer.
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default="{}"
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 4: Register the model**

In `apps/api/src/relaydesk/models/__init__.py`, add the import in alphabetical position (after the `activity` import) and both names to `__all__`:

```python
from relaydesk.models.api_key import ApiKey, ApiKeyScope
```

`__all__` gains `"ApiKey"` and `"ApiKeyScope"`, placed alphabetically after `"ActivityKind"`.

- [ ] **Step 5: Write the migration**

Create `apps/api/migrations/versions/0015_api_keys.py`:

```python
"""api keys

Adds ``api_keys``, the first non-human principal in the product. Every
credential before this one belonged to a person: a session belongs to a
user, an invite and a password reset are addressed to a mailbox. A key
belongs to the *workspace*, which is why ``created_by_user_id`` is nullable
and ``SET NULL`` -- an integration must not stop working, or keep working
under a departed employee's name, because of an HR action.

``token_hash`` is unique and is all that persists; the plaintext exists only
in the response that created the key. ``prefix`` is display-only. A revoked
key keeps its row (``revoked_at``) rather than being deleted, so the
attribution columns added in 0016 keep resolving to a name.

``scopes`` is a plain text array rather than an array of a database enum:
the ``native_enum=False`` CHECK-constraint pattern used by every scalar enum
column in this schema has no array form, so the closed set is enforced at
the application edge instead.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-08 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.String(length=32)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_api_keys_workspace_id", "api_keys", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_api_keys_workspace_id", table_name="api_keys")
    op.drop_table("api_keys")
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_api_key_model.py -v`
Expected: PASS, 4 tests. The suite's `migrated_database` fixture drops and re-migrates the test database, so this also proves the migration runs.

- [ ] **Step 7: Verify the whole suite and lint still pass**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS, no lint findings.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/relaydesk/models/api_key.py \
        apps/api/src/relaydesk/models/__init__.py \
        apps/api/migrations/versions/0015_api_keys.py \
        apps/api/tests/test_api_key_model.py
git commit -m "feat(api): add the ApiKey model and its scope enum"
```

---

### Task 2: Minting and resolving keys

**Files:**
- Create: `apps/api/src/relaydesk/services/api_keys.py`
- Test: `apps/api/tests/test_api_keys_service.py`

**Interfaces:**
- Consumes: `relaydesk.models.ApiKey`, `ApiKeyScope` (Task 1); `relaydesk.security.tokens.generate_token`, `hash_token`; `relaydesk.errors.Unauthorized`, `NotFound`.
- Produces:
  - `mint(session, workspace_id: uuid.UUID, *, name: str, scopes: Sequence[ApiKeyScope], created_by_user_id: uuid.UUID | None, expires_at: datetime | None = None) -> tuple[str, ApiKey]` — returns `(plaintext_token, row)`.
  - `resolve(session, token: str) -> ApiKey` — raises `Unauthorized`.
  - `list_keys(session, workspace_id: uuid.UUID) -> list[ApiKey]`
  - `revoke(session, workspace_id: uuid.UUID, key_id: uuid.UUID) -> None` — raises `NotFound`.
  - `LAST_USED_INTERVAL: timedelta`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_api_keys_service.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from relaydesk.errors import NotFound, Unauthorized
from relaydesk.models import ApiKey, ApiKeyScope
from relaydesk.security.tokens import hash_token
from relaydesk.services import api_keys
from tests.factories import make_member, make_workspace


async def _mint(db_session, workspace, user=None, **kwargs):
    return await api_keys.mint(
        db_session,
        workspace.id,
        name=kwargs.pop("name", "Production ingest"),
        scopes=kwargs.pop("scopes", [ApiKeyScope.conversations_read]),
        created_by_user_id=user.id if user else None,
        **kwargs,
    )


async def test_mint_returns_a_prefixed_token_and_stores_only_its_hash(
    db_session,
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)

    token, key = await _mint(db_session, workspace, user)

    assert token.startswith("rd_")
    assert key.token_hash == hash_token(token)
    assert token not in (key.prefix, key.token_hash)
    # The prefix is "rd_" plus four characters of the secret.
    assert key.prefix == token[:7]
    assert key.scopes == ["conversations:read"]
    assert key.created_by_user_id == user.id


async def test_two_mints_never_produce_the_same_token(db_session) -> None:
    workspace = await make_workspace(db_session)

    first, _ = await _mint(db_session, workspace, name="One")
    second, _ = await _mint(db_session, workspace, name="Two")

    assert first != second


async def test_resolve_finds_a_live_key(db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await _mint(db_session, workspace)

    resolved = await api_keys.resolve(db_session, token)

    assert resolved.id == key.id


async def test_resolve_refuses_an_unknown_token(db_session) -> None:
    with pytest.raises(Unauthorized):
        await api_keys.resolve(db_session, "rd_nothing-was-ever-minted-here")


async def test_resolve_refuses_a_revoked_key(db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await _mint(db_session, workspace)
    key.revoked_at = datetime.now(UTC)
    await db_session.commit()

    with pytest.raises(Unauthorized):
        await api_keys.resolve(db_session, token)


async def test_resolve_refuses_an_expired_key(db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await _mint(
        db_session, workspace, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )

    with pytest.raises(Unauthorized):
        await api_keys.resolve(db_session, token)


async def test_resolve_stamps_last_used_once_per_interval(db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await _mint(db_session, workspace)

    await api_keys.resolve(db_session, token)
    first = (
        await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))
    ).last_used_at
    assert first is not None

    await api_keys.resolve(db_session, token)
    second = (
        await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))
    ).last_used_at
    assert second == first

    key.last_used_at = datetime.now(UTC) - api_keys.LAST_USED_INTERVAL * 2
    await db_session.commit()
    await api_keys.resolve(db_session, token)
    third = (
        await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))
    ).last_used_at
    assert third > first


async def test_list_keys_returns_only_this_workspaces_keys(db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    await _mint(db_session, ours, name="Ours")
    await _mint(db_session, theirs, name="Theirs")

    rows = await api_keys.list_keys(db_session, ours.id)

    assert [row.name for row in rows] == ["Ours"]


async def test_revoke_marks_the_row_rather_than_deleting_it(db_session) -> None:
    workspace = await make_workspace(db_session)
    _, key = await _mint(db_session, workspace)

    await api_keys.revoke(db_session, workspace.id, key.id)

    stored = await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))
    assert stored is not None
    assert stored.revoked_at is not None


async def test_revoke_cannot_reach_another_workspaces_key(db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    _, key = await _mint(db_session, theirs)

    with pytest.raises(NotFound):
        await api_keys.revoke(db_session, ours.id, key.id)


async def test_mint_refuses_a_scope_outside_the_closed_set(db_session) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(ValueError):
        await api_keys.mint(
            db_session,
            workspace.id,
            name="Bad",
            scopes=["workspace:destroy"],
            created_by_user_id=None,
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_api_keys_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'api_keys' from 'relaydesk.services'`

- [ ] **Step 3: Write the service**

Create `apps/api/src/relaydesk/services/api_keys.py`:

```python
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound, Unauthorized
from relaydesk.models import ApiKey, ApiKeyScope
from relaydesk.security.tokens import generate_token, hash_token

# Mirrors ``services.auth.LAST_SEEN_INTERVAL`` and exists for the same
# reason: the only consumer of ``last_used_at`` is a "Last used" label in a
# settings list, and writing it on every request would put a write on the
# hot path of every read.
LAST_USED_INTERVAL = timedelta(hours=1)

# Uniform on purpose. A caller must not be able to tell an unknown token from
# a revoked one from an expired one -- the difference is only useful to
# somebody probing with tokens that are not theirs.
BAD_KEY = "API key is invalid, revoked or expired."


def _new_token() -> tuple[str, str]:
    """A fresh token and the prefix stored beside its hash.

    The prefix is ``rd_`` plus the first four characters of the secret. It is
    shown in the console so a human can tell two keys apart. Four characters
    of a 43-character token narrow nothing: an attacker who could brute-force
    the remaining 39 could brute-force all 43.
    """
    token = f"rd_{generate_token()}"
    return token, token[:7]


async def mint(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    name: str,
    scopes: Sequence[ApiKeyScope | str],
    created_by_user_id: uuid.UUID | None,
    expires_at: datetime | None = None,
) -> tuple[str, ApiKey]:
    """Create a key and return its plaintext token exactly once.

    The returned token is never recoverable afterwards: only its SHA-256
    digest is stored. SHA-256 rather than argon2 for the same reason
    ``Session`` uses it -- the token is 256 bits of CSPRNG output with no
    low-entropy structure, so there is no dictionary to slow down, and a
    password KDF on the hot path of every API request would only buy latency.

    This is the only writer of ``ApiKey.scopes``, so it is where the closed
    set is enforced (see the note on the column: an array column cannot carry
    the CHECK-constraint pattern the scalar enum columns use).
    """
    trimmed = name.strip()
    if not trimmed:
        raise ValueError("An API key needs a name.")

    values = [ApiKeyScope(scope).value for scope in scopes]

    token, prefix = _new_token()
    key = ApiKey(
        workspace_id=workspace_id,
        name=trimmed[:120],
        prefix=prefix,
        token_hash=hash_token(token),
        scopes=values,
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
    )
    session.add(key)
    await session.commit()
    return token, key


async def resolve(session: AsyncSession, token: str) -> ApiKey:
    """The live key a bearer token names, or ``Unauthorized``.

    A single unique-index lookup on the digest, so there is no per-candidate
    comparison and no timing channel of the kind ``services.auth.authenticate``
    guards against.
    """
    key = await session.scalar(
        sa.select(ApiKey).where(ApiKey.token_hash == hash_token(token))
    )
    if key is None or key.revoked_at is not None:
        raise Unauthorized(BAD_KEY)

    now = datetime.now(UTC)
    if key.expires_at is not None and key.expires_at <= now:
        raise Unauthorized(BAD_KEY)

    if key.last_used_at is None or now - key.last_used_at > LAST_USED_INTERVAL:
        key.last_used_at = now
        await session.commit()
    return key


async def list_keys(session: AsyncSession, workspace_id: uuid.UUID) -> list[ApiKey]:
    """Live keys, newest first. Revoked rows are kept for attribution but are
    not offered back to the console as though they still worked."""
    return list(
        await session.scalars(
            sa.select(ApiKey)
            .where(ApiKey.workspace_id == workspace_id, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
        )
    )


async def revoke(
    session: AsyncSession, workspace_id: uuid.UUID, key_id: uuid.UUID
) -> None:
    """Stop a key working, keeping its row.

    Scoped by workspace, and a key belonging to another workspace raises
    ``NotFound`` rather than ``Forbidden`` -- the slice-1 isolation contract.
    """
    key = await session.scalar(
        sa.select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.workspace_id == workspace_id,
            ApiKey.revoked_at.is_(None),
        )
    )
    if key is None:
        raise NotFound("API key not found.")
    key.revoked_at = datetime.now(UTC)
    await session.commit()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_api_keys_service.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Verify the whole suite and lint still pass**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/relaydesk/services/api_keys.py \
        apps/api/tests/test_api_keys_service.py
git commit -m "feat(api): mint, resolve and revoke API keys"
```

---

### Task 3: `Actor` — one principal type for the service layer

This is the one task that touches existing code broadly. It replaces the `actor: User` argument the conversation services take with an `Actor` that can also be an API key, and adds the two attribution columns.

**Files:**
- Create: `apps/api/src/relaydesk/services/actors.py`
- Create: `apps/api/migrations/versions/0016_actor_api_keys.py`
- Modify: `apps/api/src/relaydesk/models/activity.py`, `apps/api/src/relaydesk/models/message.py`
- Modify: `apps/api/src/relaydesk/services/conversations.py`, `apps/api/src/relaydesk/services/notifications.py`, `apps/api/src/relaydesk/services/ingest.py`
- Modify: `apps/api/src/relaydesk/api/conversations.py`
- Test: `apps/api/tests/test_actors.py`
- Modify (call sites): `apps/api/tests/test_assignment_notifications.py`, `apps/api/tests/test_outbound.py`, `apps/api/tests/test_mail_templates.py`

**Interfaces:**
- Consumes: `relaydesk.models.ApiKey` (Task 1), `relaydesk.models.User`.
- Produces: `relaydesk.services.actors.Actor`, a frozen dataclass with fields `name: str`, `user_id: uuid.UUID | None`, `api_key_id: uuid.UUID | None`, and constructors `Actor.for_user(user: User) -> Actor` and `Actor.for_key(key: ApiKey) -> Actor`. After this task every mutating function in `services.conversations` takes `actor: Actor`, and `conversations.record` takes `actor: Actor | None` with **no** `actor_name` parameter.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_actors.py`:

```python
import sqlalchemy as sa

from relaydesk.models import ActivityEvent, ApiKeyScope, ConversationStatus, Message
from relaydesk.services import api_keys, conversations
from relaydesk.services.actors import Actor
from tests.factories import make_conversation, make_member, make_workspace


def test_an_actor_for_a_user_carries_the_users_name_and_id() -> None:
    from relaydesk.models import User

    user = User(email="sara@relaydesk.dev", name="Sara Ali", monogram="SA")
    actor = Actor.for_user(user)

    assert actor.name == "Sara Ali"
    assert actor.user_id == user.id
    assert actor.api_key_id is None


async def test_an_actor_for_a_key_carries_the_keys_name(db_session) -> None:
    workspace = await make_workspace(db_session)
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name="Zapier integration",
        scopes=[ApiKeyScope.conversations_write],
        created_by_user_id=None,
    )

    actor = Actor.for_key(key)

    assert actor.name == "Zapier integration"
    assert actor.api_key_id == key.id
    assert actor.user_id is None


async def test_a_key_driven_status_change_is_attributed_to_the_key(
    db_session,
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name="Zapier integration",
        scopes=[ApiKeyScope.conversations_write],
        created_by_user_id=None,
    )

    await conversations.set_status(
        db_session,
        workspace.id,
        conversation.id,
        ConversationStatus.resolved,
        Actor.for_key(key),
    )

    event = await db_session.scalar(
        sa.select(ActivityEvent)
        .where(ActivityEvent.conversation_id == conversation.id)
        .order_by(ActivityEvent.at.desc())
    )
    assert event.actor_user_id is None
    assert event.actor_api_key_id == key.id
    assert event.actor_name == "Zapier integration"


async def test_a_user_driven_status_change_still_names_the_user(db_session) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)

    await conversations.set_status(
        db_session,
        workspace.id,
        conversation.id,
        ConversationStatus.resolved,
        Actor.for_user(user),
    )

    event = await db_session.scalar(
        sa.select(ActivityEvent)
        .where(ActivityEvent.conversation_id == conversation.id)
        .order_by(ActivityEvent.at.desc())
    )
    assert event.actor_user_id == user.id
    assert event.actor_api_key_id is None


async def test_a_key_driven_reply_is_attributed_to_the_key(db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name="Zapier integration",
        scopes=[ApiKeyScope.messages_write],
        created_by_user_id=None,
    )

    await conversations.add_reply(
        db_session, workspace.id, conversation.id, "On its way.", Actor.for_key(key)
    )

    message = await db_session.scalar(
        sa.select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.sent_at.desc())
    )
    assert message.author_user_id is None
    assert message.author_api_key_id == key.id
    assert message.author_name == "Zapier integration"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_actors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.services.actors'`

- [ ] **Step 3: Write the `Actor`**

Create `apps/api/src/relaydesk/services/actors.py`:

```python
import uuid
from dataclasses import dataclass

from relaydesk.models.api_key import ApiKey
from relaydesk.models.user import User


@dataclass(frozen=True, slots=True)
class Actor:
    """Whoever caused a change, whether or not they are a person.

    The persistence layer was already built for this shape before there was
    a name for it: ``activity_events`` and ``messages`` both carry a
    nullable actor foreign key beside a name *snapshot*, because inbound
    mail has always produced activity that no signed-in user caused. This
    type is that pattern made explicit, with a second nullable key for the
    principal added in slice 6.

    The name is a snapshot on purpose. It is what history displays, and it
    must keep displaying after the key is revoked or the user is removed --
    which is exactly when both foreign keys go ``NULL``.
    """

    name: str
    user_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None

    @classmethod
    def for_user(cls, user: User) -> "Actor":
        return cls(name=user.name, user_id=user.id)

    @classmethod
    def for_key(cls, key: ApiKey) -> "Actor":
        return cls(name=key.name, api_key_id=key.id)
```

- [ ] **Step 4: Add the attribution columns to the models**

In `apps/api/src/relaydesk/models/activity.py`, add below `actor_user_id`:

```python
    actor_api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
```

In `apps/api/src/relaydesk/models/message.py`, add below `author_user_id`:

```python
    author_api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
```

- [ ] **Step 5: Write the migration**

Create `apps/api/migrations/versions/0016_actor_api_keys.py`:

```python
"""attribute activity and messages to an API key

``activity_events`` and ``messages`` each carry a nullable actor foreign key
beside a name snapshot, because inbound mail has always produced rows no
signed-in user caused. Slice 6 adds a second kind of principal, so each
table gains a second nullable key.

The name snapshot is enough to *display* history. The foreign key is what
answers "show me everything this key did", which is the question asked on
the day a key is suspected of having leaked -- and which cannot be
retrofitted onto rows written before the column existed. That is the whole
argument for paying for it now rather than when it is wanted.

``SET NULL`` rather than ``CASCADE``: revoking or deleting a key must never
erase the history of what it did.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-08 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activity_events", sa.Column("actor_api_key_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_activity_events_actor_api_key_id",
        "activity_events",
        "api_keys",
        ["actor_api_key_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "messages", sa.Column("author_api_key_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_messages_author_api_key_id",
        "messages",
        "api_keys",
        ["author_api_key_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_messages_author_api_key_id", "messages", type_="foreignkey"
    )
    op.drop_column("messages", "author_api_key_id")
    op.drop_constraint(
        "fk_activity_events_actor_api_key_id", "activity_events", type_="foreignkey"
    )
    op.drop_column("activity_events", "actor_api_key_id")
```

- [ ] **Step 6: Change `record()` to take an `Actor`**

In `apps/api/src/relaydesk/services/conversations.py`, replace the `record` function (currently at line 293) with:

```python
def record(
    session: AsyncSession,
    conversation: Conversation,
    actor: Actor | None,
    kind: ActivityKind,
    verb: str,
    value: str,
    status: str | None = None,
) -> None:
    """Append to the conversation's history.

    Every mutation calls this, so the detail panel's timeline is a
    consequence of the change rather than a second thing to remember.

    ``actor`` is ``None`` only for activity with no nameable cause at all;
    everything else passes an ``Actor``, including inbound mail, which
    passes one carrying just a display name and neither key. The separate
    ``actor_name`` parameter this used to take is gone -- ``Actor`` is that
    parameter, with somewhere to put an identity when there is one.
    """
    session.add(
        ActivityEvent(
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            actor_user_id=actor.user_id if actor else None,
            actor_api_key_id=actor.api_key_id if actor else None,
            actor_name=actor.name if actor else "Relaydesk",
            kind=kind,
            verb=verb,
            value=value,
            status=status,
            at=datetime.now(UTC),
        )
    )
```

Add `from relaydesk.services.actors import Actor` to the imports, and remove `User` from the `relaydesk.models` import list if nothing else in the module uses it (`set_assignee` still queries `User`, so it stays).

- [ ] **Step 7: Change every mutating signature from `User` to `Actor`**

In the same file, change the `actor: User` annotation to `actor: Actor` in `_apply_status`, `set_status`, `bulk_set_status`, `set_priority`, `set_assignee`, `add_label`, `remove_label` and `add_reply`. No body changes are needed except in `add_reply`, where the `Message` construction becomes:

```python
    message = Message(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        role=MessageRole.agent,
        author_name=actor.name,
        author_user_id=actor.user_id,
        author_api_key_id=actor.api_key_id,
        to_address=conversation.contact.email,
        body=trimmed,
        sent_at=now,
        direction=MessageDirection.outbound,
        external_id=outbound.new_message_id(),
        delivery_state=DeliveryState.queued,
    )
```

- [ ] **Step 8: Update `notify_assignment`**

In `apps/api/src/relaydesk/services/notifications.py`, change the signature and the self-assignment check:

```python
def notify_assignment(
    conversation: Conversation, assignee: User, actor: Actor
) -> None:
    """Fire-and-forget. Never raises into the caller's request: an email that
    fails to enqueue must not fail the assignment itself.

    ``actor.user_id`` is ``None`` when an API key made the assignment, so the
    self-assignment suppression below correctly does not fire: nobody
    assigned it to themselves, and the assignee genuinely wants to know.
    """
    if assignee.id == actor.user_id or not assignee.notify_on_assignment:
        return
```

Import `Actor` from `relaydesk.services.actors`. The `f"{actor.name} assigned a conversation to you."` line needs no change — `Actor` has a `name`.

- [ ] **Step 9: Update the two `ingest` call sites**

In `apps/api/src/relaydesk/services/ingest.py`, the two `conversations.record(...)` calls pass `actor=None, actor_name=...`. Replace the pair of arguments with a single positional `Actor`:

At line ~260, `actor_name="Mail delivery"` becomes the third positional argument `Actor(name="Mail delivery")`, and the `actor_name=` keyword is deleted. At line ~426, `actor_name=contact.name` becomes `Actor(name=contact.name)` in the same way. Add `from relaydesk.services.actors import Actor` to the module's imports.

- [ ] **Step 10: Update the console routes**

In `apps/api/src/relaydesk/api/conversations.py`, every `scope.user` passed as an actor becomes `Actor.for_user(scope.user)`. There are seven such call sites (lines 99, 131, 135, 143, 189, 197, 214, 224 in the current file). Add `from relaydesk.services.actors import Actor` to the imports. Do not change anything else in the file — `scope.user` is still used for its own sake elsewhere.

- [ ] **Step 11: Update the test call sites**

Find them:

```bash
docker compose exec api grep -rn "conversations\.\(set_assignee\|set_status\|bulk_set_status\|set_priority\|add_label\|remove_label\|add_reply\)(" tests/
docker compose exec api grep -rn "notify_assignment" tests/
```

Known call sites: `tests/test_assignment_notifications.py` (five `set_assignee` calls), `tests/test_outbound.py` (five `add_reply` calls), `tests/test_mail_templates.py:101` (one `notify_assignment`). In each, the trailing `User` argument becomes `Actor.for_user(<that user>)`, and the module gains `from relaydesk.services.actors import Actor`.

- [ ] **Step 12: Run the full suite**

Run: `docker compose exec api pytest -m "not integration" -v`
Expected: PASS, including the five new tests in `tests/test_actors.py`. Any `AttributeError: 'User' object has no attribute 'user_id'` names a call site missed in Step 11.

- [ ] **Step 13: Lint**

Run: `docker compose exec api ruff check .`
Expected: no findings.

- [ ] **Step 14: Commit**

```bash
git add apps/api/src/relaydesk/services/actors.py \
        apps/api/migrations/versions/0016_actor_api_keys.py \
        apps/api/src/relaydesk/models/activity.py \
        apps/api/src/relaydesk/models/message.py \
        apps/api/src/relaydesk/services/conversations.py \
        apps/api/src/relaydesk/services/notifications.py \
        apps/api/src/relaydesk/services/ingest.py \
        apps/api/src/relaydesk/api/conversations.py \
        apps/api/tests/
git commit -m "refactor(api): attribute conversation changes to an Actor, not a User"
```

---

### Task 4: The per-key rate-limit counter

**Files:**
- Create: `apps/api/src/relaydesk/models/api_usage.py`
- Create: `apps/api/src/relaydesk/services/api_usage.py`
- Create: `apps/api/migrations/versions/0017_api_key_usage.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`, `apps/api/src/relaydesk/config.py`, `apps/api/src/relaydesk/worker/tasks/ratelimit.py`, `apps/api/src/relaydesk/worker/app.py`
- Test: `apps/api/tests/test_api_usage.py`

**Interfaces:**
- Consumes: `relaydesk.models.ApiKey` (Task 1).
- Produces: `relaydesk.models.ApiKeyUsage` (composite primary key `api_key_id`, `window_start`; `count: int`), and `relaydesk.services.api_usage.charge(session, api_key_id: uuid.UUID, *, limit: int) -> tuple[bool, int]` returning `(allowed, remaining)`, plus `api_usage.sweep(session, older_than: timedelta) -> int`. `config.Settings.api_key_rate_limit_per_minute: int = 120`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_api_usage.py`:

```python
import asyncio
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from relaydesk.models import ApiKeyScope, ApiKeyUsage
from relaydesk.services import api_keys, api_usage
from tests.factories import make_workspace


async def _key(db_session, name="Production ingest"):
    workspace = await make_workspace(db_session, slug=name.lower().replace(" ", "-"))
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name=name,
        scopes=[ApiKeyScope.conversations_read],
        created_by_user_id=None,
    )
    return key


async def test_calls_under_the_limit_are_allowed(db_session) -> None:
    key = await _key(db_session)

    for _ in range(3):
        allowed, _remaining = await api_usage.charge(db_session, key.id, limit=3)
        assert allowed


async def test_remaining_counts_down(db_session) -> None:
    key = await _key(db_session)

    _, first = await api_usage.charge(db_session, key.id, limit=3)
    _, second = await api_usage.charge(db_session, key.id, limit=3)

    assert (first, second) == (2, 1)


async def test_the_call_over_the_limit_is_refused(db_session) -> None:
    key = await _key(db_session)
    for _ in range(3):
        await api_usage.charge(db_session, key.id, limit=3)

    allowed, remaining = await api_usage.charge(db_session, key.id, limit=3)

    assert not allowed
    assert remaining == 0


async def test_two_keys_have_separate_allowances(db_session) -> None:
    ours = await _key(db_session, name="Ours")
    theirs = await _key(db_session, name="Theirs")
    for _ in range(3):
        await api_usage.charge(db_session, ours.id, limit=3)

    allowed, _ = await api_usage.charge(db_session, theirs.id, limit=3)

    assert allowed


async def test_one_row_per_key_per_window(db_session) -> None:
    key = await _key(db_session)

    for _ in range(5):
        await api_usage.charge(db_session, key.id, limit=100)

    rows = list(
        await db_session.scalars(
            sa.select(ApiKeyUsage).where(ApiKeyUsage.api_key_id == key.id)
        )
    )
    assert len(rows) == 1
    assert rows[0].count == 5


async def test_concurrent_charges_are_all_counted(db_session, engine) -> None:
    """The whole reason this exists rather than reusing ``ratelimit.check``.

    Ten callers arriving together must produce a count of ten, not a count
    of one repeated ten times -- and must do it without an advisory lock
    serialising them.
    """
    key = await _key(db_session)
    await db_session.commit()

    async def charge_once() -> None:
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(bind=engine, expire_on_commit=False) as session:
            await api_usage.charge(session, key.id, limit=100)

    await asyncio.gather(*(charge_once() for _ in range(10)))

    async with engine.connect() as connection:
        total = await connection.scalar(
            sa.select(sa.func.sum(ApiKeyUsage.__table__.c.count)).where(
                ApiKeyUsage.__table__.c.api_key_id == key.id
            )
        )
    assert total == 10

    async with engine.begin() as connection:
        await connection.execute(
            sa.delete(ApiKeyUsage.__table__).where(
                ApiKeyUsage.__table__.c.api_key_id == key.id
            )
        )


async def test_sweep_drops_windows_older_than_the_retention(db_session) -> None:
    key = await _key(db_session)
    db_session.add(
        ApiKeyUsage(
            api_key_id=key.id,
            window_start=datetime.now(UTC) - timedelta(days=2),
            count=7,
        )
    )
    await db_session.commit()
    await api_usage.charge(db_session, key.id, limit=100)

    dropped = await api_usage.sweep(db_session, timedelta(days=1))

    assert dropped == 1
    remaining = list(
        await db_session.scalars(
            sa.select(ApiKeyUsage).where(ApiKeyUsage.api_key_id == key.id)
        )
    )
    assert len(remaining) == 1
```

Note on `test_concurrent_charges_are_all_counted`: it opens its own sessions against `engine` because the shared `db_session` fixture wraps everything in one outer transaction that concurrent connections cannot see. It cleans up after itself for the same reason — its writes are real and are not rolled back with the fixture.

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_api_usage.py -v`
Expected: FAIL — `ImportError: cannot import name 'ApiKeyUsage' from 'relaydesk.models'`

- [ ] **Step 3: Write the model**

Create `apps/api/src/relaydesk/models/api_usage.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base


class ApiKeyUsage(Base):
    """One fixed window of one key's API calls.

    Deliberately *not* ``rate_limit_hits``. That table records one row per
    call and serialises same-key callers on a ``pg_advisory_xact_lock``,
    which is the right trade at five portal submissions an hour and the
    wrong one at a couple of requests a second: an import job would queue
    behind its own lock and write a row per call.

    This is a counter instead -- one row per key per minute, incremented in
    place. No lock, no serialisation between concurrent callers, and a row
    count bounded by (keys x minutes) rather than by traffic.

    No ``UUIDMixin``: the natural key *is* the pair, and it is what the
    upsert conflicts on.
    """

    __tablename__ = "api_key_usage"

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        primary_key=True,
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
```

Register it in `models/__init__.py`: `from relaydesk.models.api_usage import ApiKeyUsage`, and `"ApiKeyUsage"` in `__all__`.

- [ ] **Step 4: Write the service**

Create `apps/api/src/relaydesk/services/api_usage.py`:

```python
import uuid
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.api_usage import ApiKeyUsage


async def charge(
    session: AsyncSession, api_key_id: uuid.UUID, *, limit: int
) -> tuple[bool, int]:
    """Record one call and say whether the key is still within its limit.

    Returns ``(allowed, remaining)``.

    One statement, one round trip: the upsert increments the current
    window's row and returns the new count in the same breath. Because the
    increment happens inside the row's own lock, concurrent callers are
    counted correctly without an advisory lock and without serialising --
    which is the difference between this and ``services.ratelimit.check``.

    **This commits**, for the reason that function documents: the charge has
    to outlive the request that earned it whatever else that request goes on
    to do, and ``get_session`` rolls back a session that ends without an
    explicit commit. It is called from a dependency, before the route body
    runs, so nothing else is pending on the session when it does.

    The window boundary is computed by Postgres (``date_trunc`` over
    ``now()``), not by this process, for the reason spelled out in
    ``ratelimit.check``: one clock has to decide both sides of the
    comparison, or a skewed app clock silently disables the limit.

    A refused call is still counted. A caller already over the limit does
    not get free retries by being refused.
    """
    statement = (
        pg_insert(ApiKeyUsage)
        .values(
            api_key_id=api_key_id,
            window_start=sa.func.date_trunc("minute", sa.func.now()),
            count=1,
        )
        .on_conflict_do_update(
            index_elements=["api_key_id", "window_start"],
            set_={"count": ApiKeyUsage.count + 1},
        )
        .returning(ApiKeyUsage.count)
    )
    used = int(await session.scalar(statement) or 0)
    await session.commit()
    return used <= limit, max(limit - used, 0)


async def sweep(session: AsyncSession, older_than: timedelta) -> int:
    """Delete windows too old to count, and say how many.

    Nothing reads a closed window, and one row per key per minute adds up
    over a year. ``older_than`` is expected to be a generous multiple of the
    one-minute window so a sweep can never race a live count.
    """
    result = await session.execute(
        sa.delete(ApiKeyUsage).where(
            ApiKeyUsage.window_start
            < sa.func.now() - sa.literal(older_than, sa.Interval)
        )
    )
    await session.commit()
    return int(result.rowcount or 0)
```

- [ ] **Step 5: Write the migration**

Create `apps/api/migrations/versions/0017_api_key_usage.py`:

```python
"""api key usage windows

Adds ``api_key_usage``, the counter behind the per-key rate limit.

Deliberately not ``rate_limit_hits``. That table stores one row per call and
takes a ``pg_advisory_xact_lock`` per call, which is correct for five
anonymous portal submissions an hour and wrong for an authenticated API: at
a couple of requests a second every same-key caller would serialise behind
one lock, and a bulk import would write a row per request.

This is a fixed-window counter instead: the primary key is the
``(api_key_id, window_start)`` pair, which is what the upsert conflicts on,
so a call is one ``INSERT ... ON CONFLICT DO UPDATE ... RETURNING`` with no
lock and no extra row. The trade is the usual fixed-window one -- up to
twice the limit across a window boundary -- which is accepted because this
bound exists to stop a runaway integration, not to defeat an adversary.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-08 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_key_usage",
        sa.Column("api_key_id", sa.UUID(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("api_key_id", "window_start"),
    )
    op.create_index(
        "ix_api_key_usage_window_start",
        "api_key_usage",
        ["window_start"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_api_key_usage_window_start", table_name="api_key_usage")
    op.drop_table("api_key_usage")
```

- [ ] **Step 6: Add the setting**

In `apps/api/src/relaydesk/config.py`, below `ticket_attachment_max_count`:

```python
    # Calls one API key may make per minute. Generous for an integration
    # syncing tickets, and low enough that a runaway loop is bounded before
    # it becomes the database's problem. A fixed window, so a caller can see
    # up to twice this across a boundary -- see the note in migration 0017.
    api_key_rate_limit_per_minute: int = 120
```

- [ ] **Step 7: Sweep old windows on the beat schedule**

Append to `apps/api/src/relaydesk/worker/tasks/ratelimit.py`:

```python
# One minute is the only window ``api_usage.charge`` uses. A day is a
# deliberately generous multiple: a window this old cannot affect any count,
# and the margin means a longer window added later does not silently start
# deleting rows that still matter.
API_USAGE_RETENTION = timedelta(days=1)


async def _sweep_api_usage() -> int:
    async with bridge.session_scope() as session:
        return await api_usage.sweep(session, API_USAGE_RETENTION)


@app.task(name="relaydesk.sweep_api_usage")
def sweep_api_usage() -> int:
    """Drop rate-limit windows too old to count against any limit.

    One row per key per minute is small, but nothing else deletes it, and
    over a year an active key leaves half a million rows behind.
    """
    return bridge.run(_sweep_api_usage())
```

Change the module's import line to `from relaydesk.services import api_usage, ratelimit`.

In `apps/api/src/relaydesk/worker/app.py`, add to `beat_schedule` after `sweep-rate-limits`:

```python
        "sweep-api-usage": {
            "task": "relaydesk.sweep_api_usage",
            "schedule": 3600.0,
        },
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_api_usage.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 9: Verify the whole suite and lint**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add apps/api/src/relaydesk/models/api_usage.py \
        apps/api/src/relaydesk/models/__init__.py \
        apps/api/src/relaydesk/services/api_usage.py \
        apps/api/migrations/versions/0017_api_key_usage.py \
        apps/api/src/relaydesk/config.py \
        apps/api/src/relaydesk/worker/tasks/ratelimit.py \
        apps/api/src/relaydesk/worker/app.py \
        apps/api/tests/test_api_usage.py
git commit -m "feat(api): count API key calls in a fixed window"
```

---

### Task 5: `external_id` and `metadata` on a conversation

The two fields the published code sample promises. They land before the endpoint that uses them so the v1 response shape is complete from its first commit and never changes underneath the snapshot test in Task 12.

**Files:**
- Modify: `apps/api/src/relaydesk/models/conversation.py`
- Create: `apps/api/migrations/versions/0018_conversation_external_id.py`
- Test: `apps/api/tests/test_conversation_external_id.py`

**Interfaces:**
- Produces: `Conversation.external_id: str | None` and `Conversation.meta: dict` (the database column is named `metadata`; the Python attribute cannot be, because Declarative owns that name). A partial unique index `uq_conversations_external_id` on `(workspace_id, external_id)` where `external_id IS NOT NULL`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_conversation_external_id.py`:

```python
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.models import Conversation
from tests.factories import make_conversation, make_workspace


async def test_external_id_defaults_to_null_and_metadata_to_empty(db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)

    stored = await db_session.scalar(
        sa.select(Conversation).where(Conversation.id == conversation.id)
    )

    assert stored.external_id is None
    assert stored.meta == {}


async def test_metadata_round_trips_as_json(db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    conversation.meta = {"order_id": "ord_456", "plan": "growth", "seats": 12}
    await db_session.commit()

    stored = await db_session.scalar(
        sa.select(Conversation).where(Conversation.id == conversation.id)
    )

    assert stored.meta == {"order_id": "ord_456", "plan": "growth", "seats": 12}


async def test_one_external_id_per_workspace(db_session) -> None:
    workspace = await make_workspace(db_session)
    first = await make_conversation(db_session, workspace, subject="First")
    second = await make_conversation(db_session, workspace, subject="Second")
    first.external_id = "ticket-123"
    await db_session.commit()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            second.external_id = "ticket-123"
            await db_session.flush()


async def test_two_workspaces_may_use_the_same_external_id(db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    mine = await make_conversation(db_session, ours)
    yours = await make_conversation(db_session, theirs)

    mine.external_id = "ticket-123"
    yours.external_id = "ticket-123"
    await db_session.commit()  # does not raise


async def test_many_conversations_may_have_no_external_id(db_session) -> None:
    """The index is partial for exactly this reason.

    Postgres treats NULLs as distinct, so a plain unique index would appear
    to constrain while permitting unlimited duplicate (workspace, NULL)
    rows -- which is every conversation that did not arrive through the API.
    """
    workspace = await make_workspace(db_session)
    for index in range(3):
        await make_conversation(db_session, workspace, subject=f"Ticket {index}")

    total = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Conversation)
        .where(
            Conversation.workspace_id == workspace.id,
            Conversation.external_id.is_(None),
        )
    )
    assert total == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_conversation_external_id.py -v`
Expected: FAIL — `AttributeError: type object 'Conversation' has no attribute 'external_id'`

- [ ] **Step 3: Add the columns**

In `apps/api/src/relaydesk/models/conversation.py`, add `JSONB` to the `sqlalchemy.dialects.postgresql` import, extend `__table_args__`, and add the two columns after `summary_state`:

```python
    __table_args__ = (
        UniqueConstraint("workspace_id", "number"),
        Index("ix_conversations_inbox", "workspace_id", "status", "last_message_at"),
        # Partial, for the same reason as ``uq_messages_channel_external``:
        # Postgres treats NULLs as distinct, so a plain unique index would
        # permit unlimited duplicate (workspace_id, NULL) rows -- which is
        # every conversation that did not arrive through the API -- while
        # appearing to enforce the constraint.
        Index(
            "uq_conversations_external_id",
            "workspace_id",
            "external_id",
            unique=True,
            postgresql_where=sa.text("external_id IS NOT NULL"),
        ),
    )
```

(`import sqlalchemy as sa` at the top of the module if it is not already there — the current file imports names directly from `sqlalchemy`, so add the `sa` alias import alongside them.)

```python
    # The caller's own identifier for this ticket. Unique per workspace, so
    # a repeated POST returns the conversation it already created rather
    # than a duplicate -- which is what makes an interrupted import safe to
    # re-run.
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # The column is ``metadata``; the attribute cannot be, because
    # Declarative owns that name on every model. Capped at the schema edge
    # (8 KB, 50 keys) so it stays a place for an order id and does not
    # become a blob store inside the hottest table in the product.
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}", default=dict
    )
```

- [ ] **Step 4: Write the migration**

Create `apps/api/migrations/versions/0018_conversation_external_id.py`:

```python
"""conversation external_id and metadata

The two fields the console's published code sample
(``apps/web/components/settings/code-sample.tsx``) promises on
``POST /v1/conversations``.

``external_id`` is the caller's own identifier, unique per workspace, and it
is what makes the create endpoint idempotent: a repeated POST returns the
conversation it already created instead of a duplicate. The index is
*partial* because Postgres treats NULLs as distinct -- a plain unique index
would permit unlimited duplicate ``(workspace_id, NULL)`` rows, which is
every conversation that did not arrive through the API, while appearing to
enforce the constraint. The same trap is documented on
``uq_messages_channel_external``.

``metadata`` is JSONB and unindexed: retrievable per conversation, not
queryable across them. Filtering on it would want a GIN index and a query
language, and that decision is deliberately not made here.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-08 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("external_id", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "conversations",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.create_index(
        "uq_conversations_external_id",
        "conversations",
        ["workspace_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_conversations_external_id", table_name="conversations")
    op.drop_column("conversations", "metadata")
    op.drop_column("conversations", "external_id")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_conversation_external_id.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 6: Verify the whole suite and lint**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/models/conversation.py \
        apps/api/migrations/versions/0018_conversation_external_id.py \
        apps/api/tests/test_conversation_external_id.py
git commit -m "feat(api): give a conversation an external_id and metadata"
```

---

### Task 6: The v1 surface — authentication, scopes, limits, and the read endpoints

**Files:**
- Create: `apps/api/src/relaydesk/api/v1/__init__.py`, `apps/api/src/relaydesk/api/v1/deps.py`, `apps/api/src/relaydesk/api/v1/router.py`, `apps/api/src/relaydesk/api/v1/conversations.py`, `apps/api/src/relaydesk/schemas/v1.py`
- Modify: `apps/api/src/relaydesk/errors.py`, `apps/api/src/relaydesk/main.py`, `apps/api/src/relaydesk/services/conversations.py`
- Test: `apps/api/tests/test_v1_auth.py`, `apps/api/tests/test_v1_conversations_read.py`

**Interfaces:**
- Consumes: `services.api_keys.resolve` (Task 2), `services.actors.Actor` (Task 3), `services.api_usage.charge` (Task 4), `Conversation.external_id`/`.meta` (Task 5), `api.deps.bearer_token`, `api.deps.DbSession`.
- Produces:
  - `api.v1.deps.ApiPrincipal` with `.key: ApiKey`, `.workspace: Workspace`, `.workspace_id: uuid.UUID`, `.actor: Actor`, `.require(*scopes) -> None`.
  - `api.v1.deps.requires(*scopes: ApiKeyScope)` — a dependency factory returning `ApiPrincipal`.
  - `schemas.v1.V1Model`, `ContactOut`, `ConversationOut`, `ConversationPage`, `MessageOut`, and the constructors `conversation_out(conversation) -> ConversationOut`, `message_out(message) -> MessageOut`, `contact_out(contact) -> ContactOut`.
  - `GET /v1/conversations`, `GET /v1/conversations/{id}`, `GET /v1/conversations/{id}/messages`.
- Note for later tasks: response schemas are **constructed explicitly**, never `model_validate(orm_object)`. Reading `metadata` off a `Conversation` returns SQLAlchemy's `MetaData`, not the column — the column's attribute is `meta`. `conversation_out` is the single place that knows this.

- [ ] **Step 1: Write the failing auth test**

Create `apps/api/tests/test_v1_auth.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest

from relaydesk.config import get_settings
from relaydesk.models import ApiKeyScope
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_workspace


async def mint(db_session, workspace, scopes, **kwargs):
    token, key = await api_keys.mint(
        db_session,
        workspace.id,
        name=kwargs.pop("name", "Integration"),
        scopes=scopes,
        created_by_user_id=None,
        **kwargs,
    )
    return token, key


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_a_call_with_no_key_is_refused(client) -> None:
    response = await client.get("/v1/conversations")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_a_call_with_an_unknown_key_is_refused(client) -> None:
    response = await client.get(
        "/v1/conversations", headers=auth("rd_never-minted-anywhere")
    )

    assert response.status_code == 401


async def test_a_revoked_key_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await mint(db_session, workspace, [ApiKeyScope.conversations_read])
    await api_keys.revoke(db_session, workspace.id, key.id)

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 401


async def test_an_expired_key_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await mint(
        db_session,
        workspace,
        [ApiKeyScope.conversations_read],
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 401


async def test_a_key_without_the_scope_is_refused_and_told_which(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.labels_read])

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "forbidden"
    assert "conversations:read" in body["message"]


async def test_a_key_with_the_scope_is_allowed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.conversations_read])

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 200


async def test_a_key_cannot_see_another_workspaces_conversation(
    client, db_session
) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    token, _ = await mint(db_session, ours, [ApiKeyScope.conversations_read])

    response = await client.get(
        f"/v1/conversations/{hidden.id}", headers=auth(token)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_every_response_carries_the_rate_limit_headers(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.conversations_read])

    response = await client.get("/v1/conversations", headers=auth(token))

    limit = get_settings().api_key_rate_limit_per_minute
    assert response.headers["x-ratelimit-limit"] == str(limit)
    assert int(response.headers["x-ratelimit-remaining"]) == limit - 1


async def test_a_key_over_its_limit_is_refused_with_retry_after(
    client, db_session, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "api_key_rate_limit_per_minute", 2)
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.conversations_read])

    for _ in range(2):
        assert (
            await client.get("/v1/conversations", headers=auth(token))
        ).status_code == 200

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_requests"
    assert response.headers["retry-after"] == "60"


async def test_the_console_surface_does_not_accept_an_api_key(
    client, db_session
) -> None:
    """A key is not a session. ``/api`` stays session-only (spec D2)."""
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.conversations_read])

    response = await client.get("/api/conversations", headers=auth(token))

    assert response.status_code == 401
```

- [ ] **Step 2: Write the failing read test**

Create `apps/api/tests/test_v1_conversations_read.py`:

```python
from datetime import UTC, datetime, timedelta

from relaydesk.models import ApiKeyScope, ConversationStatus, Priority
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_label, make_workspace


async def setup_key(db_session, workspace, scopes=None):
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Integration",
        scopes=scopes or [ApiKeyScope.conversations_read],
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_list_returns_this_workspaces_conversations(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace, subject="Refund")
    headers = await setup_key(db_session, workspace)

    response = await client.get("/v1/conversations", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["subject"] for item in body["data"]] == ["Refund"]
    assert body["next_cursor"] is None
    item = body["data"][0]
    assert item["id"] == str(conversation.id)
    assert item["number"] == conversation.number
    assert item["status"] == "open"
    assert item["external_id"] is None
    assert item["metadata"] == {}
    assert item["customer"]["email"] == "priya@northwind.io"


async def test_the_response_carries_no_console_only_fields(client, db_session) -> None:
    """v1 must not inherit the inbox's rendering decisions (spec D6)."""
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await setup_key(db_session, workspace)

    item = (await client.get("/v1/conversations", headers=headers)).json()["data"][0]

    for console_only in ("age", "date", "hasDraft", "has_draft", "unread"):
        assert console_only not in item


async def test_the_response_is_snake_case(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await setup_key(db_session, workspace)

    item = (await client.get("/v1/conversations", headers=headers)).json()["data"][0]

    assert "last_message_at" in item
    assert "lastMessageAt" not in item


async def test_list_filters_by_status(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace, subject="Open one")
    await make_conversation(
        db_session, workspace, subject="Resolved one",
        status=ConversationStatus.resolved,
    )
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations", params={"status": "resolved"}, headers=headers
    )

    assert [item["subject"] for item in response.json()["data"]] == ["Resolved one"]


async def test_list_filters_by_priority(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace, subject="Urgent one")
    await make_conversation(
        db_session, workspace, subject="Low one", priority=Priority.low
    )
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations", params={"priority": "low"}, headers=headers
    )

    assert [item["subject"] for item in response.json()["data"]] == ["Low one"]


async def test_list_filters_by_updated_since(client, db_session) -> None:
    """What makes a polling sync possible before webhooks exist."""
    workspace = await make_workspace(db_session)
    stale = await make_conversation(db_session, workspace, subject="Stale")
    headers = await setup_key(
        db_session,
        workspace,
        scopes=[ApiKeyScope.conversations_read, ApiKeyScope.conversations_write],
    )
    boundary = datetime.now(UTC)

    fresh = await make_conversation(db_session, workspace, subject="Fresh")
    fresh.updated_at = boundary + timedelta(seconds=5)
    stale.updated_at = boundary - timedelta(hours=1)
    await db_session.commit()

    response = await client.get(
        "/v1/conversations",
        params={"updated_since": boundary.isoformat()},
        headers=headers,
    )

    assert [item["subject"] for item in response.json()["data"]] == ["Fresh"]


async def test_list_rejects_an_unknown_status(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations", params={"status": "banana"}, headers=headers
    )

    assert response.status_code == 422


async def test_list_paginates_by_cursor(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    for index in range(3):
        await make_conversation(
            db_session, workspace, subject=f"Ticket {index}", minutes_ago=index + 1
        )
    headers = await setup_key(db_session, workspace)

    first = await client.get(
        "/v1/conversations", params={"limit": 2}, headers=headers
    )
    cursor = first.json()["next_cursor"]
    assert cursor is not None

    second = await client.get(
        "/v1/conversations", params={"limit": 2, "cursor": cursor}, headers=headers
    )

    seen = [item["id"] for item in first.json()["data"]] + [
        item["id"] for item in second.json()["data"]
    ]
    assert len(seen) == len(set(seen)) == 3


async def test_get_returns_one_conversation_with_its_labels(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    label = await make_label(db_session, workspace)
    conversation.labels.append(label)
    await db_session.commit()
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        f"/v1/conversations/{conversation.id}", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["label_ids"] == [str(label.id)]


async def test_get_answers_404_for_an_unknown_id(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations/00000000-0000-0000-0000-000000000000", headers=headers
    )

    assert response.status_code == 404


async def test_messages_are_returned_oldest_first(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        f"/v1/conversations/{conversation.id}/messages", headers=headers
    )

    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 1
    assert messages[0]["role"] == "customer"
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["author_name"] == "Priya Raman"


async def test_messages_for_another_workspace_answer_404(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers = await setup_key(db_session, ours)

    response = await client.get(
        f"/v1/conversations/{hidden.id}/messages", headers=headers
    )

    assert response.status_code == 404
```

- [ ] **Step 3: Run both tests to verify they fail**

Run: `docker compose exec api pytest tests/test_v1_auth.py tests/test_v1_conversations_read.py -v`
Expected: FAIL — every request answers `404` because nothing is mounted at `/v1`.

- [ ] **Step 4: Let an `AppError` carry response headers**

In `apps/api/src/relaydesk/errors.py`, replace `AppError.__init__`:

```python
class AppError(Exception):
    """Base for domain errors. Services raise these; routers map them."""

    code = "error"
    status_code = 400

    def __init__(self, message: str, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        # Only a 429 uses this today: ``Retry-After`` is part of what makes a
        # rate-limit refusal actionable rather than just a status code, and
        # the handler in ``relaydesk.main`` is the only thing that can attach
        # it to the response.
        self.headers = headers
```

In `apps/api/src/relaydesk/main.py`, in `handle_app_error`:

```python
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
        headers=error.headers,
    )
```

- [ ] **Step 5: Extend `list_conversations` with the two filters v1 promises**

The spec's surface table says `GET /v1/conversations` filters on `status`,
`priority`, `assignee_id`, `label_id` and `updated_since`. The service supports
the first, third and fourth today. In
`apps/api/src/relaydesk/services/conversations.py`, add two keyword-only
parameters to `list_conversations` — `priority: Priority | None = None` and
`updated_since: datetime | None = None` — and the two clauses they imply, after
the existing `assignee_id` clause:

```python
    if priority is not None:
        query = query.where(Conversation.priority == priority)
    if updated_since is not None:
        # Filtered, not ordered by. The keyset stays on
        # ``(last_message_at, id)``, so a conversation whose status changed
        # without a new message keeps its old position in the page rather
        # than jumping to the front. A poller asking "what changed since T"
        # still sees all of them; it just does not see them in change order.
        # Ordering by ``updated_at`` instead would need its own cursor and
        # its own index, and is not worth it until something asks.
        query = query.where(Conversation.updated_at >= updated_since)
```

Both are additive keyword arguments with defaults, so no existing caller changes.

- [ ] **Step 6: Write the v1 schemas**

Create `apps/api/src/relaydesk/schemas/v1.py`:

```python
"""Public API request and response shapes.

Deliberately **not** ``CamelModel``. The console's schemas are camelCase and
carry fields rendered for one particular sidebar -- ``age`` as "3h", ``date``
as "Sep 4", ``has_draft`` -- and serving those here would freeze a UI's
rendering decisions into a third-party contract (spec D6). Everything in this
module is snake_case, with ISO-8601 timestamps and no derived display fields.

Response models are **constructed by the helpers at the bottom of this
module, never by ``model_validate`` on an ORM object**. ``Conversation`` has
no ``metadata`` attribute -- reading it returns SQLAlchemy's ``MetaData``,
because Declarative owns that name -- so the column is reached as ``.meta``,
and that fact is confined to ``conversation_out``.
"""

import json
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict

from relaydesk.models import Contact, Conversation, Message

METADATA_MAX_BYTES = 8192
METADATA_MAX_KEYS = 50


def _bounded_metadata(value: dict[str, Any]) -> dict[str, Any]:
    """Keep ``metadata`` a place for an order id, not a blob store.

    It lives inside ``conversations``, the hottest table in the product, and
    it is unindexed, so an unbounded field would cost every inbox query
    without ever being queryable itself.
    """
    if len(value) > METADATA_MAX_KEYS:
        raise ValueError(f"metadata accepts at most {METADATA_MAX_KEYS} keys.")
    encoded = json.dumps(value, separators=(",", ":")).encode()
    if len(encoded) > METADATA_MAX_BYTES:
        raise ValueError(f"metadata must be under {METADATA_MAX_BYTES} bytes.")
    return value


Metadata = Annotated[dict[str, Any], AfterValidator(_bounded_metadata)]


class V1Model(BaseModel):
    """Every public schema inherits this. snake_case on the wire."""

    model_config = ConfigDict(from_attributes=False)


class ContactOut(V1Model):
    id: str
    email: str
    name: str


class ConversationOut(V1Model):
    id: str
    number: int
    subject: str
    preview: str
    status: str
    priority: str
    channel: str
    customer: ContactOut
    assignee_id: str | None
    label_ids: list[str]
    external_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime


class ConversationPage(V1Model):
    data: list[ConversationOut]
    next_cursor: str | None = None


class MessageOut(V1Model):
    id: str
    conversation_id: str
    role: str
    direction: str
    author_name: str
    body: str
    sent_at: datetime


def contact_out(contact: Contact) -> ContactOut:
    return ContactOut(id=str(contact.id), email=contact.email, name=contact.name)


def conversation_out(conversation: Conversation) -> ConversationOut:
    return ConversationOut(
        id=str(conversation.id),
        number=conversation.number,
        subject=conversation.subject,
        preview=conversation.preview,
        status=conversation.status.value,
        priority=conversation.priority.value,
        channel=conversation.channel.value,
        customer=contact_out(conversation.contact),
        assignee_id=(
            str(conversation.assignee_id) if conversation.assignee_id else None
        ),
        label_ids=[str(label.id) for label in conversation.labels],
        external_id=conversation.external_id,
        # ``.meta``, not ``.metadata`` -- see this module's docstring.
        metadata=conversation.meta,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_message_at=conversation.last_message_at,
    )


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=str(message.id),
        conversation_id=str(message.conversation_id),
        role=message.role.value,
        direction=message.direction.value,
        author_name=message.author_name,
        body=message.body,
        sent_at=message.sent_at,
    )
```

- [ ] **Step 7: Write the v1 dependency**

Create `apps/api/src/relaydesk/api/v1/__init__.py` (empty file), and `apps/api/src/relaydesk/api/v1/deps.py`:

```python
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Response

from relaydesk.api.deps import DbSession, bearer_token
from relaydesk.config import get_settings
from relaydesk.errors import Forbidden, TooManyRequests, Unauthorized
from relaydesk.models import ApiKey, ApiKeyScope, Workspace
from relaydesk.services import api_keys, api_usage
from relaydesk.services.actors import Actor


@dataclass(slots=True)
class ApiPrincipal:
    """Resolved tenant context for a key-authenticated call.

    The public-surface counterpart to ``WorkspaceScope``, and deliberately
    not the same object. ``WorkspaceScope.user`` is non-null at every one of
    its call sites, several of which hand it straight to a service; making it
    optional to accommodate a principal no console route uses would turn a
    compile-time guarantee into a runtime audit of every console route (spec
    D2). The two meet at the service layer instead, through ``Actor``.
    """

    key: ApiKey
    workspace: Workspace

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id

    @property
    def actor(self) -> Actor:
        return Actor.for_key(self.key)

    def require(self, *scopes: ApiKeyScope) -> None:
        for scope in scopes:
            if scope.value not in self.key.scopes:
                # Naming the missing scope is safe: the caller holds this key
                # and can already read its scopes in the console. Withholding
                # it would only make a correct integration harder to write.
                raise Forbidden(f"This key needs the {scope.value} scope.")


async def api_principal(
    session: DbSession,
    response: Response,
    token: Annotated[str, Depends(bearer_token)],
) -> ApiPrincipal:
    """Authenticate the key and charge the call against its limit.

    The charge happens here, before the route body, so a refused caller
    never reaches the work -- and it happens on every call, including ones
    that go on to 404, because a probe is still a call.
    """
    key = await api_keys.resolve(session, token)
    workspace = await session.get(Workspace, key.workspace_id)
    if workspace is None:
        raise Unauthorized(api_keys.BAD_KEY)

    limit = get_settings().api_key_rate_limit_per_minute
    allowed, remaining = await api_usage.charge(session, key.id, limit=limit)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    if not allowed:
        # The headers set above belong to the *success* response object; an
        # exception bypasses it, so the refusal carries its own copy.
        raise TooManyRequests(
            "Rate limit exceeded for this API key.",
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
            },
        )

    return ApiPrincipal(key=key, workspace=workspace)


Principal = Annotated[ApiPrincipal, Depends(api_principal)]


def requires(
    *scopes: ApiKeyScope,
) -> Callable[[ApiPrincipal], Coroutine[Any, Any, ApiPrincipal]]:
    """A dependency that authenticates and then demands specific scopes.

    Every v1 route declares its own, so the scope a route needs is written
    next to the route rather than in a table somewhere else -- and it shows
    up in the generated OpenAPI document as part of the signature.
    """

    async def dependency(principal: Principal) -> ApiPrincipal:
        principal.require(*scopes)
        return principal

    return dependency
```

- [ ] **Step 8: Write the read endpoints**

Create `apps/api/src/relaydesk/api/v1/conversations.py`:

```python
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from relaydesk.api.deps import DbSession
from relaydesk.api.v1.deps import ApiPrincipal, requires
from relaydesk.models import ApiKeyScope, ConversationStatus, Priority
from relaydesk.schemas.v1 import (
    ConversationOut,
    ConversationPage,
    MessageOut,
    conversation_out,
    message_out,
)
from relaydesk.services import conversations

router = APIRouter()

Reader = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.conversations_read))]


@router.get("", response_model=ConversationPage)
async def list_route(
    principal: Reader,
    session: DbSession,
    status: ConversationStatus | None = None,
    priority: Priority | None = None,
    assignee_id: uuid.UUID | None = None,
    label_id: uuid.UUID | None = None,
    updated_since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> ConversationPage:
    rows, next_cursor = await conversations.list_conversations(
        session,
        principal.workspace_id,
        status=status,
        priority=priority,
        label_id=label_id,
        assignee_id=assignee_id,
        updated_since=updated_since,
        limit=limit,
        cursor=cursor,
    )
    return ConversationPage(
        data=[conversation_out(row) for row in rows], next_cursor=next_cursor
    )


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_route(
    conversation_id: uuid.UUID, principal: Reader, session: DbSession
) -> ConversationOut:
    conversation = await conversations.get_conversation(
        session, principal.workspace_id, conversation_id
    )
    return conversation_out(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages_route(
    conversation_id: uuid.UUID, principal: Reader, session: DbSession
) -> list[MessageOut]:
    rows = await conversations.list_messages(
        session, principal.workspace_id, conversation_id
    )
    return [message_out(row) for row in rows]
```

Create `apps/api/src/relaydesk/api/v1/router.py`:

```python
"""The public API.

Mounted at ``/v1``, beside ``/api`` rather than under it (spec D7). ``/api``
is the console's private surface and is free to change with the UI; this one
is a promise to third parties. Keeping the two prefixes apart makes which is
which legible in the route table, and makes the published sample --
``https://api.relaydesk.dev/v1/conversations`` -- true with no proxy
rewriting.
"""

from fastapi import APIRouter

from relaydesk.api.v1.conversations import router as conversations_router

v1_router = APIRouter()
v1_router.include_router(
    conversations_router, prefix="/conversations", tags=["v1: conversations"]
)
```

- [ ] **Step 9: Mount it**

In `apps/api/src/relaydesk/main.py`, beside the existing `app.include_router(api_router, prefix="/api")`:

```python
from relaydesk.api.v1.router import v1_router

app.include_router(v1_router, prefix="/v1")
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/test_v1_auth.py tests/test_v1_conversations_read.py -v`
Expected: PASS, 10 + 12 tests.

- [ ] **Step 11: Verify the whole suite and lint**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add apps/api/src/relaydesk/api/v1/ \
        apps/api/src/relaydesk/services/conversations.py \
        apps/api/src/relaydesk/schemas/v1.py \
        apps/api/src/relaydesk/errors.py \
        apps/api/src/relaydesk/main.py \
        apps/api/tests/test_v1_auth.py \
        apps/api/tests/test_v1_conversations_read.py
git commit -m "feat(api): serve conversations over the public v1 API"
```

---

### Task 7: `POST /v1/conversations`, idempotent on `external_id`

**Files:**
- Modify: `apps/api/src/relaydesk/services/tickets.py`, `apps/api/src/relaydesk/schemas/v1.py`, `apps/api/src/relaydesk/api/v1/conversations.py`
- Test: `apps/api/tests/test_v1_conversations_create.py`

**Interfaces:**
- Consumes: `services.contacts.upsert`, `services.conversations.create_conversation`, `append_message`, `record`; `Actor` (Task 3); `Conversation.external_id`/`.meta` (Task 5); `ApiPrincipal` (Task 6).
- Produces: `services.tickets.create_from_api(session, workspace_id, *, email: str, name: str, subject: str, message: str, priority: Priority, external_id: str | None, metadata: dict, actor: Actor) -> tuple[Conversation, bool]` where the bool is `created`. And `schemas.v1.ConversationCreate`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_v1_conversations_create.py`:

```python
import asyncio

import sqlalchemy as sa

from relaydesk.models import (
    ActivityEvent,
    ActivityKind,
    ApiKeyScope,
    Channel,
    Contact,
    Conversation,
    Message,
    MessageDirection,
    MessageRole,
)
from relaydesk.services import api_keys
from tests.factories import make_workspace

BODY = {
    "customer_email": "customer@example.com",
    "customer_name": "Priya Raman",
    "subject": "Help with order",
    "message": "I need help with my recent order.",
    "priority": "high",
    "external_id": "ticket-123",
    "metadata": {"order_id": "ord_456", "plan": "growth"},
}


async def writer(db_session, workspace, name="Production ingest"):
    token, key = await api_keys.mint(
        db_session,
        workspace.id,
        name=name,
        scopes=[ApiKeyScope.conversations_write],
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}, key


async def test_the_published_code_sample_works_verbatim(client, db_session) -> None:
    """The exact body ``components/settings/code-sample.tsx`` publishes."""
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    response = await client.post("/v1/conversations", json=BODY, headers=headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["subject"] == "Help with order"
    assert body["priority"] == "high"
    assert body["channel"] == "api"
    assert body["external_id"] == "ticket-123"
    assert body["metadata"] == {"order_id": "ord_456", "plan": "growth"}
    assert body["customer"]["email"] == "customer@example.com"
    assert body["customer"]["name"] == "Priya Raman"


async def test_the_first_message_is_the_customers(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    created = (
        await client.post("/v1/conversations", json=BODY, headers=headers)
    ).json()

    stored = list(
        await db_session.scalars(
            sa.select(Message).where(Message.conversation_id == created["id"])
        )
    )
    assert len(stored) == 1
    assert stored[0].role is MessageRole.customer
    assert stored[0].direction is MessageDirection.inbound
    assert stored[0].body == "I need help with my recent order."
    assert stored[0].author_name == "Priya Raman"


async def test_creation_is_recorded_against_the_key(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, key = await writer(db_session, workspace)

    created = (
        await client.post("/v1/conversations", json=BODY, headers=headers)
    ).json()

    event = await db_session.scalar(
        sa.select(ActivityEvent).where(
            ActivityEvent.conversation_id == created["id"],
            ActivityEvent.kind == ActivityKind.created,
        )
    )
    assert event is not None
    assert event.actor_api_key_id == key.id
    assert event.actor_user_id is None
    assert event.actor_name == "Production ingest"


async def test_a_repeated_external_id_returns_the_first_conversation(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    first = await client.post("/v1/conversations", json=BODY, headers=headers)
    second = await client.post("/v1/conversations", json=BODY, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    total = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Conversation)
        .where(Conversation.workspace_id == workspace.id)
    )
    assert total == 1


async def test_two_workspaces_may_use_the_same_external_id(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    our_headers, _ = await writer(db_session, ours)
    their_headers, _ = await writer(db_session, theirs, name="Theirs")

    first = await client.post("/v1/conversations", json=BODY, headers=our_headers)
    second = await client.post("/v1/conversations", json=BODY, headers=their_headers)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]


async def test_a_creation_without_an_external_id_is_never_deduplicated(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)
    body = {key: value for key, value in BODY.items() if key != "external_id"}

    first = await client.post("/v1/conversations", json=body, headers=headers)
    second = await client.post("/v1/conversations", json=body, headers=headers)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]


async def test_a_repeat_reuses_the_contact(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)
    body = {key: value for key, value in BODY.items() if key != "external_id"}

    await client.post("/v1/conversations", json=body, headers=headers)
    await client.post("/v1/conversations", json=body, headers=headers)

    total = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Contact)
        .where(Contact.workspace_id == workspace.id)
    )
    assert total == 1


async def test_a_blank_message_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    response = await client.post(
        "/v1/conversations",
        json={**BODY, "message": "   ", "external_id": "blank"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_oversized_metadata_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    response = await client.post(
        "/v1/conversations",
        json={**BODY, "external_id": "big", "metadata": {"blob": "x" * 9000}},
        headers=headers,
    )

    assert response.status_code == 422


async def test_too_many_metadata_keys_are_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    response = await client.post(
        "/v1/conversations",
        json={
            **BODY,
            "external_id": "many",
            "metadata": {f"k{index}": index for index in range(51)},
        },
        headers=headers,
    )

    assert response.status_code == 422


async def test_a_read_only_key_cannot_create(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Reporting",
        scopes=[ApiKeyScope.conversations_read],
        created_by_user_id=None,
    )

    response = await client.post(
        "/v1/conversations",
        json=BODY,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "conversations:write" in response.json()["error"]["message"]


async def test_two_concurrent_creates_with_one_external_id_make_one_row(
    db_session, engine
) -> None:
    """The savepoint in ``create_from_api``, exercised.

    Both callers miss the lookup, both insert, and the partial unique index
    refuses the loser. The loser must return the winner's conversation, not
    an unhandled IntegrityError -> 500.

    Its own sessions, not the ``db_session`` fixture: that fixture wraps
    everything in one outer transaction, which concurrent connections cannot
    see. Its writes are therefore real, and it cleans up after itself.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from relaydesk.models import Priority, Workspace
    from relaydesk.services import tickets
    from relaydesk.services.actors import Actor

    workspace = await make_workspace(db_session)
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name="Importer",
        scopes=[ApiKeyScope.conversations_write],
        created_by_user_id=None,
    )
    await db_session.commit()

    async def create_once():
        async with AsyncSession(bind=engine, expire_on_commit=False) as session:
            conversation, created = await tickets.create_from_api(
                session,
                workspace.id,
                email="customer@example.com",
                name="Priya Raman",
                subject="Help with order",
                message="I need help with my recent order.",
                priority=Priority.high,
                external_id="race-1",
                metadata={},
                actor=Actor.for_key(key),
            )
            return str(conversation.id), created

    results = await asyncio.gather(create_once(), create_once())

    assert len({identifier for identifier, _ in results}) == 1
    assert sorted(created for _, created in results) == [False, True]

    async with engine.begin() as connection:
        await connection.execute(
            sa.delete(Workspace.__table__).where(
                Workspace.__table__.c.id == workspace.id
            )
        )


async def test_the_conversation_is_channel_api(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    created = (
        await client.post("/v1/conversations", json=BODY, headers=headers)
    ).json()

    stored = await db_session.scalar(
        sa.select(Conversation).where(Conversation.id == created["id"])
    )
    assert stored.channel is Channel.api
```

Note: `test_the_first_message_is_the_customers` asserts through the database rather than the API because the second key it mints deliberately lacks `conversations:read` — the point being that create and read are separate grants.

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_v1_conversations_create.py -v`
Expected: FAIL — `405 Method Not Allowed`, since only GET routes are mounted.

- [ ] **Step 3: Write the create service**

Append to `apps/api/src/relaydesk/services/tickets.py`:

```python
async def create_from_api(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    email: str,
    name: str,
    subject: str,
    message: str,
    priority: Priority,
    external_id: str | None,
    metadata: dict,
    actor: Actor,
) -> tuple[Conversation, bool]:
    """Open a ticket on behalf of an API caller.

    Returns ``(conversation, created)``. ``created`` is ``False`` when
    ``external_id`` matched a conversation this workspace already has, which
    is what makes an interrupted import safe to re-run: the caller retries
    the whole batch and gets its original tickets back rather than a second
    copy of each.

    Composes the same services email ingest and the portal form use, so an
    API ticket is the same rows as an emailed one. The differences are the
    channel, the caller's own identifier, and the activity event: unlike
    inbound mail, this creation has a principal, and recording it is what
    makes "show me everything this key did" answerable later.
    """
    body = message.strip()
    if not body:
        raise Invalid("A message is required.")
    if len(body) > get_settings().ticket_message_max_chars:
        raise Invalid("That message is too long.")

    if external_id:
        existing = await session.scalar(
            sa.select(Conversation).where(
                Conversation.workspace_id == workspace_id,
                Conversation.external_id == external_id,
            )
        )
        if existing is not None:
            return existing, False

    display_name = name.strip() or email
    contact = await contacts.upsert(session, workspace_id, email, display_name)

    now = datetime.now(UTC)
    conversation = await conversations.create_conversation(
        session,
        workspace_id,
        contact,
        subject.strip() or f"Message from {display_name}",
        Channel.api,
        now,
    )
    # See the note in ``submit``: ``create_conversation`` sets ``contact_id``
    # but not the relationship, and a selectin strategy does not fire for an
    # object this call just constructed.
    conversation.contact = contact
    conversation.priority = priority
    conversation.external_id = external_id
    conversation.meta = metadata

    await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name=display_name,
        body=body,
        sent_at=now,
    )
    conversations.record(
        session,
        conversation,
        actor,
        ActivityKind.created,
        "opened this through the API",
        "",
    )

    try:
        # A savepoint, not a bare flush. Two concurrent creates carrying the
        # same external_id both miss the lookup above and both insert; the
        # partial unique index refuses the loser, and only this savepoint
        # unwinds rather than the whole transaction. Same shape as the race
        # ``contacts.upsert`` handles.
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        if not external_id:
            raise
        existing = await session.scalar(
            sa.select(Conversation).where(
                Conversation.workspace_id == workspace_id,
                Conversation.external_id == external_id,
            )
        )
        if existing is None:
            raise
        return existing, False

    await session.commit()
    await session.refresh(conversation, ["labels", "assignee"])
    return conversation, True
```

Extend the module's imports to cover what this uses:

```python
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.models.activity import ActivityKind
from relaydesk.models.conversation import Channel, Conversation, Priority
from relaydesk.services.actors import Actor
```

- [ ] **Step 4: Add the request schema**

Append to `apps/api/src/relaydesk/schemas/v1.py`:

```python
class ConversationCreate(V1Model):
    """The body ``components/settings/code-sample.tsx`` publishes.

    ``customer_email`` and ``message`` are required; everything else is
    optional, exactly as the sample's own description says.
    """

    customer_email: EmailStr
    message: str = Field(min_length=1)
    customer_name: str = ""
    subject: str = ""
    priority: Priority = Priority.medium
    external_id: str | None = Field(default=None, max_length=200)
    metadata: Metadata = Field(default_factory=dict)
```

Add `from pydantic import EmailStr` and `from relaydesk.models import Priority` to the module's imports.

- [ ] **Step 5: Add the route**

Append to `apps/api/src/relaydesk/api/v1/conversations.py`:

```python
Writer = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.conversations_write))]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: ConversationCreate,
    principal: Writer,
    session: DbSession,
    response: Response,
) -> ConversationOut:
    """Open a ticket.

    Answers 201 for a new conversation and 200 when ``external_id`` matched
    one this workspace already has -- so a caller retrying a batch can tell
    what it actually created without the retry costing anything.
    """
    conversation, created = await tickets.create_from_api(
        session,
        principal.workspace_id,
        email=payload.customer_email,
        name=payload.customer_name,
        subject=payload.subject,
        message=payload.message,
        priority=payload.priority,
        external_id=payload.external_id,
        metadata=payload.metadata,
        actor=principal.actor,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return conversation_out(conversation)
```

Extend the module's imports: `from fastapi import APIRouter, Depends, Query, Response, status`, `from relaydesk.schemas.v1 import ConversationCreate` (added to the existing import list), and `from relaydesk.services import conversations, tickets`.

- [ ] **Step 6: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_v1_conversations_create.py -v`
Expected: PASS, 13 tests.

- [ ] **Step 7: Verify the whole suite and lint**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/relaydesk/services/tickets.py \
        apps/api/src/relaydesk/schemas/v1.py \
        apps/api/src/relaydesk/api/v1/conversations.py \
        apps/api/tests/test_v1_conversations_create.py
git commit -m "feat(api): create conversations over v1, idempotent on external_id"
```

---

### Task 8: Updating a conversation and replying to it

**Files:**
- Modify: `apps/api/src/relaydesk/schemas/v1.py`, `apps/api/src/relaydesk/api/v1/conversations.py`
- Test: `apps/api/tests/test_v1_conversations_write.py`

**Interfaces:**
- Consumes: `services.conversations.set_status`, `set_priority`, `set_assignee`, `add_reply` (all taking `Actor` after Task 3); `ApiPrincipal.actor`.
- Produces: `schemas.v1.ConversationUpdate`, `schemas.v1.MessageCreate`; `PATCH /v1/conversations/{id}`, `POST /v1/conversations/{id}/messages`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_v1_conversations_write.py`:

```python
import sqlalchemy as sa

from relaydesk.models import (
    ApiKeyScope,
    ConversationStatus,
    DeliveryState,
    Message,
    MessageRole,
    Priority,
)
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_member, make_workspace


async def key_for(db_session, workspace, scopes, name="Integration"):
    token, key = await api_keys.mint(
        db_session,
        workspace.id,
        name=name,
        scopes=scopes,
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}, key


async def test_patch_changes_the_status(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"status": "resolved"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


async def test_patch_changes_the_priority(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(
        db_session, workspace, priority=Priority.low
    )
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"priority": "urgent"},
        headers=headers,
    )

    assert response.json()["priority"] == "urgent"


async def test_patch_assigns_to_a_member(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    member = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"assignee_id": str(member.id)},
        headers=headers,
    )

    assert response.json()["assignee_id"] == str(member.id)


async def test_an_empty_patch_changes_nothing(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}", json={}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "open"


async def test_patch_on_another_workspace_answers_404(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers, _ = await key_for(db_session, ours, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{hidden.id}", json={"status": "resolved"}, headers=headers
    )

    assert response.status_code == 404


async def test_a_key_without_conversations_write_cannot_patch(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_read])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"status": "resolved"},
        headers=headers,
    )

    assert response.status_code == 403


async def test_a_reply_is_queued_for_delivery_and_attributed_to_the_key(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, key = await key_for(
        db_session, workspace, [ApiKeyScope.messages_write], name="Support bot"
    )

    response = await client.post(
        f"/v1/conversations/{conversation.id}/messages",
        json={"body": "We have refunded your order."},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "agent"
    assert response.json()["author_name"] == "Support bot"

    message = await db_session.scalar(
        sa.select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.sent_at.desc())
    )
    assert message.role is MessageRole.agent
    assert message.author_api_key_id == key.id
    assert message.author_user_id is None
    assert message.delivery_state is DeliveryState.queued


async def test_conversations_write_alone_cannot_reply(client, db_session) -> None:
    """The whole point of splitting the two scopes (spec D5).

    A triage integration that labels and prioritises must not be one bug
    away from mailing a customer.
    """
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.post(
        f"/v1/conversations/{conversation.id}/messages",
        json={"body": "Hello."},
        headers=headers,
    )

    assert response.status_code == 403
    assert "messages:write" in response.json()["error"]["message"]


async def test_a_blank_reply_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.messages_write])

    response = await client.post(
        f"/v1/conversations/{conversation.id}/messages",
        json={"body": "   "},
        headers=headers,
    )

    assert response.status_code == 422


async def test_replying_into_another_workspace_answers_404(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers, _ = await key_for(db_session, ours, [ApiKeyScope.messages_write])

    response = await client.post(
        f"/v1/conversations/{hidden.id}/messages",
        json={"body": "Hello."},
        headers=headers,
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_v1_conversations_write.py -v`
Expected: FAIL — `405 Method Not Allowed`.

- [ ] **Step 3: Add the request schemas**

Append to `apps/api/src/relaydesk/schemas/v1.py`:

```python
class ConversationUpdate(V1Model):
    """Every field optional. An omitted field is left alone, which is what
    makes it safe for two integrations to update different fields of the
    same conversation without either clobbering the other."""

    status: ConversationStatus | None = None
    priority: Priority | None = None
    assignee_id: uuid.UUID | None = None


class MessageCreate(V1Model):
    body: str = Field(min_length=1)
```

Add `import uuid` and extend the models import to `from relaydesk.models import Contact, Conversation, ConversationStatus, Message, Priority`.

- [ ] **Step 4: Add the routes**

Append to `apps/api/src/relaydesk/api/v1/conversations.py`:

```python
Replier = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.messages_write))]


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_route(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    principal: Writer,
    session: DbSession,
) -> ConversationOut:
    """Change status, priority or assignee.

    Reads the conversation first so an id belonging to another workspace
    answers 404 before any field is considered -- including for an empty
    body, which must not become a way to probe for ids that exist.
    """
    conversation = await conversations.get_conversation(
        session, principal.workspace_id, conversation_id
    )
    actor = principal.actor

    if payload.status is not None:
        conversation = await conversations.set_status(
            session, principal.workspace_id, conversation_id, payload.status, actor
        )
    if payload.priority is not None:
        conversation = await conversations.set_priority(
            session, principal.workspace_id, conversation_id, payload.priority, actor
        )
    if payload.assignee_id is not None:
        conversation = await conversations.set_assignee(
            session,
            principal.workspace_id,
            conversation_id,
            payload.assignee_id,
            actor,
        )
    return conversation_out(conversation)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_message_route(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    principal: Replier,
    session: DbSession,
) -> MessageOut:
    """Send a reply to the customer.

    Requires ``messages:write``, which ``conversations:write`` does not
    imply: this one puts mail in a customer's inbox under the workspace's
    name, and the delivery is queued the moment it returns.
    """
    await conversations.add_reply(
        session,
        principal.workspace_id,
        conversation_id,
        payload.body,
        principal.actor,
    )
    messages = await conversations.list_messages(
        session, principal.workspace_id, conversation_id
    )
    return message_out(messages[-1])
```

Extend the module's imports with `ConversationUpdate` and `MessageCreate` from `relaydesk.schemas.v1`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_v1_conversations_write.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 6: Verify the whole suite and lint**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/schemas/v1.py \
        apps/api/src/relaydesk/api/v1/conversations.py \
        apps/api/tests/test_v1_conversations_write.py
git commit -m "feat(api): update and reply to conversations over v1"
```

---

### Task 9: Labels and contacts

**Files:**
- Create: `apps/api/src/relaydesk/services/pagination.py`, `apps/api/src/relaydesk/api/v1/labels.py`, `apps/api/src/relaydesk/api/v1/contacts.py`
- Modify: `apps/api/src/relaydesk/services/contacts.py`, `apps/api/src/relaydesk/services/conversations.py`, `apps/api/src/relaydesk/schemas/v1.py`, `apps/api/src/relaydesk/api/v1/conversations.py`, `apps/api/src/relaydesk/api/v1/router.py`
- Test: `apps/api/tests/test_v1_labels.py`, `apps/api/tests/test_v1_contacts.py`

**Interfaces:**
- Produces:
  - `services.pagination.encode(moment: datetime, identifier: uuid.UUID) -> str` and `decode(cursor: str) -> tuple[datetime, uuid.UUID]`.
  - `services.contacts.list_contacts(session, workspace_id, *, limit: int = 50, cursor: str | None = None) -> tuple[list[Contact], str | None]` and `get_contact(session, workspace_id, contact_id) -> Contact`.
  - `schemas.v1.LabelOut`, `LabelCreate`, `ContactPage`.
  - `GET /v1/labels`, `POST /v1/labels`, `PUT /v1/conversations/{id}/labels/{label_id}`, `DELETE /v1/conversations/{id}/labels/{label_id}`, `GET /v1/contacts`, `GET /v1/contacts/{id}`.

- [ ] **Step 1: Write the failing label test**

Create `apps/api/tests/test_v1_labels.py`:

```python
from relaydesk.models import ApiKeyScope
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_label, make_workspace


async def key_for(db_session, workspace, scopes):
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Integration",
        scopes=scopes,
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_labels_are_listed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_label(db_session, workspace, name="Billing")
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_read])

    response = await client.get("/v1/labels", headers=headers)

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Billing"]


async def test_only_this_workspaces_labels_are_listed(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    await make_label(db_session, ours, name="Ours")
    await make_label(db_session, theirs, name="Theirs")
    headers = await key_for(db_session, ours, [ApiKeyScope.labels_read])

    response = await client.get("/v1/labels", headers=headers)

    assert [item["name"] for item in response.json()] == ["Ours"]


async def test_a_label_is_created(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_write])

    response = await client.post(
        "/v1/labels", json={"name": "Refunds"}, headers=headers
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Refunds"


async def test_creating_the_same_label_twice_returns_the_first(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_write])

    first = await client.post("/v1/labels", json={"name": "Refunds"}, headers=headers)
    second = await client.post("/v1/labels", json={"name": "refunds"}, headers=headers)

    assert first.json()["id"] == second.json()["id"]


async def test_labels_read_alone_cannot_create(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_read])

    response = await client.post("/v1/labels", json={"name": "X"}, headers=headers)

    assert response.status_code == 403


async def test_a_label_is_applied_and_removed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    label = await make_label(db_session, workspace)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_write])

    applied = await client.put(
        f"/v1/conversations/{conversation.id}/labels/{label.id}", headers=headers
    )
    assert applied.status_code == 200
    assert applied.json()["label_ids"] == [str(label.id)]

    removed = await client.delete(
        f"/v1/conversations/{conversation.id}/labels/{label.id}", headers=headers
    )
    assert removed.status_code == 200
    assert removed.json()["label_ids"] == []


async def test_applying_another_workspaces_label_answers_404(
    client, db_session
) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    conversation = await make_conversation(db_session, ours)
    foreign = await make_label(db_session, theirs, name="Theirs")
    headers = await key_for(db_session, ours, [ApiKeyScope.labels_write])

    response = await client.put(
        f"/v1/conversations/{conversation.id}/labels/{foreign.id}", headers=headers
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Write the failing contacts test**

Create `apps/api/tests/test_v1_contacts.py`:

```python
from relaydesk.models import ApiKeyScope, Contact
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_workspace


async def key_for(db_session, workspace, scopes=None):
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Integration",
        scopes=scopes or [ApiKeyScope.contacts_read],
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_contacts_are_listed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await key_for(db_session, workspace)

    response = await client.get("/v1/contacts", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["email"] for item in body["data"]] == ["priya@northwind.io"]
    assert body["next_cursor"] is None


async def test_only_this_workspaces_contacts_are_listed(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    await make_conversation(db_session, ours, contact_email="ours@example.com")
    await make_conversation(db_session, theirs, contact_email="theirs@example.com")
    headers = await key_for(db_session, ours)

    response = await client.get("/v1/contacts", headers=headers)

    assert [item["email"] for item in response.json()["data"]] == ["ours@example.com"]


async def test_contacts_paginate(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    for index in range(3):
        db_session.add(
            Contact(
                workspace_id=workspace.id,
                email=f"person{index}@example.com",
                name=f"Person {index}",
            )
        )
    await db_session.commit()
    headers = await key_for(db_session, workspace)

    first = await client.get("/v1/contacts", params={"limit": 2}, headers=headers)
    cursor = first.json()["next_cursor"]
    assert cursor is not None

    second = await client.get(
        "/v1/contacts", params={"limit": 2, "cursor": cursor}, headers=headers
    )

    seen = [item["id"] for item in first.json()["data"]] + [
        item["id"] for item in second.json()["data"]
    ]
    assert len(seen) == len(set(seen)) == 3


async def test_one_contact_is_returned(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers = await key_for(db_session, workspace)

    response = await client.get(
        f"/v1/contacts/{conversation.contact_id}", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["email"] == "priya@northwind.io"


async def test_another_workspaces_contact_answers_404(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers = await key_for(db_session, ours)

    response = await client.get(
        f"/v1/contacts/{hidden.contact_id}", headers=headers
    )

    assert response.status_code == 404


async def test_a_key_without_contacts_read_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_read])

    response = await client.get("/v1/contacts", headers=headers)

    assert response.status_code == 403
    assert "contacts:read" in response.json()["error"]["message"]
```

- [ ] **Step 3: Run both tests to verify they fail**

Run: `docker compose exec api pytest tests/test_v1_labels.py tests/test_v1_contacts.py -v`
Expected: FAIL — `404`, nothing is mounted at `/v1/labels` or `/v1/contacts`.

- [ ] **Step 4: Extract the cursor helpers**

Create `apps/api/src/relaydesk/services/pagination.py`:

```python
"""Keyset cursors, shared by every paginated list.

A cursor is an opaque base64 of ``<timestamp>|<uuid>``. The pair is what
makes the cursor stable when two rows share a timestamp, which is why the
uuid is in there at all.

Extracted from ``services.conversations`` when contacts became the second
list to need it. Callers keep their own encode function so each list names
the timestamp column it orders by; only the format lives here.
"""

import base64
import uuid
from datetime import datetime


def encode(moment: datetime, identifier: uuid.UUID) -> str:
    raw = f"{moment.isoformat()}|{identifier}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Raises ``ValueError`` on anything malformed.

    ``binascii.Error`` and ``UnicodeDecodeError`` both subclass ``ValueError``,
    so a bad base64 payload arrives here as one error type and callers can
    turn it into a single ``Invalid``.
    """
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    moment, identifier = raw.split("|", 1)
    return datetime.fromisoformat(moment), uuid.UUID(identifier)
```

In `apps/api/src/relaydesk/services/conversations.py`, replace the two cursor functions with delegating ones and drop the now-unused `base64` import:

```python
def encode_cursor(conversation: Conversation) -> str:
    return pagination.encode(conversation.last_message_at, conversation.id)


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    return pagination.decode(cursor)
```

Add `pagination` to the `from relaydesk.services import ...` line.

- [ ] **Step 5: Add the contact queries**

Append to `apps/api/src/relaydesk/services/contacts.py`:

```python
DEFAULT_LIMIT = 50


async def list_contacts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[Contact], str | None]:
    """Keyset-paginated contacts, newest first.

    Ordered by ``(created_at, id)`` for the same reason the inbox list is:
    the pair keeps the cursor stable when two rows share a timestamp, which
    they will whenever a batch is imported inside one transaction.
    """
    query = sa.select(Contact).where(Contact.workspace_id == workspace_id)

    if cursor:
        try:
            moment, identifier = pagination.decode(cursor)
        except ValueError as error:
            raise Invalid("Invalid cursor.") from error
        query = query.where(
            sa.tuple_(Contact.created_at, Contact.id) < (moment, identifier)
        )

    query = query.order_by(Contact.created_at.desc(), Contact.id.desc()).limit(
        limit + 1
    )
    rows = list(await session.scalars(query))
    next_cursor = (
        pagination.encode(rows[limit - 1].created_at, rows[limit - 1].id)
        if len(rows) > limit
        else None
    )
    return rows[:limit], next_cursor


async def get_contact(
    session: AsyncSession, workspace_id: uuid.UUID, contact_id: uuid.UUID
) -> Contact:
    """Cross-workspace ids raise NotFound, never Forbidden."""
    contact = await session.scalar(
        sa.select(Contact).where(
            Contact.id == contact_id, Contact.workspace_id == workspace_id
        )
    )
    if contact is None:
        raise NotFound("Contact not found.")
    return contact
```

Add `from relaydesk.errors import Invalid, NotFound` and `from relaydesk.services import pagination` to the module's imports.

- [ ] **Step 6: Add the schemas**

Append to `apps/api/src/relaydesk/schemas/v1.py`:

```python
class LabelOut(V1Model):
    id: str
    name: str
    color: str


class LabelCreate(V1Model):
    name: str = Field(min_length=1, max_length=80)


class ContactPage(V1Model):
    data: list[ContactOut]
    next_cursor: str | None = None


def label_out(label: Label) -> LabelOut:
    return LabelOut(id=str(label.id), name=label.name, color=label.color.value)
```

Extend the models import with `Label`.

- [ ] **Step 7: Add the label routes**

Create `apps/api/src/relaydesk/api/v1/labels.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, status

from relaydesk.api.deps import DbSession
from relaydesk.api.v1.deps import ApiPrincipal, requires
from relaydesk.models import ApiKeyScope
from relaydesk.schemas.v1 import LabelCreate, LabelOut, label_out
from relaydesk.services import labels

router = APIRouter()

Reader = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.labels_read))]
Writer = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.labels_write))]


@router.get("", response_model=list[LabelOut])
async def list_route(principal: Reader, session: DbSession) -> list[LabelOut]:
    rows = await labels.list_labels(session, principal.workspace_id)
    return [label_out(row) for row in rows]


@router.post("", response_model=LabelOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: LabelCreate, principal: Writer, session: DbSession
) -> LabelOut:
    """Idempotent by name -- ``labels.name`` is CITEXT, so "Refunds" and
    "refunds" are the same label and a repeat returns the existing one."""
    label = await labels.create_label(session, principal.workspace_id, payload.name)
    return label_out(label)
```

Append the conversation-label routes to `apps/api/src/relaydesk/api/v1/conversations.py`:

```python
Labeller = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.labels_write))]


@router.put("/{conversation_id}/labels/{label_id}", response_model=ConversationOut)
async def add_label_route(
    conversation_id: uuid.UUID,
    label_id: uuid.UUID,
    principal: Labeller,
    session: DbSession,
) -> ConversationOut:
    conversation = await conversations.add_label(
        session, principal.workspace_id, conversation_id, label_id, principal.actor
    )
    return conversation_out(conversation)


@router.delete("/{conversation_id}/labels/{label_id}", response_model=ConversationOut)
async def remove_label_route(
    conversation_id: uuid.UUID,
    label_id: uuid.UUID,
    principal: Labeller,
    session: DbSession,
) -> ConversationOut:
    conversation = await conversations.remove_label(
        session, principal.workspace_id, conversation_id, label_id, principal.actor
    )
    return conversation_out(conversation)
```

- [ ] **Step 8: Add the contact routes**

Create `apps/api/src/relaydesk/api/v1/contacts.py`:

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from relaydesk.api.deps import DbSession
from relaydesk.api.v1.deps import ApiPrincipal, requires
from relaydesk.models import ApiKeyScope
from relaydesk.schemas.v1 import ContactOut, ContactPage, contact_out
from relaydesk.services import contacts

router = APIRouter()

Reader = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.contacts_read))]


@router.get("", response_model=ContactPage)
async def list_route(
    principal: Reader,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> ContactPage:
    rows, next_cursor = await contacts.list_contacts(
        session, principal.workspace_id, limit=limit, cursor=cursor
    )
    return ContactPage(
        data=[contact_out(row) for row in rows], next_cursor=next_cursor
    )


@router.get("/{contact_id}", response_model=ContactOut)
async def get_route(
    contact_id: uuid.UUID, principal: Reader, session: DbSession
) -> ContactOut:
    contact = await contacts.get_contact(session, principal.workspace_id, contact_id)
    return contact_out(contact)
```

- [ ] **Step 9: Mount both routers**

In `apps/api/src/relaydesk/api/v1/router.py`:

```python
from relaydesk.api.v1.contacts import router as contacts_router
from relaydesk.api.v1.labels import router as labels_router

v1_router.include_router(labels_router, prefix="/labels", tags=["v1: labels"])
v1_router.include_router(contacts_router, prefix="/contacts", tags=["v1: contacts"])
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/test_v1_labels.py tests/test_v1_contacts.py -v`
Expected: PASS, 7 + 6 tests.

- [ ] **Step 11: Verify the whole suite and lint**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS. `tests/test_conversations_read.py` exercises the console cursor and proves the delegation in Step 4 did not change its format.

- [ ] **Step 12: Commit**

```bash
git add apps/api/src/relaydesk/services/pagination.py \
        apps/api/src/relaydesk/services/contacts.py \
        apps/api/src/relaydesk/services/conversations.py \
        apps/api/src/relaydesk/schemas/v1.py \
        apps/api/src/relaydesk/api/v1/ \
        apps/api/tests/test_v1_labels.py \
        apps/api/tests/test_v1_contacts.py
git commit -m "feat(api): serve labels and contacts over v1"
```

---

### Task 10: Console key management

**Files:**
- Create: `apps/api/src/relaydesk/api/api_keys.py`, `apps/api/src/relaydesk/schemas/api_key.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Test: `apps/api/tests/test_api_keys_api.py`

**Interfaces:**
- Consumes: `services.api_keys` (Task 2), `api.deps.Scope`, `WorkspaceScope.require_admin`.
- Produces: `GET /api/api-keys`, `POST /api/api-keys`, `DELETE /api/api-keys/{key_id}`. Response schemas are camelCase (`CamelModel`) because this surface is the console's, not the public one.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_api_keys_api.py`:

```python
from relaydesk.models import ApiKeyScope, Role
from tests.factories import make_member, make_workspace, sign_in


async def admin_headers(client, db_session, workspace):
    await make_member(db_session, workspace, email="admin@relaydesk.dev")
    await db_session.commit()
    return await sign_in(client, db_session, "admin@relaydesk.dev")


async def agent_headers(client, db_session, workspace):
    await make_member(
        db_session, workspace, email="agent@relaydesk.dev", role=Role.agent
    )
    await db_session.commit()
    return await sign_in(client, db_session, "agent@relaydesk.dev")


async def test_an_admin_creates_a_key_and_sees_the_secret_once(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    created = await client.post(
        "/api/api-keys",
        json={
            "name": "Production ingest",
            "scopes": ["conversations:read", "conversations:write"],
        },
        headers=headers,
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["token"].startswith("rd_")
    assert body["key"]["name"] == "Production ingest"
    assert body["key"]["prefix"] == body["token"][:7]
    assert body["key"]["scopes"] == ["conversations:read", "conversations:write"]

    listed = await client.get("/api/api-keys", headers=headers)
    assert [item["name"] for item in listed.json()] == ["Production ingest"]
    # The secret is never offered again, in any field.
    assert body["token"] not in listed.text


async def test_an_agent_cannot_manage_keys(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await agent_headers(client, db_session, workspace)

    listed = await client.get("/api/api-keys", headers=headers)
    created = await client.post(
        "/api/api-keys",
        json={"name": "Sneaky", "scopes": ["conversations:read"]},
        headers=headers,
    )

    assert listed.status_code == 403
    assert created.status_code == 403


async def test_an_unknown_scope_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.post(
        "/api/api-keys",
        json={"name": "Bad", "scopes": ["workspace:destroy"]},
        headers=headers,
    )

    assert response.status_code == 422


async def test_a_revoked_key_disappears_from_the_list(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post(
        "/api/api-keys",
        json={"name": "Temporary", "scopes": ["conversations:read"]},
        headers=headers,
    )
    key_id = created.json()["key"]["id"]

    deleted = await client.delete(f"/api/api-keys/{key_id}", headers=headers)

    assert deleted.status_code == 204
    assert (await client.get("/api/api-keys", headers=headers)).json() == []


async def test_a_revoked_key_stops_working_immediately(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post(
        "/api/api-keys",
        json={"name": "Temporary", "scopes": ["conversations:read"]},
        headers=headers,
    )
    token = created.json()["token"]
    assert (
        await client.get(
            "/v1/conversations", headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 200

    await client.delete(f"/api/api-keys/{created.json()['key']['id']}", headers=headers)

    after = await client.get(
        "/v1/conversations", headers={"Authorization": f"Bearer {token}"}
    )
    assert after.status_code == 401


async def test_an_admin_cannot_revoke_another_workspaces_key(
    client, db_session
) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    from relaydesk.services import api_keys

    _, foreign = await api_keys.mint(
        db_session,
        theirs.id,
        name="Theirs",
        scopes=[ApiKeyScope.conversations_read],
        created_by_user_id=None,
    )
    headers = await admin_headers(client, db_session, ours)

    response = await client.delete(f"/api/api-keys/{foreign.id}", headers=headers)

    assert response.status_code == 404
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec api pytest tests/test_api_keys_api.py -v`
Expected: FAIL — `404`, nothing is mounted at `/api/api-keys`.

- [ ] **Step 3: Write the schemas**

Create `apps/api/src/relaydesk/schemas/api_key.py`:

```python
from datetime import datetime

from pydantic import Field

from relaydesk.models import ApiKeyScope
from relaydesk.schemas.base import CamelModel


class ApiKeyOut(CamelModel):
    """What the settings list shows. Never the secret.

    ``CamelModel``, unlike everything in ``schemas.v1``: this is the
    console's own surface and matches its TypeScript types field for field.
    """

    id: str
    name: str
    prefix: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[ApiKeyScope] = Field(min_length=1)


class ApiKeyCreated(CamelModel):
    """The one response that carries the plaintext token.

    It is not recoverable afterwards -- only the SHA-256 digest is stored --
    which is why the dialog says the key is shown once and why rotation is
    "create a new one, delete the old one" rather than a reveal.
    """

    token: str
    key: ApiKeyOut
```

- [ ] **Step 4: Write the routes**

Create `apps/api/src/relaydesk/api/api_keys.py`:

```python
import uuid

from fastapi import APIRouter, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models import ApiKey
from relaydesk.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from relaydesk.services import api_keys

router = APIRouter()


def _out(key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=str(key.id),
        name=key.name,
        prefix=key.prefix,
        scopes=list(key.scopes),
        created_at=key.created_at,
        last_used_at=key.last_used_at,
    )


@router.get("", response_model=list[ApiKeyOut])
async def list_route(scope: Scope, session: DbSession) -> list[ApiKeyOut]:
    scope.require_admin()
    rows = await api_keys.list_keys(session, scope.workspace_id)
    return [_out(row) for row in rows]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: ApiKeyCreate, scope: Scope, session: DbSession
) -> ApiKeyCreated:
    """Mint a key and return its secret, once.

    Admin only: a key is a credential for the whole workspace, and handing
    an agent the ability to mint one with ``messages:write`` would be
    handing them a way to mail customers from outside the console with no
    session to revoke.
    """
    scope.require_admin()
    token, key = await api_keys.mint(
        session,
        scope.workspace_id,
        name=payload.name,
        scopes=payload.scopes,
        created_by_user_id=scope.user.id,
    )
    return ApiKeyCreated(token=token, key=_out(key))


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_route(key_id: uuid.UUID, scope: Scope, session: DbSession) -> None:
    scope.require_admin()
    await api_keys.revoke(session, scope.workspace_id, key_id)
```

In `apps/api/src/relaydesk/api/router.py`, import the router and mount it after `workspace_router`:

```python
from relaydesk.api.api_keys import router as api_keys_router

api_router.include_router(api_keys_router, prefix="/api-keys", tags=["api-keys"])
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `docker compose exec api pytest tests/test_api_keys_api.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 6: Verify the whole suite and lint**

Run: `docker compose exec api pytest -m "not integration" && docker compose exec api ruff check .`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/api/api_keys.py \
        apps/api/src/relaydesk/schemas/api_key.py \
        apps/api/src/relaydesk/api/router.py \
        apps/api/tests/test_api_keys_api.py
git commit -m "feat(api): manage API keys from the console"
```

---

### Task 11: Wire the console page to the real API

The page, the dialog and the code sample already exist as shells reading `lib/mock/settings.ts`. This replaces the mock with the endpoints from Task 10 and grows the dialog a scope picker.

**Files:**
- Create: `apps/web/lib/api/api-keys.ts`, `apps/web/app/(console)/settings/api-keys/actions.ts`, `apps/web/components/settings/api-key-actions.tsx`
- Modify: `apps/web/lib/types.ts`, `apps/web/lib/mock/settings.ts`, `apps/web/app/(console)/settings/api-keys/page.tsx`, `apps/web/components/settings/api-key-dialog.tsx`, `apps/web/components/settings/code-sample.tsx`

**Interfaces:**
- Consumes: `GET/POST/DELETE /api/api-keys` (Task 10), `lib/api/client.ts`'s `apiFetch` and `ApiError`.
- Produces: `getApiKeys()`, `createApiKey(name, scopes)`, `revokeApiKey(id)` in `lib/api/api-keys.ts`; `createApiKeyAction`, `revokeApiKeyAction` in the page's `actions.ts`; the `ApiKeyScope` union and an extended `ApiKey` in `lib/types.ts`.

- [ ] **Step 1: Extend the types**

In `apps/web/lib/types.ts`, replace the `ApiKey` interface:

```ts
export type ApiKeyScope =
  | "conversations:read"
  | "conversations:write"
  | "messages:write"
  | "contacts:read"
  | "labels:read"
  | "labels:write";

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: ApiKeyScope[];
  createdAt: string;
  lastUsedAt: string | null;
}

export interface ApiKeyCreated {
  token: string;
  key: ApiKey;
}
```

- [ ] **Step 2: Add the API client**

Create `apps/web/lib/api/api-keys.ts`:

```ts
import "server-only";

import { cache } from "react";

import { apiFetch } from "./client";
import type { ApiKey, ApiKeyCreated, ApiKeyScope } from "@/lib/types";

export const getApiKeys = cache(async (): Promise<ApiKey[]> => {
  return apiFetch<ApiKey[]>("/api-keys");
});

export async function createApiKey(
  name: string,
  scopes: ApiKeyScope[],
): Promise<ApiKeyCreated> {
  return apiFetch<ApiKeyCreated>("/api-keys", {
    method: "POST",
    body: JSON.stringify({ name, scopes }),
  });
}

export async function revokeApiKey(id: string): Promise<void> {
  await apiFetch(`/api-keys/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 3: Add the server actions**

Create `apps/web/app/(console)/settings/api-keys/actions.ts`:

```ts
"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api/client";
import { createApiKey, revokeApiKey } from "@/lib/api/api-keys";
import type { ApiKeyScope } from "@/lib/types";

export type ApiKeyActionResult =
  | { ok: true; token: string }
  | { ok: false; message: string };

export type RevokeResult = { ok: true } | { ok: false; message: string };

function refresh() {
  revalidatePath("/", "layout");
}

/**
 * The token comes back to the browser exactly once, here.
 *
 * It is not stored anywhere the page can read again: the API keeps only a
 * SHA-256 digest, so if the dialog is dismissed before the value is copied,
 * the only recourse is to create another key and delete this one. That is
 * what the dialog's own copy says, and it is true rather than a convention.
 */
export async function createApiKeyAction(
  name: string,
  scopes: ApiKeyScope[],
): Promise<ApiKeyActionResult> {
  try {
    const created = await createApiKey(name, scopes);
    refresh();
    return { ok: true, token: created.token };
  } catch (error) {
    // A non-admin gets a 403 from the API. The page already hides these
    // controls for them; this is what stands between a stale client and an
    // error boundary. Compare settings/channels/actions.ts.
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

export async function revokeApiKeyAction(id: string): Promise<RevokeResult> {
  try {
    await revokeApiKey(id);
    refresh();
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}
```

- [ ] **Step 4: Rewrite the dialog with a scope picker**

Replace `apps/web/components/settings/api-key-dialog.tsx`:

```tsx
"use client";

import { useState, useTransition } from "react";
import { Check, Copy, Plus } from "lucide-react";

import { createApiKeyAction } from "@/app/(console)/settings/api-keys/actions";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ApiKeyScope } from "@/lib/types";

/**
 * Presets, not a checkbox grid, as the default path.
 *
 * "Ticket bot" deliberately stops short of messages:write. Creating and
 * triaging tickets is a different blast radius from mailing a customer
 * under the workspace's name, and a preset that quietly bundled the two
 * would undo the reason the scopes are separate at all.
 */
const PRESETS: { id: string; label: string; hint: string; scopes: ApiKeyScope[] }[] = [
  {
    id: "read-only",
    label: "Read-only",
    hint: "Reporting and sync. Cannot change anything.",
    scopes: ["conversations:read", "contacts:read", "labels:read"],
  },
  {
    id: "ticket-bot",
    label: "Ticket bot",
    hint: "Creates and triages tickets. Cannot reply to customers.",
    scopes: [
      "conversations:read",
      "conversations:write",
      "contacts:read",
      "labels:read",
      "labels:write",
    ],
  },
  {
    id: "full",
    label: "Full access",
    hint: "Everything, including replying to customers by email.",
    scopes: [
      "conversations:read",
      "conversations:write",
      "messages:write",
      "contacts:read",
      "labels:read",
      "labels:write",
    ],
  },
];

export function ApiKeyDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [preset, setPreset] = useState(PRESETS[1].id);
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, startTransition] = useTransition();

  function reset() {
    setName("");
    setPreset(PRESETS[1].id);
    setToken(null);
    setError(null);
    setCopied(false);
  }

  function create() {
    setError(null);
    const scopes = PRESETS.find((entry) => entry.id === preset)!.scopes;
    startTransition(async () => {
      const result = await createApiKeyAction(name.trim(), scopes);
      if (result.ok) setToken(result.token);
      else setError(result.message);
    });
  }

  async function copy() {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked; the token is still selectable below.
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Plus />
          Create API key
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{token ? "Copy your key" : "Create API key"}</DialogTitle>
          <DialogDescription>
            {token
              ? "This is the only time it is shown. Store it somewhere safe before closing."
              : "The key is shown once, immediately after it is created."}
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          {token ? (
            <div className="space-y-2">
              <pre className="overflow-x-auto rounded-md border border-ink-200 bg-ink-950 p-3 font-mono text-[12px] text-ink-100">
                <code>{token}</code>
              </pre>
              <button
                type="button"
                onClick={copy}
                className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
              >
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="key-name">Name</Label>
                <Input
                  id="key-name"
                  placeholder="Production ingest"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoFocus
                />
              </div>
              <fieldset className="space-y-1.5">
                <legend className="text-[13px] font-medium text-ink-900">
                  Access
                </legend>
                {PRESETS.map((entry) => (
                  <label
                    key={entry.id}
                    className="flex cursor-pointer items-start gap-2 rounded-md border border-ink-200 p-2.5"
                  >
                    <input
                      type="radio"
                      name="preset"
                      className="mt-0.5"
                      value={entry.id}
                      checked={preset === entry.id}
                      onChange={() => setPreset(entry.id)}
                    />
                    <span className="min-w-0">
                      <span className="block text-[13px] font-medium text-ink-900">
                        {entry.label}
                      </span>
                      <span className="block text-[12px] text-ink-500">
                        {entry.hint}
                      </span>
                    </span>
                  </label>
                ))}
              </fieldset>
              {error && (
                <p role="alert" className="text-[12px] text-danger-700">
                  {error}
                </p>
              )}
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          {token ? (
            <Button variant="primary" onClick={() => setOpen(false)}>
              Done
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={name.trim() === "" || pending}
                onClick={create}
              >
                Create key
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 5: Add the revoke control**

Create `apps/web/components/settings/api-key-actions.tsx`:

```tsx
"use client";

import { useState, useTransition } from "react";
import { Trash2 } from "lucide-react";

import { revokeApiKeyAction } from "@/app/(console)/settings/api-keys/actions";
import { Button } from "@/components/ui/button";
import type { ApiKey } from "@/lib/types";

/** Revoke control on a Settings → API keys row. Revoking is immediate and
 * cannot be undone: the key's row survives so its past actions still have a
 * name, but the secret stops resolving on the next request. */
export function ApiKeyActions({ apiKey }: { apiKey: ApiKey }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function revoke() {
    setError(null);
    startTransition(async () => {
      const result = await revokeApiKeyAction(apiKey.id);
      if (!result.ok) setError(result.message);
    });
  }

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Revoke ${apiKey.name}`}
        disabled={pending}
        onClick={revoke}
      >
        <Trash2 className="size-3.5" />
      </Button>
      {error && (
        <p role="alert" className="text-[11px] text-danger-700">
          {error}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Point the page at the real data**

In `apps/web/app/(console)/settings/api-keys/page.tsx`, change the import of `getApiKeys` from `@/lib/mock/settings` to `@/lib/api/api-keys`, add `import { ApiKeyActions } from "@/components/settings/api-key-actions";`, and replace the row body so it shows the scopes and the revoke control:

```tsx
              {keys.map((key) => (
                <li key={key.id} className="flex items-center gap-3 px-3 py-2.5">
                  <KeyRound className="size-4 shrink-0 text-ink-400" />
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-ink-900">{key.name}</p>
                    <p className="font-mono text-[11px] text-ink-400">
                      {key.prefix}···
                    </p>
                    <p className="text-[11px] text-ink-500">
                      {key.scopes.join(" · ")}
                    </p>
                  </div>
                  <span className="tabular ml-auto shrink-0 text-[12px] text-ink-500">
                    {key.lastUsedAt
                      ? `Last used ${new Date(key.lastUsedAt).toLocaleDateString()}`
                      : "Never used"}
                  </span>
                  <ApiKeyActions apiKey={key} />
                </li>
              ))}
```

Also change the second `SettingSection`'s description to match the real path — it currently says `POST /v1/conversations`, which is now true, so it needs no edit. Leave it.

- [ ] **Step 7: Correct the published sample and drop the mock**

In `apps/web/components/settings/code-sample.tsx`, replace every occurrence of `rd_live_your_key_here` with `rd_your_key_here`. There are four, one per language tab.

In `apps/web/lib/mock/settings.ts`, delete the `apiKeys` array, the `getApiKeys` function, and `ApiKey` from the type import at the top of the file.

- [ ] **Step 8: Verify the web build**

Run: `docker compose exec web pnpm lint && docker compose exec web pnpm build`
Expected: PASS. A `Module not found` or an unused-import error names anything missed in Step 7.

- [ ] **Step 9: Check it by hand**

With the stack up, sign in as an admin, go to **Settings → API keys**, create a key with the "Ticket bot" preset, copy the token, and run the published sample against it:

```bash
curl -X POST http://localhost:8000/v1/conversations \
  -H "Authorization: Bearer <the token>" \
  -H "Content-Type: application/json" \
  -d '{"customer_email":"customer@example.com","message":"Testing the API.","subject":"Hello","external_id":"manual-1"}'
```

Expected: `201` and a conversation body. Run it a second time unchanged: `200`, same `id`. The ticket appears in the console inbox with the `api` channel, and its activity timeline says the key opened it. Then revoke the key in the console and run the curl again: `401`.

- [ ] **Step 10: Commit**

```bash
git add apps/web/lib/api/api-keys.ts \
        apps/web/lib/types.ts \
        apps/web/lib/mock/settings.ts \
        "apps/web/app/(console)/settings/api-keys/" \
        apps/web/components/settings/api-key-dialog.tsx \
        apps/web/components/settings/api-key-actions.tsx \
        apps/web/components/settings/code-sample.tsx
git commit -m "feat(web): manage real API keys from the settings page"
```

---

### Task 12: Pin the contract and document it

The spec's last known risk: v1 becomes a compatibility surface the day it ships, and nothing in the codebase enforces that a future inbox change does not break it. This is the cheapest enforcement.

**Files:**
- Create: `apps/api/tests/test_v1_contract.py`
- Modify: `README.md`
- Test: the new file is the test

**Interfaces:**
- Consumes: everything from Tasks 6–9.

- [ ] **Step 1: Write the contract test**

Create `apps/api/tests/test_v1_contract.py`:

```python
"""The v1 response shapes, pinned.

This is not a behaviour test. It exists so that a change to a v1 response --
a renamed field, a dropped one, a console refactor that leaks through --
fails a test in the same commit that makes it, rather than a third party's
integration some weeks later. Adding a field is compatible and should update
the expected set here; removing or renaming one is a breaking change and
should require a v2.
"""

from relaydesk.models import ApiKeyScope
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_label, make_workspace

CONVERSATION_FIELDS = {
    "id",
    "number",
    "subject",
    "preview",
    "status",
    "priority",
    "channel",
    "customer",
    "assignee_id",
    "label_ids",
    "external_id",
    "metadata",
    "created_at",
    "updated_at",
    "last_message_at",
}
CONTACT_FIELDS = {"id", "email", "name"}
MESSAGE_FIELDS = {
    "id",
    "conversation_id",
    "role",
    "direction",
    "author_name",
    "body",
    "sent_at",
}
LABEL_FIELDS = {"id", "name", "color"}


async def all_scopes_key(db_session, workspace):
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Contract",
        scopes=list(ApiKeyScope),
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_the_conversation_shape_is_exactly_this(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    page = (await client.get("/v1/conversations", headers=headers)).json()

    assert set(page) == {"data", "next_cursor"}
    assert set(page["data"][0]) == CONVERSATION_FIELDS
    assert set(page["data"][0]["customer"]) == CONTACT_FIELDS


async def test_the_message_shape_is_exactly_this(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    messages = (
        await client.get(
            f"/v1/conversations/{conversation.id}/messages", headers=headers
        )
    ).json()

    assert set(messages[0]) == MESSAGE_FIELDS


async def test_the_label_shape_is_exactly_this(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_label(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    labels = (await client.get("/v1/labels", headers=headers)).json()

    assert set(labels[0]) == LABEL_FIELDS


async def test_the_contact_page_shape_is_exactly_this(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    page = (await client.get("/v1/contacts", headers=headers)).json()

    assert set(page) == {"data", "next_cursor"}
    assert set(page["data"][0]) == CONTACT_FIELDS


async def test_every_v1_route_is_under_the_v1_prefix(client) -> None:
    """No public endpoint may hide under /api, and no console route may
    appear under /v1 -- the prefix is the whole signal of which surface a
    route belongs to."""
    from relaydesk.main import app

    v1_paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/v1")
    }
    assert v1_paths == {
        "/v1/conversations",
        "/v1/conversations/{conversation_id}",
        "/v1/conversations/{conversation_id}/messages",
        "/v1/conversations/{conversation_id}/labels/{label_id}",
        "/v1/labels",
        "/v1/contacts",
        "/v1/contacts/{contact_id}",
    }
```

- [ ] **Step 2: Run it**

Run: `docker compose exec api pytest tests/test_v1_contract.py -v`
Expected: PASS, 5 tests. If the last one fails, the printed set names the route that was added or renamed — update the expected set only if the change is deliberate.

- [ ] **Step 3: Document it in the README**

Add a section after **Public ticket submission** and before **Development commands**:

```markdown
## The API

A workspace drives its own inbox from outside the console with an API key.
Create one under **Settings → API keys**; the secret is shown once, at
creation, and only its hash is stored, so rotating means creating a new key
and deleting the old one.

The public API is at `/v1`, separate from `/api`, which is the console's own
surface and changes with the UI. Everything under `/v1` is a stable
contract:

```sh
curl -X POST http://localhost:8000/v1/conversations \
  -H "Authorization: Bearer rd_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"customer_email":"customer@example.com","message":"I need help."}'
```

Conversations, messages, labels and contacts are covered. The full route
list with request and response shapes is at
http://localhost:8000/docs under the `v1:` tags.

### Scopes

A key carries only the scopes it is given, and a write scope does not imply
its read scope:

| Scope | Grants |
|---|---|
| `conversations:read` | List and read conversations and their messages |
| `conversations:write` | Create a conversation; change status, priority, assignee |
| `messages:write` | Send a reply to the customer |
| `contacts:read` | List and read contacts |
| `labels:read` | List labels |
| `labels:write` | Create a label; add and remove labels on a conversation |

**`messages:write` is separate from `conversations:write` on purpose.**
Changing a ticket's status is internal bookkeeping; sending a reply puts
mail in a customer's inbox under your workspace's name. An integration that
triages tickets should not hold the second grant, and the console's "Ticket
bot" preset deliberately does not include it.

### Retries and `external_id`

`POST /v1/conversations` accepts your own `external_id`. It is unique per
workspace, and a repeat returns the conversation it already created with a
`200` instead of a duplicate with a `201` — so an interrupted import is safe
to re-run in full.

### Rate limit

`API_KEY_RATE_LIMIT_PER_MINUTE` (default 120) bounds one key. Every response
carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`; a refusal is a `429`
with `Retry-After`. The window is fixed rather than sliding, so a caller can
see up to twice the limit across a boundary — this bound exists to stop a
runaway integration, not to defeat an adversary, since a key holder is an
authenticated tenant acting on their own data.
```

Also update the **Project status** paragraph: the sentence listing what is not implemented currently reads "Discord, one-click import from another help desk, AI features, analytics, and billing are not yet implemented." Leave it as is — none of those changed — and add to the preceding sentence that a public API with scoped keys is available.

- [ ] **Step 4: Verify everything one last time**

Run:

```bash
docker compose exec api pytest -m "not integration" && \
docker compose exec api ruff check . && \
docker compose exec web pnpm lint && \
docker compose exec web pnpm build
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_v1_contract.py README.md
git commit -m "docs: document the public v1 API and pin its response shapes"
```

---

## Out of scope for this plan

From the spec's section 8, deliberately not built here: webhooks (slice 3), AI triage (slice 4), per-key IP allowlists, generated client SDKs, an MCP server, knowledge base / team / channel / workspace endpoints, key expiry reminders and automatic rotation, and a sandbox workspace with the `live`/`test` key split that would go with it.
