# Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a workspace a knowledge base — internal procedures an agent follows, and a customer-facing hub served on its own portal subdomain.

**Architecture:** Two tables (`kb_categories`, `kb_articles`) scoped per workspace, with a draft → ready → published review workflow. Articles are authored in a TipTap editor and stored as ProseMirror JSON, never HTML, so nothing untrusted is ever persisted or re-rendered; plain text is extracted server-side on write to feed Postgres full-text search and, later, AI grounding. Images reuse slice 2's content-addressed blob storage, extracted into a shared module. The public hub is anonymous, read-only, server-rendered, and finds its workspace from the request's subdomain.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, Postgres 16 (JSONB, `tsvector`, GIN), Next.js 16 App Router / React 19, TipTap 3.

**Spec:** `docs/superpowers/specs/2026-09-05-knowledge-base-design.md`

## Global Constraints

Copied from the spec. Every task's requirements implicitly include this section.

- **Tenancy:** every domain table carries `workspace_id`; every query reading or writing a domain row carries a `workspace_id` predicate. A cross-workspace id returns **404, never 403**.
- **No user-supplied HTML is ever stored or rendered.** Articles are ProseMirror JSON. The public site renders from that tree with React elements — there is no `dangerouslySetInnerHTML` anywhere in this slice, and an unknown node type renders nothing.
- **Public reads are restricted to `published` articles in `external` categories.** Anything else is 404, not 403.
- **Article images inherit their article's visibility** on the public path.
- **The image allowlist excludes `image/svg+xml`** — SVG executes script when rendered inline.
- **Enums:** `enum.StrEnum` with `sa.Enum(..., native_enum=False, length=16, create_constraint=True)`.
- **Migrations** continue from `0010`, starting at `0011`.
- **Schemas live in `relaydesk/schemas/`**, never inline in routers. All inherit `CamelModel` (`schemas/base.py`).
- **Errors:** services raise `relaydesk.errors.*`; routers never build error envelopes by hand.
- **Sessions:** `expire_on_commit=False` globally; relationships `lazy="selectin"`.
- **Reserved subdomain labels** — `www`, `app`, `api`, `admin`, `mail`, `inbound` — never resolve to a workspace and cannot be registered as slugs.
- **Lint:** `ruff check .` clean, line length 88, rules `E,F,I,UP,B`. `pnpm lint` 0 problems, `pnpm build` clean.
- **Never call `asyncio.run()`, `asyncio.set_event_loop()`, or `loop.run_until_complete()` in a test.** The repo runs `asyncio_mode = "auto"` with a session-scoped fixture loop; nine tasks in slice 2 hit this and it silently breaks dozens of unrelated tests.
- **Test factories:** `make_workspace(session, slug="chronon") -> Workspace`; `make_member(session, workspace, email=..., role=...) -> User`; `sign_in(client, session, user_email) -> dict` returning ready-made headers.
- **Default test command:** `pytest -m "not integration"`.

---

## File Structure

**New API modules**

| Path | Responsibility |
|---|---|
| `models/kb.py` | `KbCategory`, `KbArticle`, `KbImage`, and their enums |
| `services/blobs.py` | Content-addressed write and containment-checked read, shared with attachments |
| `services/kb_categories.py` | Category CRUD and ordering |
| `services/kb_articles.py` | Article CRUD, slugs, the status machine |
| `services/kb_text.py` | ProseMirror document → plain text. Pure, no I/O |
| `services/kb_public.py` | The public read surface: published external only |
| `api/kb.py` | Authenticated console routes |
| `api/public.py` | Anonymous portal routes |
| `schemas/kb.py` | Every KB request and response model |

**New web modules**

| Path | Responsibility |
|---|---|
| `lib/api/kb.ts` | Console API client |
| `app/(console)/knowledge-base/[id]/page.tsx` | The editor |
| `components/knowledge-base/editor.tsx` | TipTap wrapper and toolbar |
| `components/knowledge-base/doc-renderer.tsx` | ProseMirror JSON → React elements |
| `app/(portal)/help/**` | The four public routes |
| `middleware.ts` | Subdomain → workspace slug rewrite (modified) |

`kb_text.py` is deliberately pure and separate: it is the one piece slice 4 will depend on, and keeping it free of I/O means it can be tested exhaustively against document fixtures.

---

### Task 1: Models, migration 0011, and the shared blob layer

Everything else reads and writes these tables. The blob extraction is folded in here rather than deferred, because Task 6 needs it and doing it now means slice 2's traversal protections are inherited rather than reimplemented.

**Files:**
- Create: `apps/api/src/relaydesk/models/kb.py`
- Create: `apps/api/src/relaydesk/services/blobs.py`
- Modify: `apps/api/src/relaydesk/services/attachments.py` (use `blobs`)
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Create: `apps/api/migrations/versions/0011_knowledge_base.py`
- Test: `apps/api/tests/test_kb_models.py` (create)
- Test: `apps/api/tests/test_blobs.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `KbScope.{internal,external}`, `ArticleStatus.{draft,ready,published}`
  - `KbCategory(workspace_id, scope, name, slug, position)`
  - `KbArticle(workspace_id, category_id, title, slug, excerpt, doc, body_text, status, author_user_id, published_at, search_vector)`
  - `KbImage(workspace_id, article_id, filename, content_type, size_bytes, sha256, storage_key)`
  - `blobs.write(root: Path, workspace_id: uuid.UUID, content: bytes) -> tuple[str, str]` returning `(sha256, storage_key)`
  - `blobs.read(root: Path, workspace_id: uuid.UUID, sha256: str) -> bytes` — raises `NotFound`

- [ ] **Step 1: Write the failing blob test**

Create `apps/api/tests/test_blobs.py`:

```python
import hashlib
import uuid
from pathlib import Path

import pytest

from relaydesk.errors import NotFound
from relaydesk.services import blobs


def test_content_is_addressed_by_hash(tmp_path: Path) -> None:
    workspace_id = uuid.uuid4()

    digest, key = blobs.write(tmp_path, workspace_id, b"hello")

    assert digest == hashlib.sha256(b"hello").hexdigest()
    assert key == f"{workspace_id}/{digest}"
    assert (tmp_path / str(workspace_id) / digest).read_bytes() == b"hello"


def test_identical_bytes_are_written_once(tmp_path: Path) -> None:
    workspace_id = uuid.uuid4()

    first, _ = blobs.write(tmp_path, workspace_id, b"same")
    second, _ = blobs.write(tmp_path, workspace_id, b"same")

    assert first == second
    assert [p.name for p in (tmp_path / str(workspace_id)).iterdir()] == [first]


def test_two_workspaces_do_not_share_a_path(tmp_path: Path) -> None:
    one, two = uuid.uuid4(), uuid.uuid4()

    blobs.write(tmp_path, one, b"same")
    blobs.write(tmp_path, two, b"same")

    assert blobs.read(tmp_path, one, hashlib.sha256(b"same").hexdigest()) == b"same"
    assert (tmp_path / str(one)).exists()
    assert (tmp_path / str(two)).exists()


def test_a_hostile_hash_cannot_escape_the_workspace_directory(tmp_path: Path) -> None:
    """The containment check is the only thing between one tenant's files and
    another's. Without it this resolves to a real file outside the root."""
    workspace_id = uuid.uuid4()
    (tmp_path / str(workspace_id)).mkdir(parents=True)
    (tmp_path / "secret").write_bytes(b"not yours")

    with pytest.raises(NotFound):
        blobs.read(tmp_path, workspace_id, "../secret")


def test_a_missing_blob_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFound):
        blobs.read(tmp_path, uuid.uuid4(), "0" * 64)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_blobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.services.blobs'`.

- [ ] **Step 3: Write the blob layer**

Create `apps/api/src/relaydesk/services/blobs.py`:

```python
"""Content-addressed storage for bytes that arrived from outside.

Files live at ``<root>/<workspace id>/<sha256>``. The name a sender or
uploader chose never reaches a path: the hash is what makes traversal
structurally impossible rather than merely filtered.

Extracted from the attachment store so message attachments and knowledge-base
images share one implementation. The containment check on read exists because
a caller's stored key could be malformed by a bad migration or a second
writer, and a path that escapes its workspace directory would still have
matched on the ``workspace_id`` column.
"""

import hashlib
import uuid
from pathlib import Path

from relaydesk.errors import NotFound


def write(root: Path, workspace_id: uuid.UUID, content: bytes) -> tuple[str, str]:
    """Store ``content`` and return ``(sha256, storage_key)``."""
    directory = root / str(workspace_id)
    directory.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(content).hexdigest()
    path = directory / digest
    if not path.exists():
        # Write to a temporary name and rename, so a crash mid-write cannot
        # leave a truncated file at a hash that claims to be whole.
        temporary = directory / f".{digest}.{uuid.uuid4().hex}"
        temporary.write_bytes(content)
        temporary.rename(path)

    return digest, f"{workspace_id}/{digest}"


def read(root: Path, workspace_id: uuid.UUID, sha256: str) -> bytes:
    """Read a blob, refusing anything that resolves outside the workspace.

    The path is rebuilt from the validated ``workspace_id`` and the hash --
    never from a stored key -- and the descendant check is what holds when
    the hash itself is hostile.
    """
    base = (root / str(workspace_id)).resolve()
    path = (base / sha256).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise NotFound("That file does not exist.")
    return path.read_bytes()
```

- [ ] **Step 4: Run the blob tests**

Run: `docker compose exec api pytest tests/test_blobs.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Point attachments at the shared layer**

In `services/attachments.py`, replace the inline hashing, directory creation, and temp-write-rename in `store` with `blobs.write(_root(), message.workspace_id, item.content)`, and the `base`/`path`/`is_relative_to` block in `read` with `blobs.read(_root(), workspace_id, row.sha256)`.

Keep `safe_content_type`, `INLINE_SAFE_TYPES`, `_root`, the size cap, and the row construction exactly as they are — this is a storage extraction, not a behaviour change.

Run: `docker compose exec api pytest tests/test_attachments.py -v`
Expected: PASS, unchanged. If any attachment test now fails, the extraction changed behaviour and must be corrected rather than the test adjusted.

- [ ] **Step 6: Write the failing model test**

Create `apps/api/tests/test_kb_models.py`:

```python
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbScope
from tests.factories import make_workspace


async def _category(session: AsyncSession, workspace, *, scope=KbScope.external, slug="billing"):
    category = KbCategory(
        workspace_id=workspace.id, scope=scope, name="Billing", slug=slug, position=0
    )
    session.add(category)
    await session.flush()
    return category


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


