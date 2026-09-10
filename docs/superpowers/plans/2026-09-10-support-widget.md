# Support Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A workspace pastes one `<script>` tag into its website and its customers get a launcher that searches the published knowledge base and, failing that, files a ticket into the existing inbox.

**Architecture:** A new `WidgetKey` credential — public by construction, stored in plaintext — addresses a workspace from an embed. A `/widget/{key}` router resolves the key and delegates to the existing `kb_public` and `tickets` services, adding no domain logic. The panel is an iframe served from Relaydesk's own origin, so there is no CORS; the origin allowlist is enforced as `Content-Security-Policy: frame-ancestors` on the frame response. A ~3 KB loader script draws only the launcher and injects the frame on first open.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16, pytest/httpx; Next.js App Router, React, Tailwind, vitest.

**Spec:** `docs/superpowers/specs/2026-09-10-support-widget-design.md`

## Global Constraints

- **Key format:** `"rdw_" + secrets.token_hex(16)` — 36 characters, column `varchar(64)`.
- **`WidgetKey.key` is stored in plaintext** (spec D1). Its docstring must say so, say why, and note that `ApiKey` does the opposite.
- **Origins are exact** — scheme, host and port. No wildcards, no paths. `https://acme.com` and `https://www.acme.com` are two entries (spec D4/§4).
- **An empty `allowed_origins` refuses embedding**, it does not permit it (spec §4).
- **Unknown, inactive and deleted keys return byte-identical responses** — distinguishing them lets a caller probe which keys exist (spec §5).
- **Never add a fixed first path segment under `/public`** without adding it to `RESERVED_SLUGS` in `services/workspaces.py`. This plan mounts `/widget` as its own prefix, so it is not affected — do not move it under `/public`.
- **The loader must stay under 3 KB** and must draw only the launcher (spec D6). This is a requirement, not an aspiration.
- **Copy is en-GB.** The codebase says "colour", "behaviour", "help centre", "cancelling". Match it.
- **UI colours come from `apps/web/tailwind.config.ts`** — `ink` for every neutral, `accent` citron only for focus rings, marks and active states.
- **Run API tests inside the compose network**: `docker compose exec -T api pytest …`. `.env` points `DATABASE_URL` at host `postgres`, which does not resolve from the host, and `conftest.py` drops and recreates `relaydesk_test` over that connection. Web tests run on the host: `cd apps/web && pnpm vitest run`.
- **Every new schema inherits `CamelModel`** (`relaydesk.schemas.base`), never `BaseModel` — Python stays snake_case, the wire is camelCase, matching the console's TypeScript field for field.
- **`TicketSubmittedOut` is `{received: bool}` and stays that way.** Never return a conversation id or number to an anonymous submitter: its docstring records the decision, and per-workspace numbers are sequential, so returning one leaks a workspace's ticket volume.
- **In `api/widget.py`, declare every fixed-segment route above the `GET /{key}/kb/{path:path}` catch-all.** FastAPI matches in declaration order; anything below it is swallowed as an article path.

## File Structure

| File | Responsibility |
|---|---|
| `apps/api/src/relaydesk/models/widget_key.py` | The `WidgetKey` row and its plaintext-credential docstring |
| `apps/api/migrations/versions/0023_widget_keys.py` | The table |
| `apps/api/src/relaydesk/services/widget_origins.py` | Origin normalisation, matching, and the `frame-ancestors` header. Pure functions, no I/O — the riskiest logic in the slice, isolated so it can be tested exhaustively |
| `apps/api/src/relaydesk/services/widget_keys.py` | Create, list, update, delete, resolve-by-key |
| `apps/api/src/relaydesk/schemas/widget_keys.py` | Console request/response models |
| `apps/api/src/relaydesk/api/widget_keys.py` | Admin-gated console routes |
| `apps/api/src/relaydesk/api/widget.py` | The anonymous `/widget/{key}` router |
| `apps/web/app/(widget)/widget/frame/page.tsx` | The panel, served in the iframe |
| `apps/web/components/widget/*` | Panel states |
| `apps/web/public/widget.js` | The loader |
| `apps/web/app/(console)/settings/widget/page.tsx` | Console management screen |
| `apps/api/src/relaydesk/models/widget_session.py` | The deflection counter row |
| `apps/api/src/relaydesk/services/widget_sessions.py` | Raising a session's flags idempotently |

---

### Task 1: The `WidgetKey` model and migration

**Files:**
- Create: `apps/api/src/relaydesk/models/widget_key.py`
- Create: `apps/api/migrations/versions/0023_widget_keys.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Test: `apps/api/tests/test_widget_key_model.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `WidgetKey` with columns `id, workspace_id, name, key, allowed_origins, settings, active, created_by_user_id, last_seen_at, created_at, updated_at`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_widget_key_model.py
import pytest
import sqlalchemy as sa

from relaydesk.models.widget_key import WidgetKey
from tests.factories import make_workspace


async def test_key_is_stored_verbatim(db_session):
    """The credential is public by construction; a digest could never be re-shown."""
    workspace = await make_workspace(db_session)
    db_session.add(
        WidgetKey(workspace_id=workspace.id, name="Marketing site", key="rdw_abc123")
    )
    await db_session.flush()

    stored = await db_session.scalar(sa.select(WidgetKey.key))
    assert stored == "rdw_abc123"


async def test_defaults_refuse_embedding(db_session):
    """An unconfigured key allows nobody -- empty means refuse, not permit."""
    workspace = await make_workspace(db_session)
    key = WidgetKey(workspace_id=workspace.id, name="Site", key="rdw_def456")
    db_session.add(key)
    await db_session.flush()

    assert key.allowed_origins == []
    assert key.settings == {}
    assert key.active is True
    assert key.last_seen_at is None


async def test_key_is_unique_across_workspaces(db_session):
    one = await make_workspace(db_session, slug="one")
    two = await make_workspace(db_session, slug="two")
    db_session.add(WidgetKey(workspace_id=one.id, name="A", key="rdw_same"))
    await db_session.flush()
    db_session.add(WidgetKey(workspace_id=two.id, name="B", key="rdw_same"))

    with pytest.raises(sa.exc.IntegrityError):
        await db_session.flush()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_widget_key_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.models.widget_key'`

- [ ] **Step 3: Write the model**

```python
# apps/api/src/relaydesk/models/widget_key.py
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class WidgetKey(UUIDMixin, TimestampMixin, Base):
    """A workspace's embed credential, published in other people's page source.

    ``key`` is stored verbatim, which departs from every bearer credential in
    this schema: ``ApiKey`` keeps only a SHA-256 digest and shows its secret
    exactly once. Neither is possible here. This value is printed in the HTML
    of every site that embeds the widget, so it is not secret at any point in
    its life, and an admin has to be able to read it back forever to re-paste
    the snippet. A digest cannot serve a credential that is public by
    construction. Spec D1 records why a ``public`` scope on ``ApiKey`` was
    rejected rather than this table added: a bearer token and an embed key
    sharing one table is how an ``rd_live_`` secret eventually ends up inside
    a ``<script>`` tag.

    Holding this key grants nothing anonymity did not already grant. Every
    endpoint it reaches is public: the knowledge base is a published help
    site and ticket submission is already an open endpoint. That is what
    makes ``allowed_origins`` -- enforced with ``frame-ancestors``, and so
    enforced by browsers and by nothing else -- an acceptable control. Spec
    D2 states the consequence: if a later slice gives the widget anything a
    stranger should not have, this model is wrong for it and needs verified
    identity, not more origins.

    ``allowed_origins`` holds exact origins, scheme and host and port, with
    no wildcards. An empty list refuses embedding rather than permitting it,
    so a key that has been created but not configured is inert.

    There is no ``revoked_at``. Unlike a bearer token a widget key carries no
    history worth auditing once it is gone; deleting the row is the
    revocation and the embed then fails closed.
    """

    __tablename__ = "widget_keys"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Read and written as a unit, never queried across rows.
    allowed_origins: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Written at most once a minute per key, so "is this still installed?"
    # can be answered without a write per page view.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 4: Register the model**

In `apps/api/src/relaydesk/models/__init__.py`, add the import after the `webhook` import and `"WidgetKey"` to `__all__` in alphabetical position (after `"Webhook"`, before `"Workspace"`):

```python
from relaydesk.models.widget_key import WidgetKey
```

- [ ] **Step 5: Write the migration**

```python
# apps/api/migrations/versions/0023_widget_keys.py
"""widget keys

Adds ``widget_keys``, the credential behind the embeddable support widget.

``key`` is stored in plaintext, which no other credential in this schema
does. It is printed in the page source of every site that embeds the widget,
so it is not secret at any point in its life, and an admin must be able to
read it back to re-paste the snippet. See the model docstring, which records
what that costs and why a scope on ``api_keys`` was rejected instead.

``allowed_origins`` is JSONB holding exact origins; an empty list refuses
embedding rather than permitting it. ``settings`` is JSONB because none of it
is queried and all of it is presentational.

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-10 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "widget_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "allowed_origins",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(
        "ix_widget_keys_workspace_id", "widget_keys", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_widget_keys_workspace_id", table_name="widget_keys")
    op.drop_table("widget_keys")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_widget_key_model.py -v`
Expected: PASS (3 tests). The suite runs Alembic to build the test database, so a broken migration fails here.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/models/widget_key.py apps/api/src/relaydesk/models/__init__.py apps/api/migrations/versions/0023_widget_keys.py apps/api/tests/test_widget_key_model.py
git commit -m "feat(widget): a credential that is public by construction"
```

---

### Task 2: Origin normalisation and matching

Isolated as pure functions because this is where origin checking quietly breaks, and because it must be testable without a database.

**Files:**
- Create: `apps/api/src/relaydesk/services/widget_origins.py`
- Test: `apps/api/tests/test_widget_origins.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `normalise(value: str) -> str | None`, `allowed(origins: list[str], candidate: str | None) -> bool`, `frame_ancestors(origins: list[str]) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_widget_origins.py
import pytest

from relaydesk.services import widget_origins as origins


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://acme.com", "https://acme.com"),
        # A trailing slash is what an admin pastes out of a browser bar.
        ("https://acme.com/", "https://acme.com"),
        ("HTTPS://ACME.COM", "https://acme.com"),
        # Default ports are implicit in an Origin header, so storing them
        # explicitly would never match what the browser sends.
        ("https://acme.com:443", "https://acme.com"),
        ("http://acme.com:80", "http://acme.com"),
        ("http://localhost:3000", "http://localhost:3000"),
        ("https://acme.com:8443", "https://acme.com:8443"),
    ],
)
def test_normalise_accepts(raw, expected):
    assert origins.normalise(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "acme.com",                    # no scheme
        "ftp://acme.com",              # not http(s)
        "https://*.acme.com",          # wildcards are refused, spec section 4
        "https://acme.com/help",       # a path is not an origin
        "https://acme.com?x=1",
        "https://acme.com#a",
        "null",                        # a sandboxed iframe's Origin
        "https://",
    ],
)
def test_normalise_rejects(raw):
    assert origins.normalise(raw) is None


def test_empty_allowlist_refuses():
    """Unconfigured means refuse. Permitting here would open every new key."""
    assert origins.allowed([], "https://acme.com") is False


def test_allowed_matches_exactly():
    stored = ["https://acme.com", "https://www.acme.com"]
    assert origins.allowed(stored, "https://acme.com") is True
    assert origins.allowed(stored, "https://acme.com:443") is True
    assert origins.allowed(stored, "https://ACME.com/") is True
    # A subdomain is not the same origin, and neither is another scheme.
    assert origins.allowed(stored, "https://evil.acme.com") is False
    assert origins.allowed(stored, "http://acme.com") is False
    assert origins.allowed(stored, "https://acme.com.evil.com") is False


def test_allowed_refuses_absent_and_opaque_origins():
    stored = ["https://acme.com"]
    assert origins.allowed(stored, None) is False
    assert origins.allowed(stored, "null") is False


def test_frame_ancestors_none_when_unconfigured():
    assert origins.frame_ancestors([]) == "frame-ancestors 'none'"


def test_frame_ancestors_lists_origins():
    header = origins.frame_ancestors(["https://acme.com", "https://www.acme.com"])
    assert header == "frame-ancestors https://acme.com https://www.acme.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_widget_origins.py -v`
Expected: FAIL — `ImportError: cannot import name 'widget_origins'`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/src/relaydesk/services/widget_origins.py
"""Which sites may embed a widget, and how that is enforced.

The panel is an iframe served from Relaydesk's own origin, so the embedding
page never makes a cross-origin request and CORS is not involved at all. What
is being controlled is who may *frame* us, which is
``Content-Security-Policy: frame-ancestors``.

Both that and CORS are enforced by the browser and by nothing else -- a
script that is not a browser ignores both. This is abuse control, not
authorization, and it is acceptable only because every endpoint a widget key
reaches is already public (spec D2). Nothing here should ever be relied on to
keep a stranger away from something.

Pure functions: no session, no request, no settings. Everything that decides
whether a frame renders lives here so it can be tested exhaustively.
"""

from urllib.parse import urlsplit

_DEFAULT_PORTS = {"https": 443, "http": 80}


def normalise(value: str) -> str | None:
    """``value`` reduced to ``scheme://host[:port]``, or ``None`` if it is not an origin.

    Rejects wildcards outright. A pattern like ``*.acme.com`` needs a matcher
    rather than a comparison, and a matcher is the thing that goes subtly
    wrong -- ``*.com`` being the memorable version. Spec section 4 keeps v1
    to exact origins for that reason.
    """
    candidate = value.strip().rstrip("/")
    if not candidate or "*" in candidate:
        return None

    parts = urlsplit(candidate)
    if parts.scheme not in _DEFAULT_PORTS:
        return None
    if parts.path or parts.query or parts.fragment:
        return None
    if not parts.hostname:
        return None

    host = parts.hostname.lower()
    try:
        port = parts.port
    except ValueError:
        # A non-numeric port; urlsplit only raises when it is asked.
        return None

    if port is None or port == _DEFAULT_PORTS[parts.scheme]:
        return f"{parts.scheme}://{host}"
    return f"{parts.scheme}://{host}:{port}"


def allowed(origins: list[str], candidate: str | None) -> bool:
    """Whether ``candidate`` is one of ``origins``.

    An empty ``origins`` refuses. A key that has been created but not
    configured is inert, which is the safe direction to fail: the opposite
    would leave every freshly minted key embeddable anywhere until someone
    remembered to restrict it.
    """
    if not origins or candidate is None:
        return False
    normalised = normalise(candidate)
    if normalised is None:
        return False
    return normalised in {stored for stored in map(normalise, origins) if stored}


def frame_ancestors(origins: list[str]) -> str:
    """The CSP header value for a frame response."""
    permitted = [stored for stored in map(normalise, origins) if stored]
    if not permitted:
        return "frame-ancestors 'none'"
    return "frame-ancestors " + " ".join(permitted)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_widget_origins.py -v`
Expected: PASS (all parametrised cases)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/widget_origins.py apps/api/tests/test_widget_origins.py
git commit -m "feat(widget): exact origins, and an empty list that refuses"
```

---

### Task 3: The `widget_keys` service

**Files:**
- Create: `apps/api/src/relaydesk/services/widget_keys.py`
- Test: `apps/api/tests/test_widget_keys_service.py`

**Interfaces:**
- Consumes: `WidgetKey` (Task 1), `widget_origins.normalise` (Task 2).
- Produces: `create(session, workspace_id, name, *, allowed_origins=None, created_by_user_id=None) -> WidgetKey`, `list_keys(session, workspace_id) -> list[WidgetKey]`, `get(session, workspace_id, key_id) -> WidgetKey`, `update(session, workspace_id, key_id, **fields) -> WidgetKey`, `delete(session, workspace_id, key_id) -> None`, `resolve(session, key) -> WidgetKey` (raises `NotFound`), `touch(session, widget_key) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_widget_keys_service.py
from datetime import UTC, datetime, timedelta

import pytest

from relaydesk.errors import Invalid, NotFound
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_create_mints_a_prefixed_key(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Marketing site")

    assert created.key.startswith("rdw_")
    assert len(created.key) == 36
    assert created.allowed_origins == []


async def test_create_normalises_origins(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(
        session,
        workspace.id,
        "Site",
        allowed_origins=["HTTPS://ACME.COM/", "https://acme.com:443"],
    )

    # Both inputs are the same origin; it is stored once, normalised.
    assert created.allowed_origins == ["https://acme.com"]


async def test_create_refuses_an_unparseable_origin(db_session):
    workspace = await make_workspace(db_session)
    with pytest.raises(Invalid):
        await widget_keys.create(
            session, workspace.id, "Site", allowed_origins=["*.acme.com"]
        )


async def test_resolve_finds_an_active_key(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")

    found = await widget_keys.resolve(db_session, created.key)
    assert found.id == created.id


async def test_resolve_refuses_unknown_and_inactive_alike(db_session):
    """Same exception either way -- a caller must not learn which keys exist."""
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")
    await widget_keys.update(db_session, workspace.id, created.id, active=False)

    with pytest.raises(NotFound):
        await widget_keys.resolve(db_session, created.key)
    with pytest.raises(NotFound):
        await widget_keys.resolve(db_session, "rdw_" + "0" * 32)


async def test_get_is_scoped_to_its_workspace(db_session):
    one = await make_workspace(db_session, slug="one")
    two = await make_workspace(db_session, slug="two")
    created = await widget_keys.create(db_session, one.id, "Site")

    with pytest.raises(NotFound):
        await widget_keys.get(db_session, two.id, created.id)


async def test_touch_writes_at_most_once_a_minute(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")

    await widget_keys.touch(db_session, created)
    first = created.last_seen_at
    assert first is not None

    await widget_keys.touch(db_session, created)
    assert created.last_seen_at == first

    created.last_seen_at = datetime.now(UTC) - timedelta(minutes=2)
    await widget_keys.touch(db_session, created)
    assert created.last_seen_at != first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_widget_keys_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'widget_keys'`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/src/relaydesk/services/widget_keys.py
"""Minting and resolving the credential a widget embed carries."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid, NotFound
from relaydesk.models.widget_key import WidgetKey
from relaydesk.services import widget_origins