async def test_an_article_stores_its_document_as_json(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    category = await _category(db_session, workspace)

    article = KbArticle(
        workspace_id=workspace.id,
        category_id=category.id,
        title="Refunds",
        slug="refunds",
        excerpt="How refunds work.",
        doc=_doc("Refunds are issued within 30 days."),
        body_text="Refunds are issued within 30 days.",
        status=ArticleStatus.draft,
    )
    db_session.add(article)
    await db_session.flush()

    assert article.doc["content"][0]["content"][0]["text"].startswith("Refunds")
    assert article.status is ArticleStatus.draft
    assert article.published_at is None


async def test_two_articles_cannot_share_a_slug_in_one_category(
    db_session: AsyncSession,
) -> None:
    """The slug is the public URL, so a collision inside a category would make
    one of the two unreachable."""
    workspace = await make_workspace(db_session)
    category = await _category(db_session, workspace)

    for _ in range(2):
        db_session.add(
            KbArticle(
                workspace_id=workspace.id,
                category_id=category.id,
                title="Refunds",
                slug="refunds",
                excerpt="",
                doc=_doc("x"),
                body_text="x",
                status=ArticleStatus.draft,
            )
        )

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_the_same_slug_is_fine_in_a_different_category(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    billing = await _category(db_session, workspace, slug="billing")
    returns = await _category(db_session, workspace, slug="returns")

    for category in (billing, returns):
        db_session.add(
            KbArticle(
                workspace_id=workspace.id,
                category_id=category.id,
                title="Overview",
                slug="overview",
                excerpt="",
                doc=_doc("x"),
                body_text="x",
                status=ArticleStatus.draft,
            )
        )
    await db_session.flush()


async def test_categories_are_unique_per_scope_not_globally(
    db_session: AsyncSession,
) -> None:
    """Internal and external are separate namespaces -- a workspace may well
    want a 'Billing' category in both."""
    workspace = await make_workspace(db_session)

    await _category(db_session, workspace, scope=KbScope.internal, slug="billing")
    await _category(db_session, workspace, scope=KbScope.external, slug="billing")


async def test_search_vector_is_populated_from_title_and_body(
    db_session: AsyncSession,
) -> None:
    """It is a generated column, so it must be maintained by Postgres rather
    than by anything remembering to update it."""
    workspace = await make_workspace(db_session)
    category = await _category(db_session, workspace)
    article = KbArticle(
        workspace_id=workspace.id,
        category_id=category.id,
        title="Refunds",
        slug="refunds",
        excerpt="",
        doc=_doc("x"),
        body_text="issued within thirty days",
        status=ArticleStatus.draft,
    )
    db_session.add(article)
    await db_session.flush()

    hit = await db_session.scalar(
        sa.select(KbArticle.id).where(
            KbArticle.id == article.id,
            KbArticle.search_vector.op("@@")(sa.func.plainto_tsquery("english", "thirty")),
        )
    )
    assert hit == article.id
```

- [ ] **Step 7: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_kb_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.models.kb'`.

- [ ] **Step 8: Write the models**

Create `apps/api/src/relaydesk/models/kb.py`:

```python
import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class KbScope(enum.StrEnum):
    internal = "internal"
    external = "external"


class ArticleStatus(enum.StrEnum):
    draft = "draft"
    ready = "ready"
    published = "published"


class KbCategory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "kb_categories"
    __table_args__ = (
        UniqueConstraint("workspace_id", "scope", "slug"),
        Index("ix_kb_categories_listing", "workspace_id", "scope", "position"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[KbScope] = mapped_column(
        Enum(
            KbScope,
            name="ck_kb_categories_scope",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class KbArticle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "kb_articles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "category_id", "slug"),
        Index("ix_kb_articles_listing", "workspace_id", "category_id", "status"),
        Index("ix_kb_articles_search", "search_vector", postgresql_using="gin"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # RESTRICT: a category cannot be deleted out from under its articles.
    category_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("kb_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    excerpt: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    # The ProseMirror document. Structured, never HTML -- see spec D1.
    doc: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Extracted on write, so the generated column below stays a pure function
    # of stored columns and search never depends on parsing JSON in SQL.
    body_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(
            ArticleStatus,
            name="ck_kb_articles_status",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ArticleStatus.draft,
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        sa.Computed(
            "to_tsvector('english', title || ' ' || coalesce(body_text, ''))",
            persisted=True,
        ),
        nullable=False,
    )

    category = relationship("KbCategory", lazy="selectin")
    images = relationship("KbImage", lazy="selectin", cascade="all, delete-orphan")


class KbImage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "kb_images"
    __table_args__ = (Index("ix_kb_images_article", "article_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("kb_articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
```

Register all three in `models/__init__.py` following the existing style — Alembic's autogenerate only sees models that have been imported.

- [ ] **Step 9: Generate and correct migration 0011**

Run: `docker compose exec api alembic revision --autogenerate -m "knowledge base"`

Rename to `0011_knowledge_base.py`, set `revision = "0011"` and `down_revision = "0010"`.

Then check two things autogenerate handles poorly:

**(a) The generated column.** Confirm the `search_vector` column is emitted with its `Computed` expression. If autogenerate produced a plain `TSVECTOR` column, replace it with:

```python
sa.Column(
    "search_vector",
    postgresql.TSVECTOR(),
    sa.Computed(
        "to_tsvector('english', title || ' ' || coalesce(body_text, ''))",
        persisted=True,
    ),
    nullable=False,
),
```

**(b) The GIN index.** Confirm `ix_kb_articles_search` carries `postgresql_using="gin"`. A default btree index on a `tsvector` column is not an error — it is simply never used by a `@@` query, so search silently falls back to a sequential scan.

Add to `migrations/env.py`'s `ENUM_CHECK_CONSTRAINTS` allowlist: `ck_kb_categories_scope` and `ck_kb_articles_status`. Alembic excludes type-bound CHECK constraints from the model side of every diff, so without these the empty-autogenerate verification in the next step reports spurious drops.

- [ ] **Step 10: Run the migration and the tests**

Run: `docker compose exec api alembic upgrade head`
Expected: `Running upgrade 0010 -> 0011`.

Run: `docker compose exec api pytest tests/test_kb_models.py tests/test_blobs.py tests/test_attachments.py -v`
Expected: PASS.

- [ ] **Step 11: Verify the migration matches the models**

Run: `docker compose exec api alembic revision --autogenerate -m "verify"`
Expected: the generated `upgrade()` body is empty. Any operation means a model and the migration disagree — fix the migration.

Delete it: `docker compose exec api rm migrations/versions/*_verify.py`

Also verify the downgrade round-trips: `docker compose exec api alembic downgrade 0010 && docker compose exec api alembic upgrade head`.

- [ ] **Step 12: Full suite, lint, commit**

Run: `docker compose exec api pytest -q -m "not integration" && docker compose exec api ruff check .`

```bash
git add apps/api
git commit -m "feat(api): add knowledge base models and a shared blob layer"
```

---

### Task 2: Text extraction and slugs

Two pure text transforms the rest of the slice leans on. `extract_text` is also the one function slice 4 will depend on for AI grounding, so it is kept free of I/O and tested exhaustively against document fixtures.

**Files:**
- Create: `apps/api/src/relaydesk/services/kb_text.py`
- Test: `apps/api/tests/test_kb_text.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `kb_text.extract_text(doc: dict) -> str`
  - `kb_text.slugify(value: str) -> str`
  - `kb_text.derive_excerpt(body_text: str, limit: int = 200) -> str`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_kb_text.py`:

```python
from relaydesk.services.kb_text import derive_excerpt, extract_text, slugify


def _doc(*content: dict) -> dict:
    return {"type": "doc", "content": list(content)}


def _para(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def test_text_is_extracted_in_document_order() -> None:
    doc = _doc(_para("First."), _para("Second."))

    assert extract_text(doc) == "First. Second."


def test_nested_content_is_reached() -> None:
    """Lists nest two levels deep, and a flat walk would miss the text."""
    doc = _doc(
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [_para("Alpha")]},
                {"type": "listItem", "content": [_para("Beta")]},
            ],
        }
    )

    assert extract_text(doc) == "Alpha Beta"


def test_an_unknown_node_type_does_not_stop_extraction() -> None:
    """A document written by a newer editor must still yield its text."""
    doc = _doc(_para("Before"), {"type": "somethingNew", "content": [_para("Inside")]}, _para("After"))

    assert extract_text(doc) == "Before Inside After"


def test_a_document_with_no_text_yields_an_empty_string() -> None:
    doc = _doc({"type": "horizontalRule"})

    assert extract_text(doc) == ""


def test_a_malformed_document_does_not_raise() -> None:
    """This runs on whatever the editor posts. Raising here would fail a save
    the author cannot diagnose."""
    assert extract_text({}) == ""
    assert extract_text({"type": "doc", "content": "not a list"}) == ""
    assert extract_text({"type": "doc", "content": [None, 42, "text"]}) == ""


def test_slugify_lowercases_and_hyphenates() -> None:
    assert slugify("Handling a Refund Request") == "handling-a-refund-request"


def test_slugify_strips_punctuation_and_collapses_separators() -> None:
    assert slugify("What's new?  (2026 edition)") == "whats-new-2026-edition"


def test_slugify_never_returns_an_empty_string() -> None:
    """An empty slug would produce an unreachable URL, so it falls back."""
    assert slugify("") == "untitled"
    assert slugify("!!!") == "untitled"
    assert slugify("   ") == "untitled"


def test_slugify_bounds_its_output() -> None:
    assert len(slugify("word " * 100)) <= 200


def test_derive_excerpt_truncates_on_a_word_boundary() -> None:
    text = "Refunds are issued within thirty days of the original charge date."

    assert derive_excerpt(text, limit=30) == "Refunds are issued within…"


def test_derive_excerpt_leaves_short_text_alone() -> None:
    assert derive_excerpt("Short.", limit=200) == "Short."
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_kb_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.services.kb_text'`.

- [ ] **Step 3: Write the module**

Create `apps/api/src/relaydesk/services/kb_text.py`:

```python
"""Text transforms for the knowledge base. Pure -- no database, no settings.

``extract_text`` is what feeds Postgres full-text search today and what slice
4 will retrieve against for AI grounding, so it is kept free of I/O and
tolerant of anything the editor posts: an unknown node type is walked
through rather than tripped over, and a malformed document yields an empty
string rather than raising into a save the author cannot diagnose.
"""

import re
import unicodedata

SLUG_MAX_LENGTH = 200
SLUG_FALLBACK = "untitled"

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


def extract_text(doc: object) -> str:
    """Concatenate every text node in document order."""
    parts: list[str] = []
    _walk(doc, parts)
    return _WHITESPACE.sub(" ", " ".join(parts)).strip()


def _walk(node: object, parts: list[str]) -> None:
    if not isinstance(node, dict):
        return

    text = node.get("text")
    if isinstance(text, str):
        parts.append(text)

    content = node.get("content")
    if isinstance(content, list):
        for child in content:
            _walk(child, parts)


def slugify(value: str) -> str:
    """A URL-safe, stable identifier. Never empty, always bounded."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _NON_SLUG.sub("-", ascii_only.lower()).strip("-")
    return (slug or SLUG_FALLBACK)[:SLUG_MAX_LENGTH].strip("-") or SLUG_FALLBACK


def derive_excerpt(body_text: str, limit: int = 200) -> str:
    """The fallback shown under a title when nobody wrote one."""
    text = body_text.strip()
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{clipped}…"
```

- [ ] **Step 4: Run the tests, lint, commit**

Run: `docker compose exec api pytest tests/test_kb_text.py -v`
Expected: PASS (11 passed).

Run: `docker compose exec api ruff check .`

```bash
git add apps/api/src/relaydesk/services/kb_text.py apps/api/tests/test_kb_text.py
git commit -m "feat(api): extract knowledge base text and slugs"
```

---

### Task 3: Categories

**Files:**
- Create: `apps/api/src/relaydesk/services/kb_categories.py`
- Create: `apps/api/src/relaydesk/schemas/kb.py`
- Create: `apps/api/src/relaydesk/api/kb.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Test: `apps/api/tests/test_kb_categories.py` (create)

**Interfaces:**
- Consumes: `KbCategory`, `KbArticle`, `KbScope` (Task 1); `kb_text.slugify` (Task 2).
- Produces:
  - `kb_categories.create(session, workspace_id, name, scope) -> KbCategory`
  - `kb_categories.list_for(session, workspace_id, scope) -> list[tuple[KbCategory, int]]` — category with its article count
  - `kb_categories.update(session, workspace_id, category_id, *, name=None, position=None) -> KbCategory`
  - `kb_categories.delete(session, workspace_id, category_id) -> None`
  - `schemas/kb.py`: `CategoryOut`, `CategoryCreateRequest`, `CategoryPatch`
  - `GET/POST /api/kb/categories`, `PATCH/DELETE /api/kb/categories/{id}`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_kb_categories.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, NotFound
from relaydesk.models.kb import ArticleStatus, KbArticle, KbScope
from relaydesk.services import kb_categories
from relaydesk.services.kb_text import slugify
from tests.factories import make_member, make_workspace, sign_in


async def _article(session, workspace, category, *, title="Refunds"):
    article = KbArticle(
        workspace_id=workspace.id,
        category_id=category.id,
        title=title,
        slug=slugify(title),
        excerpt="",
        doc={"type": "doc", "content": []},
        body_text="",
        status=ArticleStatus.draft,
    )
    session.add(article)
    await session.flush()
    return article


async def test_a_category_gets_a_slug_from_its_name(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    category = await kb_categories.create(
        db_session, workspace.id, "Billing & Refunds", KbScope.external
    )

    assert category.slug == "billing-refunds"
    assert category.scope is KbScope.external


async def test_the_same_name_in_both_scopes_is_allowed(db_session: AsyncSession) -> None:
    """Internal and external are separate namespaces."""
    workspace = await make_workspace(db_session)

    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.internal)
    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)


async def test_a_duplicate_name_in_one_scope_is_a_conflict(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)

    with pytest.raises(Conflict):
        await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)


async def test_new_categories_append_to_the_end(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    first = await kb_categories.create(db_session, workspace.id, "One", KbScope.external)
    second = await kb_categories.create(db_session, workspace.id, "Two", KbScope.external)

    assert (first.position, second.position) == (0, 1)


async def test_listing_returns_categories_in_position_order_with_counts(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    billing = await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)
    await kb_categories.create(db_session, workspace.id, "Returns", KbScope.external)
    await _article(db_session, workspace, billing, title="Refunds")
    await _article(db_session, workspace, billing, title="Chargebacks")

    rows = await kb_categories.list_for(db_session, workspace.id, KbScope.external)

    assert [(c.name, n) for c, n in rows] == [("Billing", 2), ("Returns", 0)]


async def test_listing_is_scoped_to_one_scope(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    await kb_categories.create(db_session, workspace.id, "Internal only", KbScope.internal)

    rows = await kb_categories.list_for(db_session, workspace.id, KbScope.external)

    assert rows == []


async def test_deleting_a_category_that_holds_articles_is_a_conflict(
    db_session: AsyncSession,
) -> None:
    """Cascading here would delete a workspace's documentation silently."""
    workspace = await make_workspace(db_session)
    category = await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)
    await _article(db_session, workspace, category)

    with pytest.raises(Conflict):
        await kb_categories.delete(db_session, workspace.id, category.id)


async def test_an_empty_category_can_be_deleted(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    category = await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)

    await kb_categories.delete(db_session, workspace.id, category.id)

    assert await kb_categories.list_for(db_session, workspace.id, KbScope.external) == []


async def test_another_workspaces_category_is_a_404(db_session: AsyncSession) -> None:
    mine = await make_workspace(db_session, slug="mine")
    theirs = await make_workspace(db_session, slug="theirs")
    category = await kb_categories.create(db_session, mine.id, "Billing", KbScope.external)

    with pytest.raises(NotFound):
        await kb_categories.delete(db_session, theirs.id, category.id)


async def test_the_route_lists_categories(db_session, client) -> None:
    workspace = await make_workspace(db_session)
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)
    await db_session.commit()
    headers = await sign_in(client, db_session, member.email)

    response = await client.get("/api/kb/categories?scope=external", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "billing"
    assert response.json()[0]["articleCount"] == 0


async def test_creating_a_category_requires_admin(db_session, client) -> None:
    from relaydesk.models.membership import Role

    workspace = await make_workspace(db_session)
    agent = await make_member(db_session, workspace, email="sara@example.com", role=Role.agent)
    await db_session.commit()
    headers = await sign_in(client, db_session, agent.email)

    response = await client.post(
        "/api/kb/categories", json={"name": "Billing", "scope": "external"}, headers=headers
    )

    assert response.status_code == 403
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_kb_categories.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.services.kb_categories'`.

- [ ] **Step 3: Write the service**

Create `apps/api/src/relaydesk/services/kb_categories.py`:

```python
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, NotFound
from relaydesk.models.kb import KbArticle, KbCategory, KbScope
from relaydesk.services.kb_text import slugify


async def create(
    session: AsyncSession, workspace_id: uuid.UUID, name: str, scope: KbScope
) -> KbCategory:
    slug = slugify(name)
    existing = await session.scalar(
        sa.select(KbCategory.id).where(
            KbCategory.workspace_id == workspace_id,
            KbCategory.scope == scope,
            KbCategory.slug == slug,
        )
    )
    if existing is not None:
        raise Conflict("A category with that name already exists.")

    highest = await session.scalar(
        sa.select(sa.func.max(KbCategory.position)).where(
            KbCategory.workspace_id == workspace_id, KbCategory.scope == scope
        )
    )
    category = KbCategory(
        workspace_id=workspace_id,
        scope=scope,
        name=name.strip(),
        slug=slug,
        position=0 if highest is None else highest + 1,
    )
    session.add(category)
    await session.flush()
    return category


async def list_for(
    session: AsyncSession, workspace_id: uuid.UUID, scope: KbScope
) -> list[tuple[KbCategory, int]]:
    """Categories in display order, each with how many articles it holds.

    The count is every article regardless of status -- this is the console.
    The public index counts published only, and lives in kb_public.
    """
    counts = (
        sa.select(KbArticle.category_id, sa.func.count().label("n"))
        .where(KbArticle.workspace_id == workspace_id)
        .group_by(KbArticle.category_id)
        .subquery()
    )
    rows = await session.execute(
        sa.select(KbCategory, sa.func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.category_id == KbCategory.id)
        .where(KbCategory.workspace_id == workspace_id, KbCategory.scope == scope)
        .order_by(KbCategory.position, KbCategory.name)
    )
    return [(category, int(n)) for category, n in rows.all()]


async def _get(
    session: AsyncSession, workspace_id: uuid.UUID, category_id: uuid.UUID
) -> KbCategory:
    category = await session.scalar(
        sa.select(KbCategory).where(
            KbCategory.id == category_id, KbCategory.workspace_id == workspace_id
        )
    )
    if category is None:
        raise NotFound("That category does not exist.")
    return category


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    *,
    name: str | None = None,
    position: int | None = None,
) -> KbCategory:
    category = await _get(session, workspace_id, category_id)
    if name is not None:
        # The slug is deliberately not recomputed: it is the public URL, and
        # renaming a category must not break a link someone bookmarked.
        category.name = name.strip()
    if position is not None:
        category.position = position
    await session.flush()
    return category


async def delete(
    session: AsyncSession, workspace_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    category = await _get(session, workspace_id, category_id)
    held = await session.scalar(
        sa.select(sa.func.count())
        .select_from(KbArticle)
        .where(KbArticle.category_id == category.id)
    )
    if held:
        raise Conflict(
            "That category still holds articles. Move or delete them first."
        )
    await session.delete(category)
    await session.flush()
```

- [ ] **Step 4: Write the schemas**

Create `apps/api/src/relaydesk/schemas/kb.py`:

```python
from pydantic import Field

from relaydesk.schemas.base import CamelModel


class CategoryOut(CamelModel):
    id: str
    name: str
    slug: str
    scope: str
    position: int
    article_count: int


class CategoryCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    scope: str


class CategoryPatch(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    position: int | None = None
```

- [ ] **Step 5: Write the router**

Create `apps/api/src/relaydesk/api/kb.py`, following `api/channels.py` — it builds its response models explicitly rather than via `from_attributes`, which this one also needs because `article_count` is computed:

```python
import uuid

from fastapi import APIRouter, Query, Response, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models.kb import KbScope
from relaydesk.schemas.kb import CategoryCreateRequest, CategoryOut, CategoryPatch
from relaydesk.services import kb_categories

router = APIRouter()


def _category_out(category, article_count: int) -> CategoryOut:
    return CategoryOut(
        id=str(category.id),
        name=category.name,
        slug=category.slug,
        scope=category.scope.value,
        position=category.position,
        article_count=article_count,
    )


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    scope: KbScope,
    scope_: Scope,
    session: DbSession,
) -> list[CategoryOut]:
    rows = await kb_categories.list_for(session, scope_.workspace_id, scope)
    return [_category_out(category, n) for category, n in rows]
```

Note the parameter naming collision: this codebase's auth dependency is called `Scope`, and the query parameter is also called `scope`. Name the dependency `scope_` as above, or rename the query parameter — but do **not** leave two things called `scope` in one signature.

Add `POST` (admin, 201), `PATCH`, and `DELETE` (admin, 204) following the same shape, each calling `scope_.require_admin()` as its first statement where marked admin, and committing before returning.

Mount in `api/router.py`: `api_router.include_router(kb_router, prefix="/kb", tags=["knowledge-base"])`.

- [ ] **Step 6: Run the tests**

Run: `docker compose exec api pytest tests/test_kb_categories.py -v`
Expected: PASS (11 passed).

- [ ] **Step 7: Full suite, lint, commit**

Run: `docker compose exec api pytest -q -m "not integration" && docker compose exec api ruff check .`

```bash
git add apps/api
git commit -m "feat(api): add knowledge base categories"
```

---

### Task 4: Articles

**Files:**
- Create: `apps/api/src/relaydesk/services/kb_articles.py`
- Modify: `apps/api/src/relaydesk/schemas/kb.py`
- Modify: `apps/api/src/relaydesk/api/kb.py`
- Test: `apps/api/tests/test_kb_articles.py` (create)

**Interfaces:**
- Consumes: `KbArticle`, `KbCategory`, `ArticleStatus` (Task 1); `kb_text.{extract_text,slugify,derive_excerpt}` (Task 2); `kb_categories` (Task 3).
- Produces:
  - `kb_articles.create(session, workspace_id, category_id, title, author) -> KbArticle`
  - `kb_articles.get(session, workspace_id, article_id) -> KbArticle`
  - `kb_articles.list_for(session, workspace_id, *, scope=None, status=None) -> list[KbArticle]`
  - `kb_articles.update(session, workspace_id, article_id, *, title=None, excerpt=None, doc=None, category_id=None) -> KbArticle`
  - `kb_articles.delete(session, workspace_id, article_id) -> None`
  - `schemas/kb.py`: `ArticleOut`, `ArticleSummary`, `ArticleCreateRequest`, `ArticlePatch`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_kb_articles.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models.kb import ArticleStatus, KbScope
from relaydesk.services import kb_articles, kb_categories
from tests.factories import make_member, make_workspace, sign_in

EMPTY_DOC = {"type": "doc", "content": []}


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


async def _setup(session, *, slug="chronon", scope=KbScope.external):
    workspace = await make_workspace(session, slug=slug)
    author = await make_member(session, workspace, email=f"a@{slug}.test")
    category = await kb_categories.create(session, workspace.id, "Billing", scope)
    return workspace, author, category


async def test_a_new_article_starts_as_a_draft(db_session: AsyncSession) -> None:
    """The console navigates straight to the editor after creating, so the row
    must exist before anyone types -- image upload needs something to attach to."""
    workspace, author, category = await _setup(db_session)

    article = await kb_articles.create(
        db_session, workspace.id, category.id, "Handling a refund", author
    )

    assert article.status is ArticleStatus.draft
    assert article.slug == "handling-a-refund"
    assert article.published_at is None
    assert article.author_user_id == author.id
    assert article.doc == EMPTY_DOC


async def test_a_slug_collision_within_a_category_is_suffixed(
    db_session: AsyncSession,
) -> None:
    """Two articles may legitimately share a title; the URL cannot collide."""
    workspace, author, category = await _setup(db_session)

    first = await kb_articles.create(db_session, workspace.id, category.id, "Refunds", author)
    second = await kb_articles.create(db_session, workspace.id, category.id, "Refunds", author)

    assert first.slug == "refunds"
    assert second.slug == "refunds-2"


async def test_the_same_slug_is_fine_in_another_category(
    db_session: AsyncSession,
) -> None:
    workspace, author, category = await _setup(db_session)
    other = await kb_categories.create(db_session, workspace.id, "Returns", KbScope.external)

    a = await kb_articles.create(db_session, workspace.id, category.id, "Overview", author)
    b = await kb_articles.create(db_session, workspace.id, other.id, "Overview", author)

    assert a.slug == b.slug == "overview"


async def test_updating_the_body_extracts_text_for_search(
    db_session: AsyncSession,
) -> None:
    workspace, author, category = await _setup(db_session)
    article = await kb_articles.create(db_session, workspace.id, category.id, "Refunds", author)

    await kb_articles.update(
        db_session, workspace.id, article.id, doc=_doc("Issued within thirty days.")
    )

    assert article.body_text == "Issued within thirty days."


async def test_an_empty_excerpt_is_derived_from_the_body(
    db_session: AsyncSession,
) -> None:
    """The excerpt is what both the console list and the public index render
    under every title, so it is never left blank."""
    workspace, author, category = await _setup(db_session)
    article = await kb_articles.create(db_session, workspace.id, category.id, "Refunds", author)

    await kb_articles.update(db_session, workspace.id, article.id, doc=_doc("Issued within thirty days."))

    assert article.excerpt == "Issued within thirty days."


async def test_an_authored_excerpt_is_not_overwritten(db_session: AsyncSession) -> None:
    workspace, author, category = await _setup(db_session)
    article = await kb_articles.create(db_session, workspace.id, category.id, "Refunds", author)

    await kb_articles.update(db_session, workspace.id, article.id, excerpt="Read this first.")
    await kb_articles.update(db_session, workspace.id, article.id, doc=_doc("Body text here."))

    assert article.excerpt == "Read this first."


async def test_renaming_an_article_does_not_change_its_slug(
    db_session: AsyncSession,
) -> None:
    """The slug is the published URL. Renaming must not break a bookmark."""
    workspace, author, category = await _setup(db_session)
    article = await kb_articles.create(db_session, workspace.id, category.id, "Refunds", author)

    await kb_articles.update(db_session, workspace.id, article.id, title="Refunds and credits")

    assert article.title == "Refunds and credits"
    assert article.slug == "refunds"


async def test_moving_an_article_to_a_category_in_the_other_scope_is_refused(
    db_session: AsyncSession,
) -> None:
    """Scope lives on the category, so moving across scopes would silently
    change who can read the article."""
    from relaydesk.errors import Invalid

    workspace, author, category = await _setup(db_session)
    internal = await kb_categories.create(db_session, workspace.id, "Runbooks", KbScope.internal)
    article = await kb_articles.create(db_session, workspace.id, category.id, "Refunds", author)

    with pytest.raises(Invalid):
        await kb_articles.update(db_session, workspace.id, article.id, category_id=internal.id)


async def test_another_workspaces_article_is_a_404(db_session: AsyncSession) -> None:
    mine, author, category = await _setup(db_session, slug="mine")
    theirs, _, _ = await _setup(db_session, slug="theirs")
    article = await kb_articles.create(db_session, mine.id, category.id, "Refunds", author)

    with pytest.raises(NotFound):
        await kb_articles.get(db_session, theirs.id, article.id)


async def test_a_category_from_another_workspace_cannot_be_used(
    db_session: AsyncSession,
) -> None:
    mine, author, _ = await _setup(db_session, slug="mine")
    _, _, theirs_category = await _setup(db_session, slug="theirs")

    with pytest.raises(NotFound):
        await kb_articles.create(db_session, mine.id, theirs_category.id, "Refunds", author)


async def test_listing_filters_by_scope(db_session: AsyncSession) -> None:
    workspace, author, external = await _setup(db_session)
    internal = await kb_categories.create(db_session, workspace.id, "Runbooks", KbScope.internal)
    await kb_articles.create(db_session, workspace.id, external.id, "Public one", author)
    await kb_articles.create(db_session, workspace.id, internal.id, "Private one", author)

    rows = await kb_articles.list_for(db_session, workspace.id, scope=KbScope.internal)

    assert [a.title for a in rows] == ["Private one"]


async def test_the_route_creates_and_reads_an_article(db_session, client) -> None:
    workspace, author, category = await _setup(db_session)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    created = await client.post(
        "/api/kb/articles",
        json={"categoryId": str(category.id), "title": "Refunds"},
        headers=headers,
    )
    assert created.status_code == 201
    article_id = created.json()["id"]

    fetched = await client.get(f"/api/kb/articles/{article_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["slug"] == "refunds"
    assert fetched.json()["status"] == "draft"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_kb_articles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.services.kb_articles'`.

- [ ] **Step 3: Write the service**

Create `apps/api/src/relaydesk/services/kb_articles.py`:

```python
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid, NotFound
from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbScope
from relaydesk.models.user import User
from relaydesk.services.kb_text import derive_excerpt, extract_text, slugify

EMPTY_DOC: dict = {"type": "doc", "content": []}


async def _category(
    session: AsyncSession, workspace_id: uuid.UUID, category_id: uuid.UUID
) -> KbCategory:
    category = await session.scalar(
        sa.select(KbCategory).where(
            KbCategory.id == category_id, KbCategory.workspace_id == workspace_id
        )
    )
    if category is None:
        raise NotFound("That category does not exist.")
    return category


async def _unique_slug(
    session: AsyncSession, category_id: uuid.UUID, title: str
) -> str:
    """Two articles may share a title; their URLs cannot."""
    base = slugify(title)
    taken = set(
        (
            await session.scalars(
                sa.select(KbArticle.slug).where(KbArticle.category_id == category_id)
            )
        ).all()
    )
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


async def create(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    title: str,
    author: User | None,
) -> KbArticle:
    category = await _category(session, workspace_id, category_id)
    article = KbArticle(
        workspace_id=workspace_id,
        category_id=category.id,
        title=title.strip(),
        slug=await _unique_slug(session, category.id, title),
        excerpt="",
        doc=EMPTY_DOC,
        body_text="",
        status=ArticleStatus.draft,
        author_user_id=author.id if author else None,
    )
    session.add(article)
    await session.flush()
    return article


async def get(
    session: AsyncSession, workspace_id: uuid.UUID, article_id: uuid.UUID
) -> KbArticle:
    article = await session.scalar(
        sa.select(KbArticle).where(
            KbArticle.id == article_id, KbArticle.workspace_id == workspace_id
        )
    )
    if article is None:
        raise NotFound("That article does not exist.")
    return article


async def list_for(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    scope: KbScope | None = None,
    status: ArticleStatus | None = None,
) -> list[KbArticle]:
    query = (
        sa.select(KbArticle)
        .join(KbCategory, KbCategory.id == KbArticle.category_id)
        .where(KbArticle.workspace_id == workspace_id)
        .order_by(KbCategory.position, KbArticle.title)
    )
    if scope is not None:
        query = query.where(KbCategory.scope == scope)
    if status is not None:
        query = query.where(KbArticle.status == status)
    return list((await session.scalars(query)).all())


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    article_id: uuid.UUID,
    *,
    title: str | None = None,
    excerpt: str | None = None,
    doc: dict | None = None,
    category_id: uuid.UUID | None = None,
) -> KbArticle:
    article = await get(session, workspace_id, article_id)
    current = await _category(session, workspace_id, article.category_id)

    if category_id is not None and category_id != article.category_id:
        target = await _category(session, workspace_id, category_id)
        if target.scope is not current.scope:
            # Scope lives on the category, so this would silently change who
            # can read the article.
            raise Invalid("An article cannot move between internal and external.")
        article.category_id = target.id
        article.slug = await _unique_slug(session, target.id, article.title)

    if title is not None:
        # The slug is deliberately not recomputed -- it is the published URL.
        article.title = title.strip()
    if excerpt is not None:
        article.excerpt = excerpt.strip()[:400]
    if doc is not None:
        article.doc = doc
        article.body_text = extract_text(doc)
        if not article.excerpt:
            article.excerpt = derive_excerpt(article.body_text)

    await session.flush()
    return article


async def delete(
    session: AsyncSession, workspace_id: uuid.UUID, article_id: uuid.UUID
) -> None:
    article = await get(session, workspace_id, article_id)
    await session.delete(article)
    await session.flush()
```

- [ ] **Step 4: Add the schemas and routes**

In `schemas/kb.py`:

```python
class ArticleSummary(CamelModel):
    id: str
    title: str
    slug: str
    excerpt: str
    status: str
    category_id: str
    updated_at: datetime


class ArticleOut(ArticleSummary):
    doc: dict
    published_at: datetime | None


class ArticleCreateRequest(CamelModel):
    category_id: str
    title: str = Field(min_length=1, max_length=200)


class ArticlePatch(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    excerpt: str | None = Field(default=None, max_length=400)
    doc: dict | None = None
    category_id: str | None = None
```

In `api/kb.py` add `GET /articles` (with optional `scope` and `status` query parameters, each needing an explicit `Query(alias=...)` if the wire name differs), `POST /articles` (201), `GET /articles/{id}`, `PATCH /articles/{id}`, and `DELETE /articles/{id}` (204). Authoring is not admin-gated — any member may write.

- [ ] **Step 5: Run the tests, lint, commit**

Run: `docker compose exec api pytest tests/test_kb_articles.py -v`
Expected: PASS (12 passed).

Run: `docker compose exec api pytest -q -m "not integration" && docker compose exec api ruff check .`

```bash
git add apps/api
git commit -m "feat(api): add knowledge base articles"
```

---

### Task 5: The status machine

**Files:**
- Modify: `apps/api/src/relaydesk/services/kb_articles.py`
- Modify: `apps/api/src/relaydesk/schemas/kb.py`
- Modify: `apps/api/src/relaydesk/api/kb.py`
- Test: `apps/api/tests/test_kb_status.py` (create)

**Interfaces:**
- Consumes: `kb_articles.get` (Task 4).
- Produces: `kb_articles.set_status(session, workspace_id, article_id, target) -> KbArticle`; `POST /api/kb/articles/{id}/status`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_kb_status.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models.kb import ArticleStatus, KbScope
from relaydesk.services import kb_articles, kb_categories
from tests.factories import make_member, make_workspace, sign_in


async def _article(session, *, status=ArticleStatus.draft):
    workspace = await make_workspace(session)
    author = await make_member(session, workspace, email="a@example.com")
    category = await kb_categories.create(session, workspace.id, "Billing", KbScope.external)
    article = await kb_articles.create(session, workspace.id, category.id, "Refunds", author)
    if status is not ArticleStatus.draft:
        article.status = status
        await session.flush()
    return workspace, author, article


async def test_draft_can_become_ready(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session)

    updated = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.ready
    )

    assert updated.status is ArticleStatus.ready
    assert updated.published_at is None


async def test_publishing_stamps_published_at(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session, status=ArticleStatus.ready)

    updated = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.published
    )

    assert updated.status is ArticleStatus.published
    assert updated.published_at is not None


async def test_draft_cannot_skip_straight_to_published(db_session: AsyncSession) -> None:
    """The review step is the whole point of having three states."""
    workspace, _, article = await _article(db_session)

    with pytest.raises(Invalid):
        await kb_articles.set_status(
            db_session, workspace.id, article.id, ArticleStatus.published
        )


async def test_published_can_be_unpublished_to_draft(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session, status=ArticleStatus.published)

    updated = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.draft
    )

    assert updated.status is ArticleStatus.draft


async def test_unpublishing_keeps_the_original_publication_date(
    db_session: AsyncSession,
) -> None:
    """published_at records when it first went live, not whether it is live
    now -- status already answers that."""
    workspace, _, article = await _article(db_session, status=ArticleStatus.ready)
    published = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.published
    )
    stamped = published.published_at

    unpublished = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.draft
    )

    assert unpublished.published_at == stamped


async def test_ready_can_go_back_to_draft(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session, status=ArticleStatus.ready)

    updated = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.draft
    )

    assert updated.status is ArticleStatus.draft


async def test_published_cannot_go_back_to_ready(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session, status=ArticleStatus.published)

    with pytest.raises(Invalid):
        await kb_articles.set_status(
            db_session, workspace.id, article.id, ArticleStatus.ready
        )


async def test_an_illegal_transition_over_http_is_a_422(db_session, client) -> None:
    workspace, author, article = await _article(db_session)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    response = await client.post(
        f"/api/kb/articles/{article.id}/status",
        json={"status": "published"},
        headers=headers,
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_kb_status.py -v`
Expected: FAIL — `kb_articles` has no attribute `set_status`.

- [ ] **Step 3: Implement the machine**

Add to `services/kb_articles.py`:

```python
# draft -> ready -> published, plus the two ways back. Publishing skips no
# step: the review state is the only thing standing between a half-written
# article and a workspace's public site.
ALLOWED_TRANSITIONS: dict[ArticleStatus, frozenset[ArticleStatus]] = {
    ArticleStatus.draft: frozenset({ArticleStatus.ready}),
    ArticleStatus.ready: frozenset({ArticleStatus.draft, ArticleStatus.published}),
    ArticleStatus.published: frozenset({ArticleStatus.draft}),
}


async def set_status(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    article_id: uuid.UUID,
    target: ArticleStatus,
) -> KbArticle:
    article = await get(session, workspace_id, article_id)
    if target not in ALLOWED_TRANSITIONS[article.status]:
        raise Invalid(
            f"An article cannot go from {article.status.value} to {target.value}."
        )

    article.status = target
    if target is ArticleStatus.published and article.published_at is None:
        # Records when it first went live. Unpublishing leaves it, because
        # status already says whether it is live now.
        article.published_at = datetime.now(UTC)

    await session.flush()
    return article
```

Add `from datetime import UTC, datetime` to the imports.

In `schemas/kb.py`:

```python
class StatusRequest(CamelModel):
    status: str
```

In `api/kb.py`, add `POST /articles/{id}/status`. `Invalid` maps to 422 through the existing error handler, so the router needs no special casing.

- [ ] **Step 4: Run the tests, lint, commit**

Run: `docker compose exec api pytest tests/test_kb_status.py -v`
Expected: PASS (8 passed).

Run: `docker compose exec api pytest -q -m "not integration" && docker compose exec api ruff check .`

```bash
git add apps/api
git commit -m "feat(api): add the article review workflow"
```

---

### Task 6: Search

**Files:**
- Modify: `apps/api/src/relaydesk/services/kb_articles.py`
- Modify: `apps/api/src/relaydesk/api/kb.py`
- Test: `apps/api/tests/test_kb_search.py` (create)

**Interfaces:**
- Consumes: `KbArticle.search_vector` (Task 1); `kb_articles.list_for` (Task 4).
- Produces: `kb_articles.search(session, workspace_id, query, *, scope=None, published_only=False) -> list[KbArticle]`; `q` on `GET /api/kb/articles`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_kb_search.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.kb import ArticleStatus, KbScope
from relaydesk.services import kb_articles, kb_categories
from tests.factories import make_member, make_workspace


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


async def _write(session, workspace, category, author, title, body, *, status=ArticleStatus.draft):
    article = await kb_articles.create(session, workspace.id, category.id, title, author)
    await kb_articles.update(session, workspace.id, article.id, doc=_doc(body))
    if status is not ArticleStatus.draft:
        article.status = status
        await session.flush()
    return article


async def _setup(session, slug="chronon"):
    workspace = await make_workspace(session, slug=slug)
    author = await make_member(session, workspace, email=f"a@{slug}.test")
    category = await kb_categories.create(session, workspace.id, "Billing", KbScope.external)
    return workspace, author, category


async def test_search_matches_the_body(db_session: AsyncSession) -> None:
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Refunds", "Issued within thirty days.")

    hits = await kb_articles.search(db_session, workspace.id, "thirty")

    assert [a.title for a in hits] == ["Refunds"]


async def test_search_matches_the_title(db_session: AsyncSession) -> None:
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Chargebacks", "Nothing relevant here.")

    hits = await kb_articles.search(db_session, workspace.id, "chargebacks")

    assert [a.title for a in hits] == ["Chargebacks"]


async def test_search_stems_english_words(db_session: AsyncSession) -> None:
    """to_tsvector('english') is what makes 'refund' find 'refunded'."""
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Policy", "The charge was refunded.")

    assert len(await kb_articles.search(db_session, workspace.id, "refund")) == 1


async def test_search_never_crosses_a_workspace(db_session: AsyncSession) -> None:
    mine, mine_author, mine_category = await _setup(db_session, slug="mine")
    theirs, theirs_author, theirs_category = await _setup(db_session, slug="theirs")
    await _write(db_session, theirs, theirs_category, theirs_author, "Secret", "thirty days")

    assert await kb_articles.search(db_session, mine.id, "thirty") == []


async def test_published_only_excludes_drafts(db_session: AsyncSession) -> None:
    """This is the mode the public hub uses; a draft leaking into it would
    publish something nobody approved."""
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Draft one", "thirty days")
    await _write(
        db_session, workspace, category, author, "Live one", "thirty days",
        status=ArticleStatus.published,
    )

    hits = await kb_articles.search(db_session, workspace.id, "thirty", published_only=True)

    assert [a.title for a in hits] == ["Live one"]


async def test_search_can_be_scoped(db_session: AsyncSession) -> None:
    workspace, author, external = await _setup(db_session)
    internal = await kb_categories.create(db_session, workspace.id, "Runbooks", KbScope.internal)
    await _write(db_session, workspace, external, author, "Public", "thirty days")
    await _write(db_session, workspace, internal, author, "Private", "thirty days")

    hits = await kb_articles.search(db_session, workspace.id, "thirty", scope=KbScope.internal)

    assert [a.title for a in hits] == ["Private"]


async def test_an_empty_query_returns_nothing(db_session: AsyncSession) -> None:
    """Rather than every article, which is what a bare tsquery would do."""
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Refunds", "thirty days")

    assert await kb_articles.search(db_session, workspace.id, "   ") == []


async def test_punctuation_in_a_query_does_not_raise(db_session: AsyncSession) -> None:
    """This is user input from a public search box. `to_tsquery` would raise on
    most of these; websearch_to_tsquery is what makes them safe."""
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Refunds", "thirty days")

    for query in ["&&&", "a | b", '"unclosed', "!!!", "thirty OR days", "-thirty"]:
        await kb_articles.search(db_session, workspace.id, query)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_kb_search.py -v`
Expected: FAIL — `kb_articles` has no attribute `search`.

- [ ] **Step 3: Implement search**

Add to `services/kb_articles.py`:

```python
async def search(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    query: str,
    *,
    scope: KbScope | None = None,
    published_only: bool = False,
) -> list[KbArticle]:
    """Full-text over title and body, ranked.

    `websearch_to_tsquery` rather than `to_tsquery`: this takes input straight
    from a search box, and `to_tsquery` raises a syntax error on ordinary
    punctuation. The websearch parser accepts quoted phrases, OR, and leading
    minus, and simply ignores anything it cannot parse.
    """
    terms = query.strip()
    if not terms:
        return []

    tsquery = sa.func.websearch_to_tsquery("english", terms)
    statement = (
        sa.select(KbArticle)
        .join(KbCategory, KbCategory.id == KbArticle.category_id)
        .where(
            KbArticle.workspace_id == workspace_id,
            KbArticle.search_vector.op("@@")(tsquery),
        )
        .order_by(sa.func.ts_rank(KbArticle.search_vector, tsquery).desc())
        .limit(50)
    )
    if scope is not None:
        statement = statement.where(KbCategory.scope == scope)
    if published_only:
        statement = statement.where(KbArticle.status == ArticleStatus.published)

    return list((await session.scalars(statement)).all())
```

- [ ] **Step 4: Wire `q` into the list route**

In `api/kb.py`'s `GET /articles`, when `q` is present, return `kb_articles.search(...)` instead of `list_for(...)`, passing through the same `scope` filter.

- [ ] **Step 5: Run the tests, lint, commit**

Run: `docker compose exec api pytest tests/test_kb_search.py -v`
Expected: PASS (8 passed).

Run: `docker compose exec api pytest -q -m "not integration" && docker compose exec api ruff check .`

```bash
git add apps/api
git commit -m "feat(api): add knowledge base search"
```

---

### Task 7: Images

**Files:**
- Create: `apps/api/src/relaydesk/services/kb_images.py`
- Modify: `apps/api/src/relaydesk/config.py`
- Modify: `apps/api/src/relaydesk/api/kb.py`
- Modify: `.env.example`
- Test: `apps/api/tests/test_kb_images.py` (create)

**Interfaces:**
- Consumes: `blobs.{write,read}` (Task 1); `attachments.INLINE_SAFE_TYPES` (slice 2); `kb_articles.get` (Task 4).
- Produces:
  - `kb_images.store(session, article, filename, content_type, content) -> KbImage`
  - `kb_images.read(session, workspace_id, image_id) -> tuple[KbImage, bytes]`
  - `Settings.kb_image_max_bytes` (default `5242880`)
  - `POST /api/kb/articles/{id}/images`, `GET /api/kb/images/{id}`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_kb_images.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Invalid, NotFound
from relaydesk.models.kb import KbScope
from relaydesk.services import kb_articles, kb_categories, kb_images
from tests.factories import make_member, make_workspace, sign_in

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "attachment_dir", str(tmp_path))
    return tmp_path