# Long enough that guessing is pointless, short enough to paste. The value is
# public, so this is about enumeration, not secrecy.
_KEY_BYTES = 16
_TOUCH_EVERY = timedelta(minutes=1)


def _new_key() -> str:
    return "rdw_" + secrets.token_hex(_KEY_BYTES)


def _clean_origins(raw: list[str] | None) -> list[str]:
    """Normalise, de-duplicate, and refuse anything that is not an origin.

    Order is preserved so the console shows origins as the admin entered
    them rather than re-sorted underneath.
    """
    cleaned: list[str] = []
    for entry in raw or []:
        normalised = widget_origins.normalise(entry)
        if normalised is None:
            raise Invalid(f"{entry!r} is not a valid site address.")
        if normalised not in cleaned:
            cleaned.append(normalised)
    return cleaned


async def create(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
    *,
    allowed_origins: list[str] | None = None,
    settings: dict | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> WidgetKey:
    label = name.strip()
    if not label:
        raise Invalid("Give this embed a name.")

    key = WidgetKey(
        workspace_id=workspace_id,
        name=label,
        key=_new_key(),
        allowed_origins=_clean_origins(allowed_origins),
        settings=settings or {},
        created_by_user_id=created_by_user_id,
    )
    db_session.add(key)
    await db_session.flush()
    return key


async def list_keys(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[WidgetKey]:
    result = await db_session.scalars(
        sa.select(WidgetKey)
        .where(WidgetKey.workspace_id == workspace_id)
        .order_by(WidgetKey.created_at.desc())
    )
    return list(result)


async def get(
    session: AsyncSession, workspace_id: uuid.UUID, key_id: uuid.UUID
) -> WidgetKey:
    key = await db_session.scalar(
        sa.select(WidgetKey).where(
            WidgetKey.id == key_id, WidgetKey.workspace_id == workspace_id
        )
    )
    if key is None:
        raise NotFound("No such embed.")
    return key


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    key_id: uuid.UUID,
    *,
    name: str | None = None,
    allowed_origins: list[str] | None = None,
    settings: dict | None = None,
    active: bool | None = None,
) -> WidgetKey:
    key = await get(session, workspace_id, key_id)
    if name is not None:
        label = name.strip()
        if not label:
            raise Invalid("Give this embed a name.")
        key.name = label
    if allowed_origins is not None:
        key.allowed_origins = _clean_origins(allowed_origins)
    if settings is not None:
        key.settings = settings
    if active is not None:
        key.active = active
    await db_session.flush()
    return key


async def delete(
    session: AsyncSession, workspace_id: uuid.UUID, key_id: uuid.UUID
) -> None:
    """Deleting the row *is* the revocation; there is no ``revoked_at``."""
    key = await get(session, workspace_id, key_id)
    await db_session.delete(key)
    await db_session.flush()


async def resolve(session: AsyncSession, key: str) -> WidgetKey:
    """The key's workspace, or ``NotFound``.

    Unknown, inactive and deleted keys all raise the same exception with the
    same message. Telling them apart would let a caller walk the key space
    and learn which embeds exist.
    """
    found = await db_session.scalar(
        sa.select(WidgetKey).where(WidgetKey.key == key, WidgetKey.active.is_(True))
    )
    if found is None:
        raise NotFound("No such embed.")
    return found


async def touch(session: AsyncSession, widget_key: WidgetKey) -> None:
    """Record that the embed is still installed, at most once a minute.

    Without the interval this is a write on every page view of every site
    that embeds the widget, to answer a question nobody asks more than once
    a day.
    """
    now = datetime.now(UTC)
    seen = widget_key.last_seen_at
    if seen is not None and now - seen < _TOUCH_EVERY:
        return
    widget_key.last_seen_at = now
    await db_session.flush()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_widget_keys_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/widget_keys.py apps/api/tests/test_widget_keys_service.py
git commit -m "feat(widget): mint, resolve and revoke an embed key"
```

---

### Task 4: Console routes for managing embeds

**Files:**
- Create: `apps/api/src/relaydesk/schemas/widget_keys.py`
- Create: `apps/api/src/relaydesk/api/widget_keys.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Test: `apps/api/tests/test_widget_keys_api.py`

**Interfaces:**
- Consumes: `widget_keys` service (Task 3), `Scope`/`DbSession` from `relaydesk.api.deps`.
- Produces: `GET/POST /widget-keys`, `PATCH/DELETE /widget-keys/{key_id}`, and `WidgetKeyOut` carrying `id, name, key, allowed_origins, settings, active, last_seen_at, created_at`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_widget_keys_api.py
from relaydesk.models import Role
from tests.factories import make_member, make_workspace, sign_in


# The house pattern -- these mirror tests/test_api_keys_api.py.
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


async def test_admin_creates_and_lists(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    created = await client.post(
        "/api/widget-keys",
        json={"name": "Marketing site", "allowedOrigins": ["https://acme.com/"]},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["key"].startswith("rdw_")
    assert body["allowedOrigins"] == ["https://acme.com"]

    listed = await client.get("/api/widget-keys", headers=headers)
    assert listed.status_code == 200
    # The key comes back in full every time -- it is public, and the admin
    # needs it to re-paste the snippet. Contrast ApiKey, whose secret is
    # shown once and never again.
    assert listed.json()[0]["key"] == body["key"]


async def test_agent_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await agent_headers(client, db_session, workspace)

    response = await client.post(
        "/api/widget-keys", json={"name": "Site"}, headers=headers
    )
    assert response.status_code == 403, response.text


async def test_bad_origin_is_rejected(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.post(
        "/api/widget-keys",
        json={"name": "Site", "allowedOrigins": ["*.acme.com"]},
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_delete_removes_the_embed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    created = await client.post(
        "/api/widget-keys", json={"name": "Site"}, headers=headers
    )
    key_id = created.json()["id"]

    deleted = await client.delete(f"/api/widget-keys/{key_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    remaining = await client.get("/api/widget-keys", headers=headers)
    assert remaining.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_widget_keys_api.py -v`
Expected: FAIL — 404 on `/widget-keys`, the router does not exist

- [ ] **Step 3: Write the schemas**

```python
# apps/api/src/relaydesk/schemas/widget_keys.py
import uuid
from datetime import datetime

from pydantic import Field

from relaydesk.schemas.base import CamelModel


class WidgetKeyCreate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    allowed_origins: list[str] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)


class WidgetKeyUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    allowed_origins: list[str] | None = None
    settings: dict | None = None
    active: bool | None = None


class WidgetKeyOut(CamelModel):
    id: uuid.UUID
    name: str
    # Returned in full on every read, unlike ApiKey's one-time secret: this
    # value is published in page source and the admin needs it to re-paste.
    key: str
    allowed_origins: list[str]
    settings: dict
    active: bool
    last_seen_at: datetime | None
    created_at: datetime
```

- [ ] **Step 4: Write the routes**

```python
# apps/api/src/relaydesk/api/widget_keys.py
"""Console management of widget embeds. Admin-gated, like every settings surface."""

import uuid

from fastapi import APIRouter, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models.widget_key import WidgetKey
from relaydesk.schemas.widget_keys import (
    WidgetKeyCreate,
    WidgetKeyOut,
    WidgetKeyUpdate,
)
from relaydesk.services import widget_keys

router = APIRouter()


def _out(key: WidgetKey) -> WidgetKeyOut:
    return WidgetKeyOut(
        id=key.id,
        name=key.name,
        key=key.key,
        allowed_origins=key.allowed_origins,
        settings=key.settings,
        active=key.active,
        last_seen_at=key.last_seen_at,
        created_at=key.created_at,
    )


@router.get("", response_model=list[WidgetKeyOut])
async def list_route(scope: Scope, session: DbSession) -> list[WidgetKeyOut]:
    scope.require_admin()
    rows = await widget_keys.list_keys(session, scope.workspace.id)
    return [_out(row) for row in rows]


@router.post("", response_model=WidgetKeyOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: WidgetKeyCreate, scope: Scope, session: DbSession
) -> WidgetKeyOut:
    scope.require_admin()
    created = await widget_keys.create(
        session,
        scope.workspace.id,
        body.name,
        allowed_origins=body.allowed_origins,
        settings=body.settings,
        created_by_user_id=scope.user.id,
    )
    return _out(created)


@router.patch("/{key_id}", response_model=WidgetKeyOut)
async def update_route(
    key_id: uuid.UUID, body: WidgetKeyUpdate, scope: Scope, session: DbSession
) -> WidgetKeyOut:
    scope.require_admin()
    updated = await widget_keys.update(
        session,
        scope.workspace.id,
        key_id,
        name=body.name,
        allowed_origins=body.allowed_origins,
        settings=body.settings,
        active=body.active,
    )
    return _out(updated)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(key_id: uuid.UUID, scope: Scope, session: DbSession) -> None:
    scope.require_admin()
    await widget_keys.delete(session, scope.workspace.id, key_id)
```

- [ ] **Step 5: Register the router**

In `apps/api/src/relaydesk/api/router.py`, add the import alongside the others and mount it after `webhooks_router`:

```python
from relaydesk.api.widget_keys import router as widget_keys_router

api_router.include_router(widget_keys_router, prefix="/widget-keys", tags=["widget"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_widget_keys_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/schemas/widget_keys.py apps/api/src/relaydesk/api/widget_keys.py apps/api/src/relaydesk/api/router.py apps/api/tests/test_widget_keys_api.py
git commit -m "feat(widget): manage embeds from the console"
```

---

### Task 5: The anonymous `/widget/{key}` router

**Files:**
- Create: `apps/api/src/relaydesk/api/widget.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Test: `apps/api/tests/test_widget_api.py`

**Interfaces:**
- Consumes: `widget_keys.resolve`/`touch` (Task 3), `widget_origins.frame_ancestors` (Task 2), and the existing `kb_public` service.
- Produces: `GET /widget/{key}` returning `WidgetBootstrapOut(workspace_name, monogram, settings, article_count)`, plus `GET /widget/{key}/kb`, `/kb/search/index`, `/kb/search`, `/kb/{path}`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_widget_api.py
import pytest

from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_bootstrap_reports_an_empty_knowledge_base(client, db_session):
    """The day-one state: the frame must know before its first paint."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.get(f"/api/widget/{key.key}")
    assert response.status_code == 200
    body = response.json()
    assert body["article_count"] == 0
    assert body["workspace_name"] == workspace.name


async def test_unknown_and_inactive_keys_answer_identically(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await widget_keys.update(db_session, workspace.id, key.id, active=False)
    await db_session.commit()

    inactive = await client.get(f"/api/widget/{key.key}")
    unknown = await client.get("/api/widget/rdw_" + "0" * 32)

    assert inactive.status_code == unknown.status_code == 404
    assert inactive.json() == unknown.json()


async def test_bootstrap_records_that_the_embed_is_installed(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    await client.get(f"/api/widget/{key.key}")
    await db_session.refresh(key)
    assert key.last_seen_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_widget_api.py -v`
Expected: FAIL — 404 from the app itself; the router does not exist

- [ ] **Step 3: Write the router**

```python
# apps/api/src/relaydesk/api/widget.py
"""Anonymous routes the embedded widget calls, addressed by widget key.

A second front door onto `relaydesk.api.public`, not new domain logic. The
KB reads below resolve the key to a workspace and then call public.py's own
route functions by slug, so the mapping from domain objects to schemas has
exactly one implementation. The difference between the two doors is only
how the workspace is named -- by key rather than by slug, so an embed
survives a workspace being renamed (spec D3).

Mounted at its own `/widget` prefix rather than under `/public`, so it adds
no fixed first path segment there and needs no entry in `RESERVED_SLUGS`.

Route order is load-bearing: FastAPI matches in declaration order, so every
fixed segment must be declared above the `{path:path}` catch-all or it is
swallowed as an article path.
"""

from fastapi import APIRouter

from relaydesk.api import public
from relaydesk.api.deps import DbSession
from relaydesk.schemas.kb import (
    PublicArticleSummary,
    PublicCollectionOut,
    PublicNodeOut,
    PublicSearchEntryOut,
)
from relaydesk.schemas.widget import WidgetBootstrapOut
from relaydesk.services import kb_public, widget_keys

router = APIRouter()


@router.get("/{key}", response_model=WidgetBootstrapOut)
async def bootstrap(key: str, session: DbSession) -> WidgetBootstrapOut:
    """Everything the frame needs for its first paint, in one call.

    ``article_count`` is here rather than behind a second request because
    the empty-knowledge-base rendering (spec D7) is a different screen, not
    a different state of the same one -- fetching it later would show a
    search field for one frame and then take it away.

    It is the length of ``searchable()`` rather than its own COUNT query so
    that "the knowledge base is empty" means exactly "search would find
    nothing", by construction rather than by two queries agreeing.
    """
    widget_key = await widget_keys.resolve(session, key)
    await widget_keys.touch(session, widget_key)
    workspace = widget_key.workspace
    entries = await kb_public.searchable(session, workspace.id)

    return WidgetBootstrapOut(
        workspace_name=workspace.name,
        monogram=workspace.monogram,
        settings=widget_key.settings,
        article_count=len(entries),
    )


@router.get("/{key}/kb", response_model=list[PublicCollectionOut])
async def kb_index(key: str, session: DbSession) -> list[PublicCollectionOut]:
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_index(slug=widget_key.workspace.slug, session=session)


@router.get("/{key}/kb/search/index", response_model=list[PublicSearchEntryOut])
async def kb_search_index(key: str, session: DbSession) -> list[PublicSearchEntryOut]:
    """The whole searchable set, fetched once and searched in the browser.

    This is what removes search from the rate-limit surface entirely (spec
    D8). It discloses nothing new -- every entry is a published,
    externally-scoped article already served in full on the public help site.
    """
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_search_index(
        slug=widget_key.workspace.slug, session=session
    )


@router.get("/{key}/kb/search", response_model=list[PublicArticleSummary])
async def kb_search(
    key: str, session: DbSession, q: str = ""
) -> list[PublicArticleSummary]:
    """Server-side search, for indexes too large to ship whole (spec D8)."""
    widget_key = await widget_keys.resolve(session, key)
    return await public.search_kb(slug=widget_key.workspace.slug, session=session, q=q)


# Declared last: `{path:path}` matches anything, including the fixed
# segments above, so moving it up silently 404s them as missing articles.
@router.get("/{key}/kb/{path:path}", response_model=PublicNodeOut)
async def kb_node(key: str, path: str, session: DbSession) -> PublicNodeOut:
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_path(
        slug=widget_key.workspace.slug, path=path, session=session
    )
```

`bootstrap` reads `widget_key.workspace`, so `WidgetKey` needs the relationship.
Add to `apps/api/src/relaydesk/models/widget_key.py`, after the columns:

```python
    workspace: Mapped["Workspace"] = relationship(lazy="selectin")
```

importing `relationship` alongside `Mapped`/`mapped_column`, and `Workspace`
under `TYPE_CHECKING`.

- [ ] **Step 4: Add the bootstrap schema**

```python
# apps/api/src/relaydesk/schemas/widget.py
from relaydesk.schemas.base import CamelModel


class WidgetBootstrapOut(CamelModel):
    workspace_name: str
    monogram: str
    settings: dict
    # Drives the empty-knowledge-base screen (spec D7).
    article_count: int
```

Nothing is added to `kb_public`: `searchable()` already returns exactly the
set the widget would search, so its length is the count, and a second query
that could disagree with it is never written.

- [ ] **Step 5: Register the router**

In `apps/api/src/relaydesk/api/router.py`, after the `public_router` mount:

```python
from relaydesk.api.widget import router as widget_router

# Anonymous, addressed by widget key rather than slug. Its own prefix, so it
# adds no fixed first segment under /public and no RESERVED_SLUGS entry.
api_router.include_router(widget_router, prefix="/widget", tags=["widget"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_widget_api.py tests/test_kb_articles.py -v`
Expected: PASS — including the existing KB tests, which must not regress

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/api/widget.py apps/api/src/relaydesk/schemas/widget.py apps/api/src/relaydesk/services/kb_public.py apps/api/src/relaydesk/models/widget_key.py apps/api/src/relaydesk/api/router.py apps/api/tests/test_widget_api.py
git commit -m "feat(widget): read the knowledge base through an embed key"
```

---

### Task 6: Submission through the widget, and a per-key cap

**Files:**
- Modify: `apps/api/src/relaydesk/api/widget.py`
- Modify: `apps/api/src/relaydesk/config.py` (add `widget_key_hourly_cap`)
- Modify: `.env.example`
- Test: `apps/api/tests/test_widget_tickets.py`

**Interfaces:**
- Consumes: `tickets.validate`, `ratelimit.check(session, bucket, key, *, limit, window)`.
- Produces: `POST /widget/{key}/tickets` returning `TicketSubmittedOut`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_widget_tickets.py
import pytest
import sqlalchemy as sa

from relaydesk.models.conversation import Conversation
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_submission_creates_a_conversation(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={"email": "wren@lantern.co", "subject": "Refund", "message": "Hello"},
    )
    assert response.status_code == 201

    count = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Conversation)
        .where(Conversation.workspace_id == workspace.id)
    )
    assert count == 1


async def test_per_key_cap_refuses_beyond_its_budget(client, db_session, monkeypatch):
    """One abused embed exhausts its own budget, not the workspace's."""
    from relaydesk.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("WIDGET_KEY_HOURLY_CAP", "2")

    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    for index in range(2):
        accepted = await client.post(
            f"/api/widget/{key.key}/tickets",
            data={"email": f"a{index}@lantern.co", "message": "Hello"},
        )
        assert accepted.status_code == 201

    refused = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={"email": "c@lantern.co", "message": "Hello"},
    )
    assert refused.status_code == 429
    get_settings.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_widget_tickets.py -v`
Expected: FAIL — 404, the route does not exist

- [ ] **Step 3: Add the setting**

In `apps/api/src/relaydesk/config.py`, beside `ticket_ip_hourly_cap`:

```python
    widget_key_hourly_cap: int = 60
```

In `.env.example`, beside `TICKET_IP_HOURLY_CAP`:

```
# Submissions one embed may accept per hour, on top of the per-IP cap. An
# abused embed exhausts this before it touches the workspace's own budget.
WIDGET_KEY_HOURLY_CAP=60
```

- [ ] **Step 4: Add the route**

Append to `apps/api/src/relaydesk/api/widget.py`. The control ordering is the
same as `public.submit_ticket`'s and is deliberate: validation first, so that
a caller cannot read a control's identity off the difference between a 422
and a 429.

```python
from datetime import timedelta
from typing import Annotated

from fastapi import File, Form, Request, UploadFile
from pydantic import EmailStr

from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid, TooManyRequests
from relaydesk.schemas.kb import TicketSubmittedOut
from relaydesk.services import client_ip, ratelimit, tickets


@router.post("/{key}/tickets", response_model=TicketSubmittedOut, status_code=201)
async def submit(
    key: str,
    session: DbSession,
    request: Request,
    email: Annotated[EmailStr, Form()],
    message: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
    subject: Annotated[str, Form()] = "",
    company: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> TicketSubmittedOut:
    widget_key = await widget_keys.resolve(db_session, key)

    uploads = files or []
    if len(uploads) > get_settings().ticket_attachment_max_count:
        raise Invalid("Too many attachments.")

    parsed = [
        ParsedAttachment(
            filename=upload.filename or "attachment",
            content_type=upload.content_type or "application/octet-stream",
            content=await upload.read(),
            inline=False,
            content_id=None,
        )
        for upload in uploads
    ]

    tickets.validate(message, parsed)

    within_ip = await ratelimit.check(
        session,
        "tickets",
        client_ip.resolve(request),
        limit=get_settings().ticket_ip_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within_ip:
        raise TooManyRequests("We could not accept that just now.")

    # The per-embed cap, on the same exception and message as the one above:
    # a caller who can tell which fired learns how to route around it.
    within_key = await ratelimit.check(
        session,
        "widget",
        str(widget_key.id),
        limit=get_settings().widget_key_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within_key:
        raise TooManyRequests("We could not accept that just now.")

    # The per-email cap, on the same exception and message again.
    if await tickets.over_email_cap(session, widget_key.workspace_id, str(email)):
        raise TooManyRequests("We could not accept that just now.")

    # The honeypot, last -- after every control above has run identically
    # for this caller and a real one. `company` is hidden by the form's
    # stylesheet, so anything in it came from something filling fields
    # blindly. Answered with the same 201 a real submission gets: the only
    # difference is whether rows get written, which is the one thing the
    # caller cannot observe.
    if company.strip():
        return TicketSubmittedOut(received=True)

    await tickets.submit(
        session,
        widget_key.workspace_id,
        email=str(email),
        name=name,
        subject=subject,
        message=message,
        attachments=parsed,
    )
    # Required, and easy to miss: `get_session` has no commit-on-exit and
    # there is no commit-on-success middleware, so an uncommitted flush is
    # rolled back by `AsyncSession.close()` when the request ends and the
    # ticket silently never exists. `public.py:332` does exactly this, for
    # exactly this reason.
    await session.commit()
    return TicketSubmittedOut(received=True)
```

`tickets.submit` already exists at `services/tickets.py:82` with exactly this
signature and returns a `Conversation`. It re-runs `validate` and
`over_email_cap` itself, which is why calling them here as well is correct
rather than redundant — the router's copies exist to fix the *ordering* a
caller can observe, and the service's exist so a future caller cannot skip
them.

**Do not return the conversation's number.** `TicketSubmittedOut` is
`{received: bool}` and its docstring records why: *"Deliberately says nothing
but 'received'. No id, no number: the submitter is anonymous and must not be
handed a handle to the inbox."* Per-workspace numbers are sequential, so
returning one would also tell any anonymous submitter how many tickets that
workspace has ever received. The honeypot branch and the real branch return
the identical object, or the difference is observable.

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_widget_tickets.py tests/test_public_tickets.py -v`
Expected: PASS — including the existing public submission tests

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/relaydesk/api/widget.py apps/api/src/relaydesk/services/tickets.py apps/api/src/relaydesk/config.py .env.example apps/api/tests/test_widget_tickets.py
git commit -m "feat(widget): file a ticket from an embed, on its own budget"
```

---

### Task 7: Repair the client-IP chain (spec D9)

Do this before the frame exists. Once the widget is live, the defect below
throttles every visitor on every embedding site into one bucket.

**Files:**
- Modify: `apps/web/middleware.ts:52-63`
- Modify: `apps/web/middleware.test.ts`
- Modify: `docker-compose.yml` (drop the web port mapping)

**Interfaces:**
- Consumes: nothing.
- Produces: an `x-forwarded-for` that survives middleware and carries the visitor's address.

- [ ] **Step 1: Write the failing test**

```typescript
// apps/web/middleware.test.ts — add to the existing suite
import { describe, expect, it } from "vitest";

import { middleware } from "./middleware";

function request(headers: Record<string, string>) {
  return new Request("https://acme.relaydesk.dev/help", { headers }) as never;
}

describe("client address", () => {
  it("preserves a proxy-supplied x-forwarded-for", () => {
    // Behind a reverse proxy the socket address is the proxy's, so deleting
    // this header buckets every visitor together and the ticket cap
    // throttles the whole internet. See spec D9.
    const response = middleware(request({ "x-forwarded-for": "203.0.113.7" }));
    expect(response.headers.get("x-middleware-request-x-forwarded-for")).toBe(
      "203.0.113.7",
    );
  });

  it("still strips the workspace header a caller supplied", () => {
    const response = middleware(
      request({ host: "acme.relaydesk.dev", "x-relaydesk-workspace": "victim" }),
    );
    expect(
      response.headers.get("x-middleware-request-x-relaydesk-workspace"),
    ).toBe("acme");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm vitest run middleware.test.ts`
Expected: FAIL on the first test — the header is deleted, so the value is `null`

- [ ] **Step 3: Replace the deletion with a comment that is true**

In `apps/web/middleware.ts`, delete the `headers.delete("x-forwarded-for")`
line and its comment block, and put this in their place:

```typescript
  // `x-forwarded-for` is deliberately NOT stripped here, and that is only
  // safe because of how this container is reached. Next fills the header in
  // from `socket.remoteAddress` when it is absent -- which is the visitor's
  // address only when Next itself faces the internet. Behind the reverse
  // proxy every real deployment needs, that socket belongs to the proxy, so
  // stripping the header buckets every visitor in the world together and
  // `TICKET_IP_HOURLY_CAP` then throttles all of them to five an hour.
  // Silently, and failing closed.
  //
  // What makes the incoming value trustworthy instead is that nothing can
  // reach this container except the proxy: the web service publishes no
  // port (see docker-compose.yml) and the proxy itself accepts
  // `X-Forwarded-For` only from its own upstream edge. Break either of
  // those and a caller can pick its own rate-limit bucket again.
```

The `x-relaydesk-workspace` deletion above it stays exactly as it is: that
header has no trustworthy source other than `Host`, and no proxy sets it.

- [ ] **Step 4: Stop publishing the web port**

In `docker-compose.yml`, remove the `ports: - "3000:3000"` mapping from the
`web` service and add:

```yaml
    # No published port. The reverse proxy is the only thing that may reach
    # this container, which is what lets middleware.ts trust the
    # X-Forwarded-For it receives. See the comment there.
```

Local development reaches the app through the proxy; a developer who needs
the container directly can add the mapping in an override file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/web && pnpm vitest run middleware.test.ts`
Expected: PASS (both tests, plus the existing suite)

- [ ] **Step 6: Commit**

```bash
git add apps/web/middleware.ts apps/web/middleware.test.ts docker-compose.yml
git commit -m "fix(web): behind a proxy, one bucket held every visitor"
```

---

### Task 8: The frame

**Files:**
- Create: `apps/web/app/(widget)/widget/frame/page.tsx`
- Create: `apps/web/components/widget/panel.tsx`
- Create: `apps/web/lib/api/widget.ts`
- Test: `apps/web/components/widget/panel.test.tsx`

**Interfaces:**
- Consumes: `GET /widget/{key}` (Task 5), `POST /widget/{key}/tickets` (Task 6).
- Produces: a route at `/widget/frame?key=rdw_…` that sends `Content-Security-Policy: frame-ancestors …`.

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/components/widget/panel.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Panel } from "@/components/widget/panel";

const workspace = { workspaceName: "Beacon", monogram: "BE", settings: {} };

describe("Panel", () => {
  it("offers search when the knowledge base has articles", () => {
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByPlaceholderText("Search for an answer")).toBeTruthy();
  });

  it("skips search entirely when there are no articles", () => {
    // The day-one state for every new customer: a search box over nothing
    // makes the product look broken on the day it is being judged.
    render(<Panel {...workspace} articleCount={0} />);
    expect(screen.queryByPlaceholderText("Search for an answer")).toBeNull();
    expect(screen.getByLabelText("Your message")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm vitest run components/widget/panel.test.tsx`
Expected: FAIL — cannot resolve `@/components/widget/panel`

- [ ] **Step 3: Build the panel**

`WidgetBootstrapOut` inherits `CamelModel`, so the API already answers in
camelCase — `workspaceName`, `articleCount` — matching the console's
TypeScript field for field. `lib/api/widget.ts` needs no mapping layer; it
fetches and types the response. Follow `apps/web/lib/api/public.ts`.

```tsx
// apps/web/components/widget/panel.tsx
"use client";

import { useState } from "react";

export type PanelProps = {
  workspaceName: string;
  monogram: string;
  settings: Record<string, unknown>;
  articleCount: number;
};

// Home and Results both offer search; Empty never mounts it. Article and
// Compose are reachable from either, and Sent is terminal.
type View =
  | { name: "home" }
  | { name: "results"; query: string }
  | { name: "article"; path: string }
  | { name: "compose" }
  | { name: "sent" };

export function Panel({ workspaceName, monogram, articleCount }: PanelProps) {
  // The day-one state for every new customer. Deciding it from articleCount
  // rather than from a failed search is what stops a new workspace ever
  // rendering a search box over nothing.
  const empty = articleCount === 0;
  const [view, setView] = useState<View>(() =>
    empty ? { name: "compose" } : { name: "home" },
  );

  return (
    <div className="flex h-screen flex-col bg-ink-50">
      <Header name={workspaceName} monogram={monogram} />
      {view.name === "home" && (
        <Home onSearch={(query) => setView({ name: "results", query })} />
      )}
      {view.name === "results" && (
        <Results
          query={view.query}
          onOpen={(path) => setView({ name: "article", path })}
          onCompose={() => setView({ name: "compose" })}
        />
      )}
      {view.name === "article" && (
        <Article path={view.path} onCompose={() => setView({ name: "compose" })} />
      )}
      {view.name === "compose" && (
        <Compose
          showBack={!empty}
          onSent={() => setView({ name: "sent" })}
        />
      )}
      {view.name === "sent" && <Sent onHome={() => setView({ name: "home" })} />}
      <Footer />
    </div>
  );
}
```

Build `Header`, `Home`, `Results`, `Article`, `Compose`, `Sent` and `Footer`
as sibling components in the same directory, from the published design at
`docs/superpowers/specs/2026-09-10-support-widget-design.md` §7. `Home`
renders the search field with placeholder `"Search for an answer"`; `Compose`
labels its textarea `"Your message"`.

Use the tokens named in Global Constraints. The two rules that carry meaning
rather than taste:

- "Send a message" is a **secondary** control on Home and a **primary** one
  after a search or at the foot of an article. That progression is the
  deflection hierarchy; flattening it removes the strategy.
- Dark follows `prefers-color-scheme` only — cross-origin, the host page's
  theme cannot be read. In dark, citron carries the primary action, because
  `ink-900` on `ink-800` is not a button.

Accessibility is required, not optional — this renders inside other people's
sites: trap focus while open, close on `Esc` and return focus to the
launcher, announce results with `aria-live`, label the launcher, and respect
`prefers-reduced-motion`.

- [ ] **Step 4: Serve the frame with its CSP**

```tsx
// apps/web/app/(widget)/widget/frame/page.tsx
import { notFound } from "next/navigation";

import { Panel } from "@/components/widget/panel";
import { getWidgetBootstrap } from "@/lib/api/widget";

export default async function WidgetFramePage({
  searchParams,
}: {
  searchParams: Promise<{ key?: string }>;
}) {
  const { key } = await searchParams;
  if (!key) notFound();

  const bootstrap = await getWidgetBootstrap(key);
  if (!bootstrap) notFound();

  return <Panel {...bootstrap} />;
}
```

A page component cannot set a response header, and `next.config.ts` headers
are static while this one is per-key. So **middleware sets it**, which is the
only place in Next that can.

Add to `apps/web/middleware.ts`, and add `/widget/frame` to its `matcher`:

```typescript
  // The frame's own CSP, and the only per-key header in the app. Unlike the
  // workspace resolution above -- pure string maths on Host -- this needs a
  // lookup, so it costs one API call per panel open. That is the price of
  // per-key origins; it is not on the portal's path and does not slow it.
  if (pathname === "/widget/frame") {
    const key = request.nextUrl.searchParams.get("key");
    const policy = key ? await embedPolicy(key) : "frame-ancestors 'none'";
    const response = NextResponse.next({ request: { headers } });
    response.headers.set("Content-Security-Policy", policy);
    return response;
  }
```

`embedPolicy` calls a dedicated endpoint that returns only the header string,
so the lookup carries nothing else. Add it to `apps/api/src/relaydesk/api/widget.py`:

```python
@router.get("/{key}/embed-policy", response_class=PlainTextResponse)
async def embed_policy(key: str, session: DbSession) -> str:
    """The frame's ``frame-ancestors`` value, and nothing else.

    An unknown or inactive key answers ``'none'`` rather than 404: the frame
    must refuse to render either way, and a 404 here would tell a caller
    which keys exist.
    """
    try:
        widget_key = await widget_keys.resolve(db_session, key)
    except NotFound:
        return "frame-ancestors 'none'"
    return widget_origins.frame_ancestors(widget_key.allowed_origins)
```

Declare it above the `{path:path}` catch-all, with the other fixed segments.

- [ ] **Step 5: Test that an unconfigured key cannot be framed**

```python
# apps/api/tests/test_widget_api.py — append
async def test_embed_policy_refuses_when_no_origins_are_set(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.get(f"/api/widget/{key.key}/embed-policy")
    assert response.text == "frame-ancestors 'none'"


async def test_embed_policy_answers_none_for_an_unknown_key(client, db_session):
    response = await client.get("/api/widget/rdw_" + "0" * 32 + "/embed-policy")
    assert response.status_code == 200
    assert response.text == "frame-ancestors 'none'"
```

Run: `docker compose exec -T api pytest tests/test_widget_api.py -v`
Expected: PASS

- [ ] **Step 6: Run the panel tests**

Run: `cd apps/web && pnpm vitest run components/widget/panel.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/web/app/\(widget\) apps/web/components/widget apps/web/lib/api/widget.ts apps/web/middleware.ts apps/api/src/relaydesk/api/widget.py apps/api/tests/test_widget_api.py
git commit -m "feat(widget): the panel, and an empty knowledge base as a screen"
```

---

### Task 9: The loader

**Files:**
- Create: `apps/web/public/widget.js`
- Test: `apps/web/public/widget.test.ts`

**Interfaces:**
- Consumes: `/widget/frame?key=…` (Task 8).
- Produces: the frozen embed contract `<script async src="…/widget.js" data-key="rdw_…">`.

- [ ] **Step 1: Write the failing test**

```typescript
// apps/web/public/widget.test.ts
import { describe, expect, it } from "vitest";
import { readFileSync, statSync } from "node:fs";

describe("loader", () => {
  it("stays under the 3 KB budget", () => {
    // Spec D6: this is the argument for choosing the widget over a heavier
    // messenger, so a regression here is a regression in the pitch.
    expect(statSync("public/widget.js").size).toBeLessThan(3072);
  });

  it("injects no iframe until the launcher is clicked", () => {
    const source = readFileSync("public/widget.js", "utf8");
    const launcher = source.indexOf("createElement(\"button\")");
    const frame = source.indexOf("createElement(\"iframe\")");
    expect(launcher).toBeGreaterThan(-1);
    expect(frame).toBeGreaterThan(launcher);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm vitest run public/widget.test.ts`
Expected: FAIL — `ENOENT: public/widget.js`

- [ ] **Step 3: Write the loader**

Deliberately dumb, and its contract is frozen: it is pasted into sites
Relaydesk does not control and will never be re-pasted (spec D6). Read the
key, draw a launcher, inject the frame on first open. Nothing else. Inline
styles only — the launcher lives outside the iframe and must not depend on a
stylesheet the host page has never loaded.

```javascript
(function () {
  var tag = document.currentScript;
  var key = tag && tag.getAttribute("data-key");
  if (!key) return;

  var origin = new URL(tag.src).origin;
  // Prefill only. Nothing can be read with an address, because the widget
  // never reads a conversation (spec D4) -- so this is not an
  // authentication claim and needs no signature.
  var email = tag.getAttribute("data-email") || "";
  var person = tag.getAttribute("data-name") || "";
  var frame = null;
  var open = false;

  var launcher = document.createElement("button");
  launcher.setAttribute("aria-label", "Help");
  launcher.style.cssText =
    "position:fixed;right:24px;bottom:24px;width:56px;height:56px;border:0;" +
    "border-radius:9999px;background:#18181B;color:#fff;cursor:pointer;" +
    "z-index:2147480000;box-shadow:0 10px 38px -10px rgba(9,9,11,.35)";
  launcher.innerHTML =
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" ' +
    'stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.7 8.7 0 ' +
    '0 1-3.8-.9L3 20.5l1.6-4.9A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z"/></svg>';

  function panel() {
    if (frame) return frame;
    frame = document.createElement("iframe");
    frame.title = "Help";
    frame.src =
      origin +
      "/widget/frame?key=" +
      encodeURIComponent(key) +
      (email ? "&email=" + encodeURIComponent(email) : "") +
      (person ? "&name=" + encodeURIComponent(person) : "");
    frame.style.cssText =
      "position:fixed;right:24px;bottom:96px;width:380px;height:600px;border:0;" +
      "border-radius:16px;z-index:2147480000;" +
      "box-shadow:0 10px 38px -10px rgba(9,9,11,.20)";
    document.body.appendChild(frame);
    return frame;
  }

  launcher.addEventListener("click", function () {
    open = !open;
    panel().style.display = open ? "block" : "none";
  });

  window.addEventListener("message", function (event) {
    if (event.origin !== origin || event.data !== "relaydesk:close") return;
    open = false;
    if (frame) frame.style.display = "none";
  });

  document.body.appendChild(launcher);
})();
```

The `z-index` sits high but well below the maximum, so a host page's own
modals can still cover the launcher.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && pnpm vitest run public/widget.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/web/public/widget.js apps/web/public/widget.test.ts
git commit -m "feat(widget): a loader small enough to be the argument"
```

---

### Task 10: The console screen

**Files:**
- Create: `apps/web/app/(console)/settings/widget/page.tsx`
- Create: `apps/web/components/settings/widget-keys.tsx`
- Modify: the settings navigation component
- Test: `apps/web/components/settings/widget-keys.test.tsx`

**Interfaces:**
- Consumes: `GET/POST/PATCH/DELETE /widget-keys` (Task 4).
- Produces: a settings screen at `/settings/widget`.

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/components/settings/widget-keys.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WidgetKeys } from "@/components/settings/widget-keys";

const key = {
  id: "1",
  name: "Marketing site",
  key: "rdw_abc",
  allowedOrigins: [],
  settings: {},
  active: true,
  lastSeenAt: null,
  createdAt: "2026-09-10T00:00:00Z",
};

describe("WidgetKeys", () => {
  it("says an embed with no origins will not load", () => {
    // An empty allowlist refuses. Without this the admin sees a snippet
    // that looks finished and a widget that silently never appears.
    render(<WidgetKeys keys={[key]} />);
    expect(screen.getByText(/add the sites/i)).toBeTruthy();
  });

  it("shows the snippet with the key in it", () => {
    render(<WidgetKeys keys={[{ ...key, allowedOrigins: ["https://acme.com"] }]} />);
    expect(screen.getByText(/data-key="rdw_abc"/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm vitest run components/settings/widget-keys.test.tsx`
Expected: FAIL — cannot resolve `@/components/settings/widget-keys`

- [ ] **Step 3: Build the screen**

```tsx
// apps/web/components/settings/widget-keys.tsx
import { SectionEmpty, SettingSection } from "@/components/console/setting-section";
import type { WidgetKey } from "@/lib/api/widget-keys";

function snippet(key: string): string {
  return `<script async src="https://app.relaydesk.dev/widget.js" data-key="${key}"></script>`;
}

export function WidgetKeys({ keys }: { keys: WidgetKey[] }) {
  if (keys.length === 0) {
    return <SectionEmpty>No embeds yet.</SectionEmpty>;
  }

  return (
    <div className="flex flex-col gap-4">
      {keys.map((embed) => (
        <SettingSection key={embed.id} title={embed.name}>
          <pre className="overflow-x-auto rounded-md border border-ink-200 bg-ink-50 p-3 text-[13px] text-ink-700">
            {snippet(embed.key)}
          </pre>
          {/* The key is public and appears in the customer's page source --
              the opposite of the API key on the neighbouring screen, which
              must never be pasted into a page. Saying so here is the only
              place a reader finds out. */}
          <p className="mt-2 text-[13px] text-ink-500">
            This key is public. It appears in the source of every page that
            embeds the widget, so it is safe to paste — unlike an API key.
          </p>
          {embed.allowedOrigins.length === 0 ? (
            // An empty allowlist refuses. Without this line the admin sees a
            // finished-looking snippet and a widget that silently never
            // appears, with nothing anywhere to explain why.
            <p className="mt-3 text-[13px] text-danger-700">
              Add the sites allowed to show this widget — until you do, it
              will not load anywhere.
            </p>
          ) : (
            <ul className="mt-3 flex flex-col gap-1 text-[13px] text-ink-700">
              {embed.allowedOrigins.map((origin) => (
                <li key={origin}>{origin}</li>
              ))}
            </ul>
          )}
        </SettingSection>
      ))}
    </div>
  );
}
```

Add the create dialog, active toggle and delete following
`apps/web/components/settings/snippet-dialog.tsx`, and the page shell
following `apps/web/app/(console)/settings/custom-webhooks/page.tsx` —
`requireAdmin()`, `PageHeader`, then this component.

Two things the copy must carry, because both are silent failures otherwise:
an embed with no origins **will not load anywhere**, and the key **is public
and appears in page source** — unlike the API key on the neighbouring screen,
which must never be pasted into a page.

- [ ] **Step 4: Add it to the settings navigation**

Place it beside "Custom webhooks" in the settings nav.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/web && pnpm vitest run components/settings/widget-keys.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 6: Run the whole suite**

Run: `docker compose exec -T api pytest` then `cd apps/web && pnpm vitest run`
Expected: PASS — nothing above may regress the portal or the public API

- [ ] **Step 7: Commit**

```bash
git add apps/web/app/\(console\)/settings/widget apps/web/components/settings/widget-keys.tsx apps/web/components/settings/widget-keys.test.tsx
git commit -m "feat(widget): manage embeds from settings"
```

---

### Task 11: The deflection baseline

The counters spec §1 promises and §4 now describes. Do this in the same slice
as the widget, not after it: deflection cannot be measured retroactively, and
a workspace that runs uninstrumented for three months has lost the only
baseline its later AI numbers could be judged against.

**Files:**
- Create: `apps/api/src/relaydesk/models/widget_session.py`
- Create: `apps/api/migrations/versions/0024_widget_sessions.py`
- Create: `apps/api/src/relaydesk/services/widget_sessions.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Modify: `apps/api/src/relaydesk/api/widget.py`
- Test: `apps/api/tests/test_widget_sessions.py`

**Interfaces:**
- Consumes: `WidgetKey` (Task 1), the `/widget/{key}` router (Task 5).
- Produces: `POST /widget/{key}/sessions/{session_id}` accepting `{"kind": "searched" | "read" | "submitted"}`, and `widget_sessions.record(db_session, widget_key, session_id, kind) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_widget_sessions.py
import uuid

import pytest
import sqlalchemy as sa

from relaydesk.models.widget_session import WidgetSession
from relaydesk.services import widget_keys, widget_sessions
from tests.factories import make_workspace


async def test_first_event_opens_the_session(db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    session_id = uuid.uuid4()

    await widget_sessions.record(db_session, key, session_id, "searched")

    row = await db_session.scalar(
        sa.select(WidgetSession).where(WidgetSession.id == session_id)
    )
    assert row.searched is True
    assert row.submitted is False
    assert row.workspace_id == workspace.id


async def test_repeating_an_event_writes_one_row(db_session):
    """A visitor who searches four times is one session, not four."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    session_id = uuid.uuid4()

    for _ in range(4):
        await widget_sessions.record(db_session, key, session_id, "searched")

    count = await db_session.scalar(sa.select(sa.func.count()).select_from(WidgetSession))
    assert count == 1


async def test_flags_accumulate_and_never_lower(db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    session_id = uuid.uuid4()

    await widget_sessions.record(db_session, key, session_id, "searched")
    await widget_sessions.record(db_session, key, session_id, "read")
    await widget_sessions.record(db_session, key, session_id, "submitted")

    row = await db_session.scalar(
        sa.select(WidgetSession).where(WidgetSession.id == session_id)
    )
    assert (row.searched, row.read_article, row.submitted) == (True, True, True)


async def test_an_unknown_kind_is_refused(db_session):
    from relaydesk.errors import Invalid

    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")

    with pytest.raises(Invalid):
        await widget_sessions.record(db_session, key, uuid.uuid4(), "purchased")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_widget_sessions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.models.widget_session'`

- [ ] **Step 3: Write the model**

```python
# apps/api/src/relaydesk/models/widget_session.py
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin


class WidgetSession(Base, TimestampMixin):
    """One panel open, and how far it got. The deflection baseline.

    Three booleans rather than an event stream: a visitor who searches four
    times is one row, the ratio is one query, and there is nothing to prune.

    The ratio this exists to answer is, of the sessions that tried to
    self-serve -- ``searched or read_article`` -- the share that did not go
    on to ``submitted``. Sessions that did neither are not deflection in
    either direction and belong in neither half of the fraction.

    ``ActivityEvent`` was the obvious home and cannot serve: its
    ``conversation_id`` is NOT NULL, and the sessions worth counting are
    exactly the ones that never produced a conversation.

    ``id`` is minted by the frame and is opaque. There is deliberately no
    address, no email, no query text and no article here -- three booleans
    and an id attributable to nobody. This table records the behaviour of
    other companies' customers, and that is the whole of what it may know.
    """

    __tablename__ = "widget_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    widget_key_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("widget_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    searched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_article: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
```

Register it in `models/__init__.py` with the others: import, and `"WidgetSession"` in `__all__` after `"WidgetKey"`.

- [ ] **Step 4: Write the migration**

```python
# apps/api/migrations/versions/0024_widget_sessions.py
"""widget sessions

One row per panel open, carrying how far that visit got: searched, read an
article, submitted. This is the deflection baseline, and it is in the same
slice as the widget because deflection cannot be measured retroactively --
a workspace only has a before-and-after if the before was recorded.

Three booleans rather than an event stream, so a visitor who searches four
times is one row. No address, no email, no query text: the id is opaque and
attributable to nobody.

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-10 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "widget_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("widget_key_id", sa.UUID(), nullable=False),
        sa.Column("searched", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "read_article", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("submitted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["widget_key_id"], ["widget_keys.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_widget_sessions_workspace_id",
        "widget_sessions",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_widget_sessions_workspace_id", table_name="widget_sessions")
    op.drop_table("widget_sessions")
```

- [ ] **Step 5: Write the service**

```python
# apps/api/src/relaydesk/services/widget_sessions.py
"""Raising a widget session's flags, once each, whatever the visitor does."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models.widget_key import WidgetKey
from relaydesk.models.widget_session import WidgetSession

# The visitor supplies this, so it is matched against a closed set rather
# than written through to a column name.
_FLAGS = {"searched": "searched", "read": "read_article", "submitted": "submitted"}


async def record(
    session: AsyncSession,
    widget_key: WidgetKey,
    session_id: uuid.UUID,
    kind: str,
) -> None:
    """Raise one flag on a session, creating the row the first time.

    An upsert rather than a read-then-write: the frame fires these
    concurrently -- a search and an article open can overlap -- and two
    inserts racing on the same id would otherwise be a primary-key error on
    an endpoint whose failure the visitor must never see.

    Flags only ever go up. ``ON CONFLICT`` re-asserts the raised one and
    leaves the rest alone, so events arriving out of order still land.
    """
    flag = _FLAGS.get(kind)
    if flag is None:
        raise Invalid("Unknown widget event.")

    now = datetime.now(UTC)
    statement = insert(WidgetSession).values(
        id=session_id,
        workspace_id=widget_key.workspace_id,
        widget_key_id=widget_key.id,
        started_at=now,
        created_at=now,
        updated_at=now,
        **{flag: True},
    )
    await db_session.execute(
        statement.on_conflict_do_update(
            index_elements=[WidgetSession.id],
            set_={flag: True, "updated_at": now},
        )
    )
    await db_session.flush()
```

- [ ] **Step 6: Add the route**

Append to `apps/api/src/relaydesk/api/widget.py`, above the `{path:path}` catch-all:

```python
@router.post("/{key}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def record_event(
    key: str, session_id: uuid.UUID, body: WidgetEventIn, session: DbSession
) -> None:
    """Record how far one panel open got. Never fails visibly to the visitor."""
    widget_key = await widget_keys.resolve(db_session, key)
    await widget_sessions.record(db_session, widget_key, session_id, body.kind)
```

with `class WidgetEventIn(CamelModel): kind: str` in `schemas/widget.py`.

The frame mints a session id with `crypto.randomUUID()` on open, holds it for
the life of the panel, and posts `searched` on the first search, `read` on the
first article, and `submitted` after a successful send. Failures are swallowed
in the frame: a counter must never be able to break a support request.

- [ ] **Step 7: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_widget_sessions.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Run the whole suite**

Run: `docker compose exec -T api pytest` then `cd apps/web && pnpm vitest run`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/relaydesk/models/widget_session.py apps/api/src/relaydesk/models/__init__.py apps/api/migrations/versions/0024_widget_sessions.py apps/api/src/relaydesk/services/widget_sessions.py apps/api/src/relaydesk/api/widget.py apps/api/src/relaydesk/schemas/widget.py apps/api/tests/test_widget_sessions.py
git commit -m "feat(widget): a deflection baseline, because it cannot be measured later"
```