async def _article(session, *, slug="chronon"):
    workspace = await make_workspace(session, slug=slug)
    author = await make_member(session, workspace, email=f"a@{slug}.test")
    category = await kb_categories.create(session, workspace.id, "Billing", KbScope.external)
    article = await kb_articles.create(session, workspace.id, category.id, "Refunds", author)
    return workspace, author, article


async def test_an_image_is_stored_content_addressed(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session)

    image = await kb_images.store(db_session, article, "screenshot.png", "image/png", PNG)

    assert image.article_id == article.id
    assert image.workspace_id == workspace.id
    assert image.storage_key.endswith(image.sha256)
    assert image.size_bytes == len(PNG)


async def test_reading_returns_the_bytes(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session)
    image = await kb_images.store(db_session, article, "screenshot.png", "image/png", PNG)

    row, content = await kb_images.read(db_session, workspace.id, image.id)

    assert content == PNG
    assert row.filename == "screenshot.png"


async def test_another_workspaces_image_is_a_404(db_session: AsyncSession) -> None:
    mine, _, article = await _article(db_session, slug="mine")
    theirs, _, _ = await _article(db_session, slug="theirs")
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    with pytest.raises(NotFound):
        await kb_images.read(db_session, theirs.id, image.id)


async def test_a_non_image_upload_is_refused(db_session: AsyncSession) -> None:
    """This route exists to put pictures in articles. Anything else would be
    an unauthenticated file host once the article is published."""
    _, _, article = await _article(db_session)

    with pytest.raises(Invalid):
        await kb_images.store(db_session, article, "payload.html", "text/html", b"<script>")


async def test_svg_is_refused(db_session: AsyncSession) -> None:
    """SVG executes script when rendered inline, and an article image is
    rendered inline by definition."""
    _, _, article = await _article(db_session)

    with pytest.raises(Invalid):
        await kb_images.store(db_session, article, "logo.svg", "image/svg+xml", b"<svg/>")


async def test_an_oversized_image_is_refused(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "kb_image_max_bytes", 16)
    _, _, article = await _article(db_session)

    with pytest.raises(Invalid):
        await kb_images.store(db_session, article, "big.png", "image/png", b"x" * 32)


async def test_deleting_an_article_removes_its_image_rows(
    db_session: AsyncSession,
) -> None:
    workspace, _, article = await _article(db_session)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)
    await db_session.flush()

    await kb_articles.delete(db_session, workspace.id, article.id)

    with pytest.raises(NotFound):
        await kb_images.read(db_session, workspace.id, image.id)


async def test_the_upload_route_returns_an_id_and_url(db_session, client) -> None:
    workspace, author, article = await _article(db_session)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    response = await client.post(
        f"/api/kb/articles/{article.id}/images",
        files={"file": ("screenshot.png", PNG, "image/png")},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["url"].startswith("/api/kb/images/")


async def test_the_download_route_serves_an_image_inline(db_session, client) -> None:
    workspace, author, article = await _article(db_session)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    response = await client.get(f"/api/kb/images/{image.id}", headers=headers)

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_kb_images.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.services.kb_images'`.

- [ ] **Step 3: Add the setting**

In `config.py`, beside `attachment_max_bytes`:

```python
    kb_image_max_bytes: int = 5242880
```

and in `.env.example`: `KB_IMAGE_MAX_BYTES=5242880`.

- [ ] **Step 4: Write the service**

Create `apps/api/src/relaydesk/services/kb_images.py`:

```python
"""Images embedded in knowledge base articles.

Unlike message attachments, these are rendered inline -- that is what an
image in an article is for -- so the upload allowlist is narrower than the
attachment one: only types that are safe to render, which excludes SVG
because it executes script.
"""

import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Invalid, NotFound
from relaydesk.models.kb import KbArticle, KbImage
from relaydesk.services import blobs
from relaydesk.services.attachments import INLINE_SAFE_TYPES


def storage_root() -> Path:
    """Public because kb_public reads images through the same root."""
    return Path(get_settings().attachment_dir)


async def store(
    session: AsyncSession,
    article: KbArticle,
    filename: str,
    content_type: str,
    content: bytes,
) -> KbImage:
    if content_type.lower() not in INLINE_SAFE_TYPES:
        raise Invalid("Only PNG, JPEG, GIF, and WebP images can be added to an article.")

    cap = get_settings().kb_image_max_bytes
    if len(content) > cap:
        raise Invalid(f"That image is larger than the {cap // 1024 // 1024} MB limit.")

    digest, key = blobs.write(storage_root(), article.workspace_id, content)
    image = KbImage(
        workspace_id=article.workspace_id,
        article_id=article.id,
        filename=filename[:255],
        content_type=content_type.lower(),
        size_bytes=len(content),
        sha256=digest,
        storage_key=key,
    )
    session.add(image)
    await session.flush()
    return image


async def read(
    session: AsyncSession, workspace_id: uuid.UUID, image_id: uuid.UUID
) -> tuple[KbImage, bytes]:
    row = await session.scalar(
        sa.select(KbImage).where(
            KbImage.id == image_id, KbImage.workspace_id == workspace_id
        )
    )
    if row is None:
        raise NotFound("That image does not exist.")
    return row, blobs.read(storage_root(), workspace_id, row.sha256)
```

- [ ] **Step 5: Add the routes**

In `api/kb.py`:

```python
@router.post("/articles/{article_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_image(
    article_id: uuid.UUID,
    scope_: Scope,
    session: DbSession,
    file: UploadFile,
) -> ImageOut:
    article = await kb_articles.get(session, scope_.workspace_id, article_id)
    image = await kb_images.store(
        session, article, file.filename or "image", file.content_type or "", await file.read()
    )
    await session.commit()
    return ImageOut(id=str(image.id), url=f"/api/kb/images/{image.id}")


@router.get("/images/{image_id}")
async def download_image(
    image_id: uuid.UUID, scope_: Scope, session: DbSession
) -> Response:
    row, content = await kb_images.read(session, scope_.workspace_id, image_id)
    return Response(
        content=content,
        media_type=row.content_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )
```

`row.content_type` is safe to return directly because `store` only ever writes a type from `INLINE_SAFE_TYPES` — the allowlist is enforced on the way in rather than on the way out. Add `ImageOut(CamelModel)` with `id: str` and `url: str` to `schemas/kb.py`.

- [ ] **Step 6: Run the tests, lint, commit**

Run: `docker compose exec api pytest tests/test_kb_images.py -v`
Expected: PASS (9 passed).

Run: `docker compose exec api pytest -q -m "not integration" && docker compose exec api ruff check .`

```bash
git add apps/api .env.example
git commit -m "feat(api): add article images"
```

---

### Task 8: Subdomain resolution

The portal has never identified a workspace — `app/(portal)/layout.tsx` reads mock settings and its comment says "in production this is served on the tenant's own subdomain," which nothing implements. This task builds that, and the submit-ticket form inherits it when it is built.

**Files:**
- Modify: `apps/api/src/relaydesk/config.py`
- Modify: `apps/api/src/relaydesk/services/workspaces.py`
- Create: `apps/api/src/relaydesk/api/public.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Modify: `apps/web/middleware.ts`
- Modify: `apps/web/app/(portal)/layout.tsx`
- Create: `apps/web/lib/api/public.ts`
- Modify: `.env.example`, `docker-compose.yml`
- Test: `apps/api/tests/test_public_workspace.py` (create)

**Interfaces:**
- Consumes: `Workspace`, `create_workspace` (slice 2).
- Produces:
  - `Settings.portal_domain` (default `localhost:3000`)
  - `workspaces.RESERVED_SLUGS: frozenset[str]`
  - `GET /api/public/workspaces/{slug}` → `{ name, monogram }`, unauthenticated
  - `x-relaydesk-workspace` request header, set by middleware, read by the portal layout

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_public_workspace.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.services import workspaces
from tests.factories import make_workspace


async def test_the_public_endpoint_returns_display_information(
    db_session, client
) -> None:
    await make_workspace(db_session, slug="acme")
    await db_session.commit()

    response = await client.get("/api/public/workspaces/acme")

    assert response.status_code == 200
    assert set(response.json()) == {"name", "monogram"}


async def test_the_public_endpoint_needs_no_session(db_session, client) -> None:
    """The whole point is that acme.<portal domain> is reachable by anyone."""
    await make_workspace(db_session, slug="acme")
    await db_session.commit()

    response = await client.get("/api/public/workspaces/acme")

    assert response.status_code == 200


async def test_an_unknown_slug_is_a_404(db_session, client) -> None:
    response = await client.get("/api/public/workspaces/nobody")

    assert response.status_code == 404


async def test_the_endpoint_leaks_nothing_beyond_display_fields(
    db_session, client
) -> None:
    """It is public, so it must not carry plan, seat counts, ticket volume, or
    anything else a competitor could scrape."""
    await make_workspace(db_session, slug="acme")
    await db_session.commit()

    body = await client.get("/api/public/workspaces/acme")

    for leaked in ("plan", "conversationSeq", "ticketsThisPeriod", "timezone", "id"):
        assert leaked not in body.json()


@pytest.mark.parametrize("slug", ["www", "app", "api", "admin", "mail", "inbound"])
async def test_a_reserved_label_cannot_be_registered_as_a_slug(
    db_session: AsyncSession, slug: str
) -> None:
    """Otherwise registering `api` takes over a hostname the deployment needs."""
    with pytest.raises(Invalid):
        await workspaces.create_workspace(
            db_session, name="Nope", slug=slug, monogram="NO"
        )


async def test_a_reserved_label_is_a_404_on_the_public_endpoint(
    db_session, client
) -> None:
    response = await client.get("/api/public/workspaces/api")

    assert response.status_code == 404
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_public_workspace.py -v`
Expected: FAIL — no `/api/public` routes mounted.

- [ ] **Step 3: Add the setting and reserved labels**

In `config.py`: `portal_domain: str = "localhost:3000"`. In `.env.example`: `PORTAL_DOMAIN=localhost:3000`. Add it to the `web` service's environment in `docker-compose.yml` as `NEXT_PUBLIC_PORTAL_DOMAIN` too — the middleware needs it client-side of the API boundary.

In `services/workspaces.py`:

```python
# A workspace is reachable at <slug>.<portal domain>, so a slug that collides
# with a hostname the deployment needs would take it over.
RESERVED_SLUGS = frozenset({"www", "app", "api", "admin", "mail", "inbound"})
```

and in `create_workspace`, before creating:

```python
    if slug.lower() in RESERVED_SLUGS:
        raise Invalid("That workspace address is reserved.")
```

- [ ] **Step 4: Write the public router**

Create `apps/api/src/relaydesk/api/public.py`:

```python
"""Anonymous, read-only routes for the customer-facing portal.

Everything here is reachable without a session by design -- a published
knowledge base is public. That makes the rule for this module simple and
absolute: return display information and published content, never anything
about tickets, members, plans, or usage.
"""

import sqlalchemy as sa
from fastapi import APIRouter

from relaydesk.api.deps import DbSession
from relaydesk.errors import NotFound
from relaydesk.models.workspace import Workspace
from relaydesk.schemas.kb import PublicWorkspaceOut
from relaydesk.services.workspaces import RESERVED_SLUGS

router = APIRouter()


async def resolve_workspace(session: DbSession, slug: str) -> Workspace:
    """Shared by every public route. A reserved label is a 404, not a lookup."""
    if slug.lower() in RESERVED_SLUGS:
        raise NotFound("No such workspace.")
    workspace = await session.scalar(
        sa.select(Workspace).where(Workspace.slug == slug.lower())
    )
    if workspace is None:
        raise NotFound("No such workspace.")
    return workspace


@router.get("/workspaces/{slug}", response_model=PublicWorkspaceOut)
async def read_workspace(slug: str, session: DbSession) -> PublicWorkspaceOut:
    workspace = await resolve_workspace(session, slug)
    return PublicWorkspaceOut(name=workspace.name, monogram=workspace.monogram)
```

Add `PublicWorkspaceOut(CamelModel)` with `name: str` and `monogram: str` to `schemas/kb.py`. Mount in `api/router.py` at `prefix="/public"`.

- [ ] **Step 5: Set the workspace header in middleware**

In `apps/web/middleware.ts`, before the existing console-auth logic, add subdomain resolution. The mechanism is a request header rather than a URL rewrite, so the portal's routes keep their natural paths:

```typescript
const PORTAL_DOMAIN = process.env.NEXT_PUBLIC_PORTAL_DOMAIN ?? "localhost:3000";
const RESERVED = new Set(["www", "app", "api", "admin", "mail", "inbound"]);

/**
 * A workspace is reached at <slug>.<portal domain>. The slug travels to the
 * portal layout as a request header rather than a rewritten path, so
 * /help/billing/refunds stays exactly that in the address bar and in the
 * route tree.
 */
function workspaceSlug(host: string | null): string | null {
  if (!host) return null;
  const bare = host.split(":")[0];
  const root = PORTAL_DOMAIN.split(":")[0];
  if (bare === root || !bare.endsWith(`.${root}`)) return null;
  const label = bare.slice(0, -(root.length + 1));
  if (!label || label.includes(".") || RESERVED.has(label)) return null;
  return label;
}
```

In the middleware body, when `workspaceSlug` returns a value, forward it:

```typescript
  const slug = workspaceSlug(request.headers.get("host"));
  if (slug) {
    const headers = new Headers(request.headers);
    headers.set("x-relaydesk-workspace", slug);
    return NextResponse.next({ request: { headers } });
  }
```

Leave the existing console-auth branch untouched below it — a portal request never reaches it, and a console request never has a workspace label.

- [ ] **Step 6: Resolve a real workspace in the portal layout**

Create `apps/web/lib/api/public.ts` following `lib/api/labels.ts`, including the `cache()` wrapper:

```typescript
export const getPublicWorkspace = cache(async (slug: string): Promise<PublicWorkspace> => {
  return apiFetch<PublicWorkspace>(`/public/workspaces/${slug}`, { auth: false });
});
```

Check `lib/api/client.ts`'s `Options` type for how to make an unauthenticated call — it has an `auth?: boolean` flag; if the flag does not do what is needed, add the smallest change that lets a public call skip the bearer header, and say so in your report.

In `app/(portal)/layout.tsx`, replace `getPortalSettings()` from the mock with:

```typescript
const slug = (await headers()).get("x-relaydesk-workspace");
if (!slug) notFound();
const workspace = await getPublicWorkspace(slug);
```

An unknown or reserved label therefore renders Next's 404 rather than a redirect to the console or an error naming other tenants.

- [ ] **Step 7: Verify against the running stack**

Run: `docker compose exec api pytest tests/test_public_workspace.py -v`
Expected: PASS (7 passed).

Then check the header path end to end:

```sh
curl -s -H "Host: chronon.localhost:3000" http://localhost:3000/submit-ticket | grep -o "Chronon" | head -1
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: nobody.localhost:3000" http://localhost:3000/submit-ticket
```

Expected: the workspace's real name in the first, `404` in the second.

- [ ] **Step 8: Lint, build, commit**

Run: `docker compose exec api ruff check . && docker compose exec web pnpm lint && docker compose exec web pnpm build`

```bash
git add apps/api apps/web .env.example docker-compose.yml
git commit -m "feat: resolve the portal's workspace from its subdomain"
```

---

### Task 9: The public knowledge base API

**Files:**
- Create: `apps/api/src/relaydesk/services/kb_public.py`
- Modify: `apps/api/src/relaydesk/api/public.py`
- Modify: `apps/api/src/relaydesk/schemas/kb.py`
- Test: `apps/api/tests/test_kb_public.py` (create)

**Interfaces:**
- Consumes: `resolve_workspace` (Task 8); `kb_articles.search` (Task 6); `kb_images.read` (Task 7).
- Produces:
  - `kb_public.index(session, workspace_id) -> list[tuple[KbCategory, list[KbArticle]]]`
  - `kb_public.article(session, workspace_id, category_slug, article_slug) -> KbArticle`
  - `kb_public.search(session, workspace_id, query) -> list[KbArticle]`
  - `kb_public.image(session, workspace_id, image_id) -> tuple[KbImage, bytes]`
  - `GET /api/public/{slug}/kb`, `/kb/{category}/{article}`, `/kb/search`, `/kb/images/{id}`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_kb_public.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models.kb import ArticleStatus, KbScope
from relaydesk.services import kb_articles, kb_categories, kb_images, kb_public
from tests.factories import make_member, make_workspace

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


async def _published(session, *, slug="acme", scope=KbScope.external, status=ArticleStatus.published):
    workspace = await make_workspace(session, slug=slug)
    author = await make_member(session, workspace, email=f"a@{slug}.test")
    category = await kb_categories.create(session, workspace.id, "Billing", scope)
    article = await kb_articles.create(session, workspace.id, category.id, "Refunds", author)
    await kb_articles.update(session, workspace.id, article.id, doc=_doc("Within thirty days."))
    article.status = status
    await session.flush()
    return workspace, category, article


async def test_the_index_lists_published_external_articles(
    db_session: AsyncSession,
) -> None:
    workspace, _, _ = await _published(db_session)

    rows = await kb_public.index(db_session, workspace.id)

    assert [(c.name, [a.title for a in arts]) for c, arts in rows] == [
        ("Billing", ["Refunds"])
    ]


async def test_a_draft_never_appears_publicly(db_session: AsyncSession) -> None:
    workspace, _, _ = await _published(db_session, status=ArticleStatus.draft)

    assert await kb_public.index(db_session, workspace.id) == []


async def test_a_ready_article_is_not_public_either(db_session: AsyncSession) -> None:
    """Ready means reviewed, not live. Publishing is a separate decision."""
    workspace, _, _ = await _published(db_session, status=ArticleStatus.ready)

    assert await kb_public.index(db_session, workspace.id) == []


async def test_internal_articles_are_never_public(db_session: AsyncSession) -> None:
    """These are the agent's runbooks. Publishing one would expose internal
    procedure to customers."""
    workspace, _, _ = await _published(db_session, scope=KbScope.internal)

    assert await kb_public.index(db_session, workspace.id) == []


async def test_an_empty_category_is_omitted_from_the_index(
    db_session: AsyncSession,
) -> None:
    workspace, _, _ = await _published(db_session)
    await kb_categories.create(db_session, workspace.id, "Returns", KbScope.external)

    rows = await kb_public.index(db_session, workspace.id)

    assert [c.name for c, _ in rows] == ["Billing"]


async def test_an_article_is_readable_by_its_slugs(db_session: AsyncSession) -> None:
    workspace, category, article = await _published(db_session)

    found = await kb_public.article(db_session, workspace.id, category.slug, article.slug)

    assert found.id == article.id


async def test_an_unpublished_article_is_a_404_not_a_403(
    db_session: AsyncSession,
) -> None:
    """403 would confirm that an article exists at a guessable slug."""
    workspace, category, article = await _published(db_session, status=ArticleStatus.draft)

    with pytest.raises(NotFound):
        await kb_public.article(db_session, workspace.id, category.slug, article.slug)


async def test_another_workspaces_article_is_not_readable(
    db_session: AsyncSession,
) -> None:
    theirs, category, article = await _published(db_session, slug="theirs")
    mine = await make_workspace(db_session, slug="mine")

    with pytest.raises(NotFound):
        await kb_public.article(db_session, mine.id, category.slug, article.slug)


async def test_public_search_excludes_unpublished(db_session: AsyncSession) -> None:
    workspace, _, article = await _published(db_session, status=ArticleStatus.draft)

    assert await kb_public.search(db_session, workspace.id, "thirty") == []


async def test_an_image_on_a_published_article_is_readable(
    db_session: AsyncSession,
) -> None:
    workspace, _, article = await _published(db_session)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    row, content = await kb_public.image(db_session, workspace.id, image.id)

    assert content == PNG


async def test_an_image_on_a_draft_article_is_a_404(db_session: AsyncSession) -> None:
    """Otherwise an unpublished article's screenshots are readable by anyone
    who guesses an id -- the article is hidden but its pictures are not."""
    workspace, _, article = await _published(db_session, status=ArticleStatus.draft)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    with pytest.raises(NotFound):
        await kb_public.image(db_session, workspace.id, image.id)


async def test_an_image_on_an_internal_article_is_a_404(
    db_session: AsyncSession,
) -> None:
    workspace, _, article = await _published(db_session, scope=KbScope.internal)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    with pytest.raises(NotFound):
        await kb_public.image(db_session, workspace.id, image.id)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec api pytest tests/test_kb_public.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relaydesk.services.kb_public'`.

- [ ] **Step 3: Write the service**

Create `apps/api/src/relaydesk/services/kb_public.py`:

```python
"""The public read surface. Published external articles and nothing else.

Every function here takes a workspace_id resolved from the request's
subdomain and applies the same two predicates -- external scope, published
status -- because this is the code path anonymous visitors reach.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbImage, KbScope
from relaydesk.services import blobs, kb_articles, kb_images


def _visible(statement):
    """The two predicates that define 'public'. Applied by every query here."""
    return statement.where(
        KbCategory.scope == KbScope.external,
        KbArticle.status == ArticleStatus.published,
    )


async def index(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[tuple[KbCategory, list[KbArticle]]]:
    rows = await session.execute(
        _visible(
            sa.select(KbCategory, KbArticle)
            .join(KbArticle, KbArticle.category_id == KbCategory.id)
            .where(KbCategory.workspace_id == workspace_id)
        ).order_by(KbCategory.position, KbArticle.title)
    )
    grouped: dict[uuid.UUID, tuple[KbCategory, list[KbArticle]]] = {}
    for category, article in rows.all():
        grouped.setdefault(category.id, (category, []))[1].append(article)
    return list(grouped.values())


async def article(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    category_slug: str,
    article_slug: str,
) -> KbArticle:
    found = await session.scalar(
        _visible(
            sa.select(KbArticle)
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbArticle.workspace_id == workspace_id,
                KbCategory.slug == category_slug,
                KbArticle.slug == article_slug,
            )
        )
    )
    if found is None:
        # 404 rather than 403: confirming an unpublished article exists at a
        # guessable slug is itself a leak.
        raise NotFound("No such article.")
    return found


async def search(
    session: AsyncSession, workspace_id: uuid.UUID, query: str
) -> list[KbArticle]:
    return await kb_articles.search(
        session, workspace_id, query, scope=KbScope.external, published_only=True
    )


async def image(
    session: AsyncSession, workspace_id: uuid.UUID, image_id: uuid.UUID
) -> tuple[KbImage, bytes]:
    """An image inherits its article's visibility.

    Without this join an unpublished article's screenshots are readable by
    anyone who guesses an id -- the article hidden, its pictures not.
    """
    row = await session.scalar(
        _visible(
            sa.select(KbImage)
            .join(KbArticle, KbArticle.id == KbImage.article_id)
            .join(KbCategory, KbCategory.id == KbArticle.category_id)
            .where(
                KbImage.id == image_id,
                KbImage.workspace_id == workspace_id,
            )
        )
    )
    if row is None:
        raise NotFound("No such image.")
    return row, blobs.read(kb_images.storage_root(), workspace_id, row.sha256)
```

- [ ] **Step 4: Add the routes**

In `api/public.py`, add the four routes, each resolving the workspace first via `resolve_workspace(session, slug)` and then delegating. The image route mirrors Task 7's headers — `media_type=row.content_type`, `X-Content-Type-Options: nosniff`.

- [ ] **Step 5: Run the tests, lint, commit**

Run: `docker compose exec api pytest tests/test_kb_public.py -v`
Expected: PASS (12 passed).

Run: `docker compose exec api pytest -q -m "not integration" && docker compose exec api ruff check .`

```bash
git add apps/api
git commit -m "feat(api): add the public knowledge base surface"
```

---

### Task 10: The document renderer

The one place a mistake becomes cross-site scripting on a page anonymous visitors read. Its safety is structural — React elements built from a known node table, so there is no code path that injects markup — and this task adds a lint rule that keeps it that way, plus the first frontend test runner in this repo.

Adding Vitest is deliberate scope. The renderer has real logic (nested lists, marks, unknown nodes) and "verified by looking at it" is not good enough for this particular file.

**Files:**
- Modify: `apps/web/package.json`, `apps/web/eslint.config.mjs`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/components/knowledge-base/doc-renderer.tsx`
- Create: `apps/web/components/knowledge-base/doc-renderer.test.tsx`

**Interfaces:**
- Consumes: nothing.
- Produces: `<DocRenderer doc={doc} imageSrc={(id) => string} />`

- [ ] **Step 1: Add Vitest and the lint rule**

```sh
docker compose exec web pnpm add -D vitest @vitejs/plugin-react @testing-library/react jsdom
```

Add to `package.json` scripts: `"test": "vitest run"`.

Create `apps/web/vitest.config.ts`:

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true },
  resolve: { alias: { "@": new URL("./", import.meta.url).pathname } },
});
```

In `eslint.config.mjs`, add a rule that bans the escape hatch outright:

```javascript
{
  rules: {
    // The knowledge base renders documents written by workspace members and
    // read by anonymous visitors. Rendering from a node table into React
    // elements is what makes that safe; one dangerouslySetInnerHTML would
    // undo it, so the rule is absolute rather than per-file.
    "react/no-danger": "error",
  },
},
```

If `eslint-plugin-react` is not already configured, use the equivalent `no-restricted-syntax` rule matching `JSXAttribute[name.name='dangerouslySetInnerHTML']` — the point is that the build fails, not which plugin enforces it.

- [ ] **Step 2: Write the failing test**

Create `apps/web/components/knowledge-base/doc-renderer.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocRenderer } from "./doc-renderer";

const src = (id: string) => `/api/kb/images/${id}`;

const doc = (...content: unknown[]) => ({ type: "doc", content });
const para = (text: string) => ({
  type: "paragraph",
  content: [{ type: "text", text }],
});

describe("DocRenderer", () => {
  it("renders paragraphs in order", () => {
    render(<DocRenderer doc={doc(para("First."), para("Second."))} imageSrc={src} />);

    expect(screen.getByText("First.")).toBeDefined();
    expect(screen.getByText("Second.")).toBeDefined();
  });

  it("renders nested lists", () => {
    render(
      <DocRenderer
        doc={doc({
          type: "bulletList",
          content: [{ type: "listItem", content: [para("Alpha")] }],
        })}
        imageSrc={src}
      />,
    );

    expect(screen.getByRole("listitem").textContent).toBe("Alpha");
  });

  it("renders an unknown node as nothing, without dropping its siblings", () => {
    render(
      <DocRenderer
        doc={doc(para("Before"), { type: "somethingNew" }, para("After"))}
        imageSrc={src}
      />,
    );

    expect(screen.getByText("Before")).toBeDefined();
    expect(screen.getByText("After")).toBeDefined();
  });

  it("renders a link's text but never a javascript: href", () => {
    render(
      <DocRenderer
        doc={doc({
          type: "paragraph",
          content: [
            {
              type: "text",
              text: "click me",
              marks: [{ type: "link", attrs: { href: "javascript:alert(1)" } }],
            },
          ],
        })}
        imageSrc={src}
      />,
    );

    const link = screen.queryByRole("link");
    expect(link?.getAttribute("href") ?? "").not.toContain("javascript:");
  });

  it("builds image sources through the provided resolver", () => {
    render(
      <DocRenderer
        doc={doc({ type: "image", attrs: { id: "abc", alt: "A screenshot" } })}
        imageSrc={src}
      />,
    );

    expect(screen.getByAltText("A screenshot").getAttribute("src")).toBe(
      "/api/kb/images/abc",
    );
  });

  it("renders nothing for a malformed document rather than throwing", () => {
    render(<DocRenderer doc={{} as never} imageSrc={src} />);
    render(<DocRenderer doc={{ type: "doc", content: "nope" } as never} imageSrc={src} />);
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `docker compose exec web pnpm test`
Expected: FAIL — cannot resolve `./doc-renderer`.

- [ ] **Step 4: Write the renderer**

Create `apps/web/components/knowledge-base/doc-renderer.tsx`. Render every node through a lookup on `node.type`; anything absent from the table returns `null`. Marks (`bold`, `italic`, `code`, `link`) wrap the text node. **There is no `dangerouslySetInnerHTML` in this file and there must never be** — that is what makes rendering a member-authored document on a public page safe.

Handle: `doc`, `paragraph`, `heading` (levels 1–3), `bulletList`, `orderedList`, `listItem`, `blockquote`, `codeBlock`, `horizontalRule`, `table`/`tableRow`/`tableCell`/`tableHeader`, `image`, `hardBreak`, and `text`.

Two specifics that are not obvious:

```tsx
// A link href comes from the editor, but the editor is a text field and a
// member could paste anything. Only http, https, and mailto survive.
const SAFE_PROTOCOLS = ["http:", "https:", "mailto:"];

function safeHref(href: unknown): string | undefined {
  if (typeof href !== "string") return undefined;
  try {
    return SAFE_PROTOCOLS.includes(new URL(href, "https://x.invalid").protocol)
      ? href
      : undefined;
  } catch {
    return undefined;
  }
}
```

and guard the walk so a malformed document renders nothing rather than throwing:

```tsx
function children(node: { content?: unknown }, imageSrc: (id: string) => string) {
  return Array.isArray(node.content)
    ? node.content.map((child, i) => (
        <DocNode key={i} node={child} imageSrc={imageSrc} />
      ))
    : null;
}
```

External links get `rel="noopener noreferrer"`.

- [ ] **Step 5: Run the tests, lint, commit**

Run: `docker compose exec web pnpm test && docker compose exec web pnpm lint && docker compose exec web pnpm build`
Expected: 6 passing, 0 lint problems, clean build.

Then prove the lint rule bites: temporarily add `<div dangerouslySetInnerHTML={{ __html: "x" }} />` to any component, run `pnpm lint`, confirm it errors, and remove it. Include that output in your report — a rule that does not fail is not a rule.

```bash
git add apps/web
git commit -m "feat(web): render knowledge base documents without HTML injection"
```

---

### Task 11: The console — list and editor

**Files:**
- Create: `apps/web/lib/api/kb.ts`
- Create: `apps/web/app/(console)/knowledge-base/[id]/page.tsx`
- Create: `apps/web/app/(console)/knowledge-base/actions.ts`
- Create: `apps/web/components/knowledge-base/editor.tsx`
- Modify: `apps/web/app/(console)/knowledge-base/page.tsx`
- Modify: `apps/web/components/knowledge-base/{category-list,new-category-dialog,source-dialog}.tsx`
- Modify: `apps/web/lib/types.ts`
- Delete: `apps/web/lib/mock/knowledge-base.ts`

**Interfaces:**
- Consumes: the whole `/api/kb` surface (Tasks 3–7); `DocRenderer` (Task 10).
- Produces: no API surface.

- [ ] **Step 1: Add TipTap and the API client**

```sh
docker compose exec web pnpm add @tiptap/react @tiptap/pm @tiptap/starter-kit @tiptap/extension-link @tiptap/extension-image @tiptap/extension-table @tiptap/extension-table-row @tiptap/extension-table-cell @tiptap/extension-table-header
```

Create `lib/api/kb.ts` following `lib/api/labels.ts` exactly, including `cache()` on every read: `getCategories(scope)`, `getArticles(params)`, `getArticle(id)`, `createArticle`, `updateArticle`, `setArticleStatus`, `deleteArticle`, `createCategory`, `updateCategory`, `deleteCategory`.

Update `lib/types.ts`: `KbArticle` gains `slug`, `categoryId`, `doc: unknown`, `publishedAt: string | null`; `KbCategory` gains `slug`, `scope`, `position`, `articleCount`. Delete `lib/mock/knowledge-base.ts` and every import of it.

- [ ] **Step 2: Wire the list page**

`knowledge-base/page.tsx` reads `getCategories` and `getArticles` per scope, keeping its existing two-tab layout. "New article" posts through a server action and redirects to `/knowledge-base/{id}`. `NewCategoryDialog` posts a real category.

`SourceDialog` stays inert — importing is explicitly out of scope — but its copy must say so plainly rather than presenting a button that silently does nothing. Change its primary action to a disabled control with a short "Coming in a later release" note, matching how the Discord section on `settings/channels` already handles this.

- [ ] **Step 3: Build the editor**

`components/knowledge-base/editor.tsx` — a client component wrapping TipTap with a toolbar: headings 1–3, bold, italic, code, bullet and ordered lists, blockquote, code block, link, table, horizontal rule, image.

Save is explicit, not autosave: a **Save** button that PATCHes `{ title, excerpt, doc }`. A knowledge hub is reviewed content, and silent autosave into a published article puts a half-finished edit in front of customers.

Status lives beside it: a control showing the current state with the legal transitions only — `draft` offers "Mark ready", `ready` offers "Publish" and "Back to draft", `published` offers "Unpublish". Do not offer a transition the API will reject; the state machine is in `ALLOWED_TRANSITIONS` in `services/kb_articles.py`.

Image upload: paste and drag both POST to `/api/kb/articles/{id}/images` and insert an `image` node carrying the returned id. The editor renders it through `/api/kb/images/{id}`.

- [ ] **Step 4: Verify in the browser**

With the stack up and seeded, at http://localhost:3000/knowledge-base: create a category, create an article, type into it with headings and a list, paste an image, save, reload and confirm it persisted, then walk it draft → ready → published and confirm the illegal transitions are simply not offered.

- [ ] **Step 5: Lint, build, commit**

Run: `docker compose exec web pnpm lint && docker compose exec web pnpm build && docker compose exec web pnpm test`

```bash
git add apps/web
git commit -m "feat(web): author knowledge base articles in the console"
```

---

### Task 12: The public hub

**Files:**
- Create: `apps/web/app/(portal)/help/page.tsx`
- Create: `apps/web/app/(portal)/help/[category]/page.tsx`
- Create: `apps/web/app/(portal)/help/[category]/[article]/page.tsx`
- Create: `apps/web/app/(portal)/help/search/page.tsx`
- Modify: `apps/web/lib/api/public.ts`
- Modify: `README.md`

**Interfaces:**
- Consumes: `/api/public/{slug}/kb*` (Task 9); `DocRenderer` (Task 10); the `x-relaydesk-workspace` header (Task 8).
- Produces: no API surface.

- [ ] **Step 1: Extend the public API client**

In `lib/api/public.ts`, add `getPublicKb(slug)`, `getPublicArticle(slug, category, article)`, and `searchPublicKb(slug, q)` — all unauthenticated, all `cache()`-wrapped.

- [ ] **Step 2: Build the four pages**

All server components. Each reads the workspace slug from the `x-relaydesk-workspace` header the middleware set, and calls `notFound()` when it is absent.

- `/help` — categories with their published articles, each showing title and excerpt. Empty categories are already omitted by the API.
- `/help/[category]` — that category's articles.
- `/help/[category]/[article]` — the article, rendered with `<DocRenderer imageSrc={(id) => `/api/public/${slug}/kb/images/${id}`} />`. **Note the resolver differs from the console's** — a public page must serve images through the public route, which enforces that the image's article is actually published.
- `/help/search?q=` — results, with an empty-query state and a no-results state.

A missing article calls `notFound()`. Next renders its 404, which is correct: `draft`, `ready`, another workspace's article, and one that never existed all look identical from outside.

Add `export const metadata` per page with the article or category title, and `openGraph` on the article page — a public knowledge base is meant to be linked and indexed.

- [ ] **Step 3: Verify in the browser**

With an article published from Task 11, visit `http://chronon.localhost:3000/help`. Then check the negative cases, which matter more:

```sh
curl -s -o /dev/null -w "draft article: %{http_code}\n" http://chronon.localhost:3000/help/billing/<a-draft-slug>
curl -s -o /dev/null -w "unknown workspace: %{http_code}\n" http://nobody.localhost:3000/help
curl -s -o /dev/null -w "reserved label: %{http_code}\n" http://api.localhost:3000/help
```

Expected: `404` for all three.

- [ ] **Step 4: Update the README**

Add a knowledge base section: the two scopes and what each is for, the review workflow, and — most importantly — the **deployment requirement** that the portal domain needs wildcard DNS and a wildcard certificate, with the note that local development uses `<slug>.localhost:3000`. Leaving that implicit is how slice 2 shipped a poller aimed at an empty mailbox.

- [ ] **Step 5: Lint, build, commit**

Run: `docker compose exec web pnpm lint && docker compose exec web pnpm build && docker compose exec api pytest -q -m "not integration"`

```bash
git add apps/web README.md
git commit -m "feat(web): serve the public knowledge base on the portal subdomain"
```

---

## Done

At the end of Task 12: a workspace writes internal runbooks and customer-facing articles in a rich editor, reviews them through draft → ready → published, and published external articles are readable by anyone at `<slug>.<portal domain>/help` with full-text search. Internal articles are stored in the shape slice 4's AI retrieval will read.

Deferred by design: importing articles from a URL or file; AI retrieval and suggestions; article versioning; custom domains; and the portal's authenticated surfaces, which still need contact sessions.
