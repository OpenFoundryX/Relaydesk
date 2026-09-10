# AI Answers in the Widget — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The widget's panel answers a visitor's question from the workspace's published knowledge base, links the articles it used, and hands off to the existing message form whenever it cannot.

**Architecture:** Retrieval runs first over Postgres full-text search; the retrieved articles are numbered and become the model's only permitted source material; the model cites them as `[n]` markers which the server maps back to real published paths, so a fabricated citation resolves to nothing. Every failure — no key, provider down, budget spent, weak retrieval, a model that declines — degrades to the search-and-form widget that already ships. The provider sits behind a protocol so the whole slice is testable without a network or a key.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Postgres 16, Alembic, `anthropic` Python SDK, Next.js App Router, vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-11-widget-ai-answers-design.md`

## Global Constraints

- **Run API tests inside the compose network**: `docker compose exec -T api pytest …` from the repo root. `.env` points `DATABASE_URL` at the Docker hostname `postgres`, which does not resolve on the host. Web tests run on the host: `cd apps/web && pnpm vitest run`.
- **Fixtures are `client` and `db_session`.** `asyncio_mode = "auto"` — never add `@pytest.mark.asyncio`. API test URLs are `/api/…`.
- **Every schema inherits `CamelModel`** (`relaydesk.schemas.base`), never `BaseModel`. Python stays snake_case, the wire is camelCase.
- **Every mutating route calls `await session.commit()`.** `get_session` has no commit-on-exit and there is no commit-on-success middleware; an uncommitted flush is rolled back at request end. This defect shipped four times in slice 8 — see `api/widget.py` and `api/snippets.py` for the pattern.
- **In `api/widget.py`, declare every fixed-segment route above the `GET /{key}/kb/{path:path}` catch-all.** FastAPI matches in declaration order.
- **The default model is `claude-opus-5`.** Never substitute a cheaper model in code; the workspace chooses. Use the exact id string — never append a date suffix.
- **Do not write an Anthropic request from memory.** Load the `claude-api` skill and read `python/claude-api/README.md` and `python/claude-api/streaming.md` first. `budget_tokens` is rejected on current models, assistant prefill returns 400, and `output_format` is superseded by `output_config`.
- **Prose and comments are en-GB** ("behaviour", "colour", "centre").
- **Known baselines, not yours to fix**: the API suite has 11 pre-existing SMTP/`aiosmtpd` failures (`test_mailer.py`, `test_outbound.py`, `test_channel_accounts.py`, `test_config.py`) plus occasionally a 12th in `test_imap_poll.py` depending on GreenMail's state; `npx tsc --noEmit` reports 3 pre-existing errors in `components/knowledge-base/*.test.tsx`. Compare against those, not zero.

## File Structure

| File | Responsibility |
|---|---|
| `apps/api/src/relaydesk/models/ai_config.py` | Per-workspace provider, model, key, budget |
| `apps/api/src/relaydesk/models/ai_call.py` | The audit row for every inference call |
| `apps/api/migrations/versions/0025_ai_configs.py` | |
| `apps/api/migrations/versions/0026_ai_calls.py` | |
| `apps/api/src/relaydesk/services/ai_provider.py` | The `Provider` protocol, the Anthropic implementation, and `FakeProvider` for tests |
| `apps/api/src/relaydesk/services/ai_redact.py` | Pattern redaction before egress. Pure functions |
| `apps/api/src/relaydesk/services/ai_retrieval.py` | Retrieval, the relevance floor, numbering, citation resolution. Pure where it can be |
| `apps/api/src/relaydesk/services/ai_budget.py` | The daily token ceiling and its window |
| `apps/api/src/relaydesk/services/ai_answers.py` | Assembles the above into one answer attempt and records the call |
| `apps/api/src/relaydesk/services/ai_configs.py` | Console CRUD, key write-only |
| `apps/api/src/relaydesk/api/ai_configs.py` | Admin console routes |
| `apps/api/src/relaydesk/api/widget.py` | Gains `POST /{key}/ask` |
| `apps/web/app/(widget)/widget/ask/route.ts` | Streams the answer through to the panel |
| `apps/web/components/widget/ask.tsx` | The conversation view |
| `apps/web/app/(console)/settings/ai/page.tsx` | Console configuration screen |

---

### Task 1: `AiConfig` — the per-workspace model configuration

**Files:**
- Create: `apps/api/src/relaydesk/models/ai_config.py`
- Create: `apps/api/migrations/versions/0025_ai_configs.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Test: `apps/api/tests/test_ai_config_model.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `AiConfig` with `workspace_id` (primary key), `provider`, `model`, `api_key`, `base_url`, `daily_token_budget`, `enabled`, timestamps.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ai_config_model.py
import sqlalchemy as sa

from relaydesk.models.ai_config import AiConfig
from tests.factories import make_workspace


async def test_defaults_are_off_and_unconfigured(db_session) -> None:
    """A workspace that has never touched AI must look exactly like one that never will."""
    workspace = await make_workspace(db_session)
    config = AiConfig(workspace_id=workspace.id)
    db_session.add(config)
    await db_session.flush()

    assert config.enabled is False
    assert config.api_key is None
    assert config.model == "claude-opus-5"
    assert config.provider == "anthropic"
    assert config.daily_token_budget == 200_000


async def test_one_config_per_workspace(db_session) -> None:
    workspace = await make_workspace(db_session)
    db_session.add(AiConfig(workspace_id=workspace.id))
    await db_session.flush()
    db_session.add(AiConfig(workspace_id=workspace.id))

    with pytest.raises(sa.exc.IntegrityError):
        await db_session.flush()
```

Add `import pytest` at the top.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ai_config_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.models.ai_config'`

- [ ] **Step 3: Write the model**

```python
# apps/api/src/relaydesk/models/ai_config.py
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_DAILY_TOKEN_BUDGET = 200_000


class AiConfig(Base, TimestampMixin):
    """How one workspace reaches a model, and what it is willing to spend.

    ``workspace_id`` is the primary key: a workspace has one configuration
    or none. There is deliberately no per-embed override -- a workspace
    running two widgets gets the same answering behaviour on both, and
    spend is a property of the workspace rather than of a script tag.

    ``api_key`` is **write-only**. It is set through the console and never
    returned by any endpoint; the console shows a masked suffix so an admin
    can tell which key is installed without being handed it back. That
    departs from ``Webhook.secret``, which is stored in plaintext and *is*
    returned, and the reason is that a webhook signature needs the same key
    at both ends while a model key needs only this server. It cannot be a
    digest either -- the value has to be replayed to the provider -- so a
    database compromise discloses it, and that is the cost this design
    accepts rather than hides.

    ``enabled`` is separate from ``api_key`` being present so a workspace
    can switch the feature off without discarding what it configured.

    ``base_url`` set means the workspace is pointing at inference it hosts
    itself, which is what makes redaction skippable (spec D6): the text
    never leaves their deployment.
    """

    __tablename__ = "ai_configs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="anthropic", server_default="anthropic"
    )
    model: Mapped[str] = mapped_column(
        String(64), nullable=False, default=DEFAULT_MODEL, server_default=DEFAULT_MODEL
    )
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    daily_token_budget: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_DAILY_TOKEN_BUDGET,
        server_default=str(DEFAULT_DAILY_TOKEN_BUDGET),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
```

- [ ] **Step 4: Register the model**

In `apps/api/src/relaydesk/models/__init__.py`, add `from relaydesk.models.ai_config import AiConfig` in alphabetical position (before `from relaydesk.models.api_key import ...`) and `"AiConfig"` to `__all__` before `"ApiKey"`.

- [ ] **Step 5: Write the migration**

```python
# apps/api/migrations/versions/0025_ai_configs.py
"""ai configs

How one workspace reaches a model, and what it will spend doing it.

``api_key`` is stored recoverable because the value must be replayed to the
provider on every call -- a digest cannot serve it. It is never returned by
any endpoint, which is the difference between this and ``webhooks.secret``:
a webhook signature needs the key at both ends, a model key needs only this
server. See the model docstring for what that costs.

Keyed on ``workspace_id`` rather than carrying its own id: a workspace has
one configuration or none, and spend is a property of the workspace, not of
an individual embed.

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-11 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_configs",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "provider", sa.String(length=32), nullable=False, server_default="anthropic"
        ),
        sa.Column(
            "model", sa.String(length=64), nullable=False, server_default="claude-opus-5"
        ),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column(
            "daily_token_budget", sa.Integer(), nullable=False, server_default="200000"
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("ai_configs")
```

- [ ] **Step 6: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_config_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/models/ai_config.py apps/api/src/relaydesk/models/__init__.py apps/api/migrations/versions/0025_ai_configs.py apps/api/tests/test_ai_config_model.py
git commit -m "feat(ai): where a workspace says which model, and what it will spend"
```

---

### Task 2: `AiCall` — the audit row

**Files:**
- Create: `apps/api/src/relaydesk/models/ai_call.py`
- Create: `apps/api/migrations/versions/0026_ai_calls.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Test: `apps/api/tests/test_ai_call_model.py`

**Interfaces:**
- Consumes: `AiConfig` (Task 1) only for migration ordering.
- Produces: `AiCall`, and `AiOutcome` — a `StrEnum` with members `answered`, `escalated`, `refused`, `degraded`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ai_call_model.py
import sqlalchemy as sa

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_cost_is_integer_micros(db_session) -> None:
    """Money in a float is a rounding argument waiting to happen."""
    workspace = await make_workspace(db_session)
    db_session.add(
        AiCall(
            workspace_id=workspace.id,
            model="claude-opus-5",
            input_tokens=1200,
            output_tokens=300,
            cost_micros=13_500,
            latency_ms=1840,
            outcome=AiOutcome.answered,
        )
    )
    await db_session.flush()

    stored = await db_session.scalar(sa.select(AiCall.cost_micros))
    assert stored == 13_500
    assert isinstance(stored, int)


async def test_revoking_an_embed_keeps_the_record_of_what_it_spent(db_session) -> None:
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    db_session.add(
        AiCall(
            workspace_id=workspace.id,
            widget_key_id=key.id,
            model="claude-opus-5",
            input_tokens=10,
            output_tokens=5,
            cost_micros=100,
            latency_ms=200,
            outcome=AiOutcome.answered,
        )
    )
    await db_session.flush()

    await widget_keys.delete(db_session, workspace.id, key.id)

    row = await db_session.scalar(sa.select(AiCall))
    assert row is not None
    assert row.widget_key_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ai_call_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.models.ai_call'`

- [ ] **Step 3: Write the model**

```python
# apps/api/src/relaydesk/models/ai_call.py
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class AiOutcome(enum.StrEnum):
    """What happened, in the terms the deflection number is computed in."""

    answered = "answered"
    escalated = "escalated"
    refused = "refused"
    degraded = "degraded"


class AiCall(UUIDMixin, TimestampMixin, Base):
    """One inference attempt, recorded whatever became of it.

    This table is what makes a deflection figure auditable rather than
    asserted. A vendor's published resolution rate is a claim; a workspace
    that can run a query over its own calls has a number.

    It holds no message content -- not the question, not the answer, not the
    retrieved articles. The transcript lives in the visitor's browser for
    the life of the panel and, on escalation only, in the ticket they chose
    to send. What is recorded here is shape and cost, never what was said.

    ``cost_micros`` is an integer count of millionths of a unit of currency.
    Money in a float is a rounding argument waiting to happen, and this
    column will eventually be summed across a billing period.

    ``widget_key_id`` is ``SET NULL`` rather than cascade on purpose:
    deleting an embed is how it is revoked (see ``WidgetKey``), and
    revocation must not erase the record of what that embed spent.
    """

    __tablename__ = "ai_calls"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    widget_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("widget_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[AiOutcome] = mapped_column(
        Enum(
            AiOutcome,
            name="ck_ai_calls_outcome",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        nullable=False,
    )
    # Which of spec D4's conditions applied, when `outcome` is `degraded`.
    reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 4: Register the model**

In `models/__init__.py`, add `from relaydesk.models.ai_call import AiCall, AiOutcome` after the `ai_config` import, and `"AiCall"`, `"AiOutcome"` to `__all__` in alphabetical position.

- [ ] **Step 5: Write the migration**

```python
# apps/api/migrations/versions/0026_ai_calls.py
"""ai calls

One row per inference attempt, whatever became of it -- answered, escalated,
refused, or degraded because one of spec D4's conditions applied.

This is the audit behind the deflection number. Slice 8 argued that such a
figure is only worth something if the workspace can check it; this table and
``widget_sessions`` are that check.

No message content is stored: not the question, not the answer, not the
articles retrieved. Shape and cost only.

``cost_micros`` is a BigInteger count of millionths, never a float, because
it will be summed across a billing period. ``widget_key_id`` is SET NULL so
that revoking an embed -- which is done by deleting it -- does not erase the
record of what it spent.

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-11 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("widget_key_id", sa.UUID(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "outcome",
            sa.String(length=16),
            sa.CheckConstraint(
                "outcome IN ('answered', 'escalated', 'refused', 'degraded')",
                name="ck_ai_calls_outcome",
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["widget_key_id"], ["widget_keys.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_calls_workspace_id", "ai_calls", ["workspace_id"])
    # The budget window (spec D5) counts today's tokens for one workspace.
    op.create_index(
        "ix_ai_calls_workspace_created", "ai_calls", ["workspace_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_calls_workspace_created", table_name="ai_calls")
    op.drop_index("ix_ai_calls_workspace_id", table_name="ai_calls")
    op.drop_table("ai_calls")
```

- [ ] **Step 6: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_call_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/models/ai_call.py apps/api/src/relaydesk/models/__init__.py apps/api/migrations/versions/0026_ai_calls.py apps/api/tests/test_ai_call_model.py
git commit -m "feat(ai): record every call, so the deflection number can be checked"
```

---

### Task 3: Redaction before egress

Isolated as pure functions so the patterns can be tested exhaustively without a database or a provider.

**Files:**
- Create: `apps/api/src/relaydesk/services/ai_redact.py`
- Test: `apps/api/tests/test_ai_redact.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `redact(text: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ai_redact.py
import pytest

from relaydesk.services.ai_redact import redact


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("email me at wren@lantern.co", "email me at [email]"),
        ("WREN@LANTERN.CO please", "[email] please"),
        ("call 020 7946 0958", "call [phone]"),
        ("call +44 20 7946 0958", "call [phone]"),
        ("card 4111 1111 1111 1111", "card [number]"),
        ("card 4111-1111-1111-1111", "card [number]"),
    ],
)
def test_redacts(raw, expected):
    assert redact(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "my order is 1042",
        "version 2.5.1 broke it",
        "I waited 30 minutes",
        "",
    ],
)
def test_leaves_ordinary_text_alone(raw):
    """Over-redaction destroys the question. A short number is not a card."""
    assert redact(raw) == raw


def test_redacts_several_in_one_message():
    assert redact("wren@lantern.co or 020 7946 0958") == "[email] or [phone]"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ai_redact.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.services.ai_redact'`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/src/relaydesk/services/ai_redact.py
"""Strip the obvious personal data out of a visitor's message before it leaves.

This is pattern matching, and the honest description of pattern matching is
that it reduces routine leakage of things a visitor volunteered -- an
address typed into a support question, a card number pasted in a panic. It
is **not** a guarantee, and nothing downstream should be designed as though
it were.

The failure mode worth avoiding is over-redaction. A question with its
nouns replaced by placeholders is a question the model cannot answer, so
these patterns are deliberately narrow: an order number stays, a version
string stays, a duration stays. Only shapes that are almost never anything
else are replaced.

Skipped entirely when the workspace has configured a ``base_url`` of its
own (spec D6): the text never leaves their deployment, so redacting it
costs answer quality and buys nothing.
"""

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Long enough runs of digits, optionally grouped, to be a card or an
# account. Fifteen digits minimum keeps order numbers and years out.
_CARD = re.compile(r"\b(?:\d[ -]?){15,19}\b")
# An international prefix, or a run of digits with separators long enough
# to be a telephone number rather than a quantity.
_PHONE = re.compile(r"(?:\+\d{1,3}[ -]?)?(?:\(?\d{2,5}\)?[ -]?){2,4}\d{2,4}")


def redact(text: str) -> str:
    """``text`` with emails, card-like runs and telephone numbers replaced.

    Order matters: cards are matched before telephone numbers, because a
    sixteen-digit card also satisfies a permissive phone pattern and the
    more specific label is the more useful one to a reader of the audit.
    """
    redacted = _EMAIL.sub("[email]", text)
    redacted = _CARD.sub("[number]", redacted)
    return _PHONE.sub("[phone]", redacted)
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_redact.py -v`
Expected: PASS. If a case in `test_leaves_ordinary_text_alone` fails, the phone pattern is too greedy — tighten it rather than deleting the test; over-redaction is the failure this task exists to prevent.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/ai_redact.py apps/api/tests/test_ai_redact.py
git commit -m "feat(ai): redact the obvious, and say plainly that it is not a guarantee"
```

---

### Task 4: Retrieval, numbering, and citation resolution

**Files:**
- Create: `apps/api/src/relaydesk/services/ai_retrieval.py`
- Test: `apps/api/tests/test_ai_retrieval.py`

**Interfaces:**
- Consumes: `kb_public.search(session, workspace_id, query) -> list[KbArticle]` and `kb_public.paths_for(session, workspace_id, articles) -> dict[uuid.UUID, list[KbCategory]]`.
- Produces:
  - `@dataclass(frozen=True) Source: number: int; article_id: uuid.UUID; title: str; path: str; body: str`
  - `async retrieve(session, workspace_id, question, *, limit=5) -> list[Source]`
  - `render_context(sources: list[Source]) -> str`
  - `resolve_citations(answer: str, sources: list[Source]) -> list[Source]`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ai_retrieval.py
import uuid

from relaydesk.services.ai_retrieval import Source, render_context, resolve_citations


def _source(number: int, title: str = "Refunds") -> Source:
    return Source(
        number=number,
        article_id=uuid.uuid4(),
        title=title,
        path="billing/refunds",
        body="We refund any plan in full within 14 days.",
    )


def test_render_numbers_the_sources_for_the_model():
    rendered = render_context([_source(1), _source(2, "Cancelling")])
    assert "[1] Refunds" in rendered
    assert "[2] Cancelling" in rendered


def test_resolves_a_cited_marker_to_its_source():
    sources = [_source(1), _source(2, "Cancelling")]
    cited = resolve_citations("You can ask for one [1].", sources)
    assert [source.number for source in cited] == [1]


def test_an_invented_marker_resolves_to_nothing():
    """The whole point of resolving server-side: a fabricated citation cannot render."""
    sources = [_source(1)]
    assert resolve_citations("See [7] and [9].", sources) == []


def test_each_source_is_returned_once_however_often_it_is_cited():
    sources = [_source(1)]
    cited = resolve_citations("[1] and again [1] and once more [1]", sources)
    assert len(cited) == 1


def test_citations_come_back_in_the_order_they_were_cited():
    sources = [_source(1), _source(2, "Cancelling"), _source(3, "Billing")]
    cited = resolve_citations("First [3], then [1].", sources)
    assert [source.number for source in cited] == [3, 1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ai_retrieval.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.services.ai_retrieval'`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/src/relaydesk/services/ai_retrieval.py
"""What the model is allowed to know, and how a citation becomes a link.

Retrieval runs before the model does. If nothing clears the relevance floor
the model is never called at all -- an answer with no source material is
the failure this module exists to prevent, not an edge case to handle
afterwards.

The retrieved articles are numbered, and the model is instructed to cite
them as ``[n]``. Those markers are mapped back to articles **here**, on the
server, from the numbering the server itself issued. A model that invents
``[9]`` when it was given five sources produces no citation, because nine
resolves to nothing. That is the difference between citing and appearing to
cite, and it is why the panel's links can be trusted (spec D3).
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.kb import KbArticle, KbCategory
from relaydesk.services import kb_public

# A tunable, not a constant. The right value is a property of a workspace's
# writing, and the deflection counters from slice 8 are what will
# eventually set it -- they record what visitors searched and whether they
# escalated anyway.
RELEVANCE_FLOOR = 0.05

_MARKER = re.compile(r"\[(\d{1,2})\]")


@dataclass(frozen=True)
class Source:
    """One retrieved article, as the model will see it and as it resolves back."""

    number: int
    article_id: uuid.UUID
    title: str
    path: str
    body: str


def _path(ancestors: list[KbCategory], article: KbArticle) -> str:
    return "/".join([*(category.slug for category in ancestors), article.slug])


async def retrieve(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    question: str,
    *,
    limit: int = 5,
) -> list[Source]:
    """The published articles this question may be answered from, numbered.

    Returns an empty list when nothing is relevant enough, and the caller
    must treat that as "do not call the model" rather than as "call it with
    no context" -- a model given no sources will answer from its training
    data, which is exactly what grounding exists to prevent.
    """
    articles = await kb_public.search(session, workspace_id, question)
    if not articles:
        return []

    kept = articles[:limit]
    ancestors = await kb_public.paths_for(session, workspace_id, kept)
    return [
        Source(
            number=index,
            article_id=article.id,
            title=article.title,
            path=_path(ancestors.get(article.id, []), article),
            body=article.excerpt or "",
        )
        for index, article in enumerate(kept, start=1)
    ]


def render_context(sources: list[Source]) -> str:
    """The sources as the model receives them, numbered for citation."""
    return "\n\n".join(
        f"[{source.number}] {source.title}\n{source.body}" for source in sources
    )


def resolve_citations(answer: str, sources: list[Source]) -> list[Source]:
    """The sources an answer actually cited, in the order it cited them.

    Out-of-range markers are dropped silently rather than reported: the
    visitor gains nothing from being told the model miscounted, and the
    absence of a link is already the honest signal.
    """
    by_number = {source.number: source for source in sources}
    seen: list[Source] = []
    for match in _MARKER.finditer(answer):
        source = by_number.get(int(match.group(1)))
        if source is not None and source not in seen:
            seen.append(source)
    return seen
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_retrieval.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Add a database-backed test for `retrieve`**

```python
# apps/api/tests/test_ai_retrieval.py — append
from relaydesk.services.ai_retrieval import retrieve
from tests.factories import make_workspace


async def test_retrieve_returns_nothing_for_an_empty_knowledge_base(db_session) -> None:
    """No sources means the caller must not call the model at all."""
    workspace = await make_workspace(db_session)
    assert await retrieve(db_session, workspace.id, "how do refunds work") == []
```

- [ ] **Step 6: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_retrieval.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/services/ai_retrieval.py apps/api/tests/test_ai_retrieval.py
git commit -m "feat(ai): a citation the server issued is a citation the server can resolve"
```

---

### Task 5: The provider protocol, a fake, and the Anthropic implementation

**Files:**
- Create: `apps/api/src/relaydesk/services/ai_provider.py`
- Modify: `apps/api/pyproject.toml` (add `anthropic`)
- Test: `apps/api/tests/test_ai_provider.py`

**Interfaces:**
- Consumes: `AiConfig` (Task 1).
- Produces:
  - `@dataclass Completion: text: str; input_tokens: int; output_tokens: int; declined: bool`
  - `class Provider(Protocol)` with `async def complete(self, *, system: str, question: str, model: str) -> AsyncIterator[str]` and `def usage(self) -> Completion`
  - `class FakeProvider` — scripted, for every other task's tests
  - `class AnthropicProvider`
  - `def for_config(config: AiConfig) -> Provider`

**Before writing any Anthropic call:** load the `claude-api` skill and read `python/claude-api/README.md` and `python/claude-api/streaming.md`. Do not write the request from memory — `budget_tokens` is rejected on current models, assistant prefill returns 400, and `output_format` is superseded by `output_config`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ai_provider.py
import pytest

from relaydesk.models.ai_config import AiConfig
from relaydesk.services.ai_provider import FakeProvider, ProviderUnavailable, for_config


async def test_fake_streams_its_script():
    provider = FakeProvider(chunks=["You can ", "ask for one [1]."])
    received = [chunk async for chunk in provider.complete(
        system="s", question="q", model="claude-opus-5"
    )]
    assert "".join(received) == "You can ask for one [1]."
    assert provider.usage().output_tokens > 0


async def test_fake_can_be_scripted_to_fail():
    """Every caller must have a way to exercise the provider-down path."""
    provider = FakeProvider(fails=True)
    with pytest.raises(ProviderUnavailable):
        [chunk async for chunk in provider.complete(
            system="s", question="q", model="claude-opus-5"
        )]


def test_no_key_means_no_provider():
    config = AiConfig(provider="anthropic", model="claude-opus-5", api_key=None)
    assert for_config(config) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ai_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.services.ai_provider'`

- [ ] **Step 3: Add the dependency**

In `apps/api/pyproject.toml`, add `"anthropic>=1.0"` to `dependencies`. Rebuild the API image so the container has it:

```bash
docker compose up -d --build api
```

- [ ] **Step 4: Write the implementation**

```python
# apps/api/src/relaydesk/services/ai_provider.py
"""One interface to a model, and the two implementations behind it.

A protocol rather than a direct SDK call for two reasons. The first is
testable: every other module in this slice can be exercised against
``FakeProvider`` with no network, no key, and no cost. The second is the
product's own argument -- this is an AGPL, self-hostable desk whose input is
other companies' support transcripts, and a deployment that could only send
them to a vendor Relaydesk picked would be unusable for the teams most
likely to self-host. Self-hosted inference plugs in here.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from relaydesk.models.ai_config import AiConfig


class ProviderUnavailable(Exception):
    """The model could not be reached, or refused to answer.

    Deliberately one exception for both. The caller's response is the same
    either way -- degrade to the widget that already works (spec D4) -- and
    a visitor must not be able to tell an outage from a refusal.
    """


@dataclass
class Completion:
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    def complete(
        self, *, system: str, question: str, model: str
    ) -> AsyncIterator[str]: ...

    def usage(self) -> Completion: ...


@dataclass
class FakeProvider:
    """A scripted provider, for every test in this slice that is not about HTTP."""

    chunks: list[str] = field(default_factory=list)
    fails: bool = False
    _usage: Completion = field(default_factory=Completion)

    async def complete(
        self, *, system: str, question: str, model: str
    ) -> AsyncIterator[str]:
        if self.fails:
            raise ProviderUnavailable("scripted failure")
        for chunk in self.chunks:
            self._usage.text += chunk
            yield chunk
        self._usage.input_tokens = len(system) // 4 + len(question) // 4
        self._usage.output_tokens = len(self._usage.text) // 4

    def usage(self) -> Completion:
        return self._usage


class AnthropicProvider:
    """The real thing.

    ``thinking`` is adaptive and ``effort`` is low: support answering is a
    chat-shaped workload over a handful of retrieved paragraphs, and that is
    the shape that does not repay a high effort setting. Raise it only if
    measurement says so.

    The system prompt and the retrieved sources are a stable prefix across a
    conversation's turns while the question is not, which is what makes the
    cache breakpoint worth its placement.
    """

    def __init__(self, *, api_key: str, base_url: str | None = None) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, base_url=base_url, timeout=30.0, max_retries=1
        )
        self._usage = Completion()

    async def complete(
        self, *, system: str, question: str, model: str
    ) -> AsyncIterator[str]:
        import anthropic

        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=1024,
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
                system=[
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": question}],
            ) as stream:
                async for text in stream.text_stream:
                    self._usage.text += text
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIStatusError as error:
            raise ProviderUnavailable(str(error)) from error
        except anthropic.APIConnectionError as error:
            raise ProviderUnavailable(str(error)) from error

        if final.stop_reason == "refusal":
            raise ProviderUnavailable("refused")
        self._usage.input_tokens = final.usage.input_tokens
        self._usage.output_tokens = final.usage.output_tokens

    def usage(self) -> Completion:
        return self._usage


def for_config(config: AiConfig) -> Provider | None:
    """The provider this workspace configured, or ``None`` if it has none.

    ``None`` is not an error -- it is the ordinary state of a workspace that
    has not set a key, and the caller degrades to the widget that already
    works rather than reporting anything (spec D4).
    """
    if not config.enabled or not config.api_key:
        return None
    if config.provider != "anthropic":
        return None
    return AnthropicProvider(api_key=config.api_key, base_url=config.base_url)
```

- [ ] **Step 5: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_provider.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/relaydesk/services/ai_provider.py apps/api/pyproject.toml apps/api/uv.lock apps/api/tests/test_ai_provider.py
git commit -m "feat(ai): one interface, so the rest of the slice needs no network"
```

---

### Task 6: The daily token budget

**Files:**
- Create: `apps/api/src/relaydesk/services/ai_budget.py`
- Test: `apps/api/tests/test_ai_budget.py`

**Interfaces:**
- Consumes: `AiCall` (Task 2), `AiConfig` (Task 1).
- Produces: `async within_budget(session, config: AiConfig) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ai_budget.py
from datetime import UTC, datetime, timedelta

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig
from relaydesk.services.ai_budget import within_budget
from tests.factories import make_workspace


async def _spend(db_session, workspace_id, tokens: int, *, days_ago: int = 0) -> None:
    call = AiCall(
        workspace_id=workspace_id,
        model="claude-opus-5",
        input_tokens=tokens,
        output_tokens=0,
        cost_micros=0,
        latency_ms=1,
        outcome=AiOutcome.answered,
    )
    db_session.add(call)
    await db_session.flush()
    if days_ago:
        call.created_at = datetime.now(UTC) - timedelta(days=days_ago)
        await db_session.flush()


async def test_a_fresh_workspace_is_within_budget(db_session) -> None:
    workspace = await make_workspace(db_session)
    config = AiConfig(workspace_id=workspace.id, daily_token_budget=1000)
    db_session.add(config)
    await db_session.flush()

    assert await within_budget(db_session, config) is True


async def test_spending_the_budget_closes_it(db_session) -> None:
    workspace = await make_workspace(db_session)
    config = AiConfig(workspace_id=workspace.id, daily_token_budget=1000)
    db_session.add(config)
    await db_session.flush()
    await _spend(db_session, workspace.id, 1000)

    assert await within_budget(db_session, config) is False


async def test_yesterdays_spend_does_not_count(db_session) -> None:
    """A daily ceiling that never rolls over is not a daily ceiling."""
    workspace = await make_workspace(db_session)
    config = AiConfig(workspace_id=workspace.id, daily_token_budget=1000)
    db_session.add(config)
    await db_session.flush()
    await _spend(db_session, workspace.id, 5000, days_ago=2)

    assert await within_budget(db_session, config) is True


async def test_another_workspace_spend_does_not_count(db_session) -> None:
    one = await make_workspace(db_session, slug="one")
    two = await make_workspace(db_session, slug="two")
    config = AiConfig(workspace_id=one.id, daily_token_budget=1000)
    db_session.add(config)
    await db_session.flush()
    await _spend(db_session, two.id, 5000)

    assert await within_budget(db_session, config) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ai_budget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.services.ai_budget'`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/src/relaydesk/services/ai_budget.py
"""The ceiling on what one workspace's widget can spend in a day.

An anonymous endpoint that costs money on every call is a different animal
from an anonymous endpoint that reads public rows, and anyone who views a
customer's page source is holding the key that reaches it. The per-key
hourly cap bounds a single embed; this bounds the workspace.

Deliberately a token count rather than a currency amount. Tokens are what
the provider reports and what this table records, so the ceiling is checked
against the same unit it is spent in, with no conversion to get wrong.
"""

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.ai_call import AiCall
from relaydesk.models.ai_config import AiConfig

WINDOW = timedelta(days=1)


async def spent_today(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    since = datetime.now(UTC) - WINDOW
    total = await session.scalar(
        sa.select(
            sa.func.coalesce(
                sa.func.sum(AiCall.input_tokens + AiCall.output_tokens), 0
            )
        ).where(AiCall.workspace_id == workspace_id, AiCall.created_at >= since)
    )
    return int(total or 0)


async def within_budget(session: AsyncSession, config: AiConfig) -> bool:
    """Whether this workspace may make another call in the current window.

    Checked before the call rather than after it, so the ceiling is a
    ceiling rather than a report of one having been passed. The cost is
    that a single call can carry the total slightly beyond the limit; the
    alternative -- reserving tokens up front -- would need an estimate of
    output length that nothing can give honestly.
    """
    return await spent_today(session, config.workspace_id) < config.daily_token_budget
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_budget.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/ai_budget.py apps/api/tests/test_ai_budget.py
git commit -m "feat(ai): a spend ceiling checked before the spend, not after"
```

---

### Task 7: `ai_answers` — assembling one attempt

**Files:**
- Create: `apps/api/src/relaydesk/services/ai_answers.py`
- Test: `apps/api/tests/test_ai_answers.py`

**Interfaces:**
- Consumes: `ai_retrieval.retrieve/render_context/resolve_citations` (Task 4), `ai_provider.for_config/FakeProvider/ProviderUnavailable` (Task 5), `ai_budget.within_budget` (Task 6), `ai_redact.redact` (Task 3), `AiCall`/`AiOutcome` (Task 2), `AiConfig` (Task 1).
- Produces:
  - `@dataclass Degraded: reason: str`
  - `async answer(session, workspace, widget_key, question, *, provider=None) -> AsyncIterator[str] | Degraded` — see the note in Step 3 on why the shape is a small class rather than a bare generator.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ai_answers.py
import sqlalchemy as sa

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig
from relaydesk.services import widget_keys
from relaydesk.services.ai_answers import Attempt, answer
from relaydesk.services.ai_provider import FakeProvider
from tests.factories import make_workspace


async def _setup(db_session, *, enabled=True, budget=200_000):
    workspace = await make_workspace(db_session)
    config = AiConfig(
        workspace_id=workspace.id,
        api_key="sk-test",
        enabled=enabled,
        daily_token_budget=budget,
    )
    db_session.add(config)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.flush()
    return workspace, config, key


async def test_no_key_degrades_without_calling_anything(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    config.api_key = None
    await db_session.flush()

    attempt = await answer(db_session, workspace, key, "how do refunds work")

    assert attempt.degraded is True
    assert attempt.reason == "not_configured"


async def test_empty_knowledge_base_degrades_without_calling_the_model(db_session) -> None:
    """Retrieval is the gate. A model with no sources answers from training data."""
    workspace, config, key = await _setup(db_session)
    provider = FakeProvider(chunks=["should never run"])

    attempt = await answer(
        db_session, workspace, key, "how do refunds work", provider=provider
    )

    assert attempt.degraded is True
    assert attempt.reason == "no_sources"
    assert provider.usage().output_tokens == 0


async def test_exhausted_budget_degrades(db_session) -> None:
    workspace, config, key = await _setup(db_session, budget=1)
    db_session.add(
        AiCall(
            workspace_id=workspace.id,
            model="claude-opus-5",
            input_tokens=10,
            output_tokens=0,
            cost_micros=0,
            latency_ms=1,
            outcome=AiOutcome.answered,
        )
    )
    await db_session.flush()

    attempt = await answer(db_session, workspace, key, "anything")

    assert attempt.degraded is True
    assert attempt.reason == "over_budget"


async def test_every_degradation_writes_exactly_one_audit_row(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    config.api_key = None
    await db_session.flush()

    await answer(db_session, workspace, key, "how do refunds work")

    rows = list(await db_session.scalars(sa.select(AiCall)))
    assert len(rows) == 1
    assert rows[0].outcome == AiOutcome.degraded
    assert rows[0].reason == "not_configured"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ai_answers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'relaydesk.services.ai_answers'`

- [ ] **Step 3: Write the implementation**

An `Attempt` object rather than a union of a generator and a sentinel: the
caller needs to know *before* it starts streaming whether there is anything
to stream, and a generator cannot say that without being started.

```python
# apps/api/src/relaydesk/services/ai_answers.py
"""One answer attempt, from question to citations, with every exit recorded.

The order here is the design. Retrieval gates the model; the budget gates
the call; the provider's failure and its refusal are the same outcome to a
visitor; and every path -- including the ones that never reach a provider --
writes exactly one ``AiCall`` row, because a deflection number computed from
a table with holes in it is worse than no number.

Every failure degrades to the widget that already works (spec D4). None of
them is an error, and none of them tells the visitor why: that a workspace
has exhausted its AI budget is not a visitor's business.
"""

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig
from relaydesk.models.widget_key import WidgetKey
from relaydesk.models.workspace import Workspace
from relaydesk.services import ai_budget, ai_redact, ai_retrieval
from relaydesk.services.ai_provider import Provider, ProviderUnavailable, for_config
from relaydesk.services.ai_retrieval import Source

SYSTEM = """You answer questions for {workspace} using only the numbered \
help articles below. If they do not contain the answer, say so plainly in \
one sentence and do not guess.

Cite every article you use as [n], matching its number. Never cite a number \
that is not listed. Keep the answer under 120 words.

{context}"""


@dataclass
class Attempt:
    """What came of one question.

    ``degraded`` is checked before streaming begins, which is why this is an
    object rather than a generator: a generator cannot report that there is
    nothing to stream without being started first.
    """

    degraded: bool
    reason: str | None = None
    stream: AsyncIterator[str] | None = None
    sources: list[Source] = field(default_factory=list)


async def _record(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    widget_key_id: uuid.UUID | None,
    *,
    model: str,
    outcome: AiOutcome,
    reason: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
) -> None:
    session.add(
        AiCall(
            workspace_id=workspace_id,
            widget_key_id=widget_key_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_micros=0,
            latency_ms=latency_ms,
            outcome=outcome,
            reason=reason,
        )
    )
    await session.flush()


async def answer(
    session: AsyncSession,
    workspace: Workspace,
    widget_key: WidgetKey,
    question: str,
    *,
    provider: Provider | None = None,
) -> Attempt:
    config = await session.get(AiConfig, workspace.id)
    model = config.model if config else "claude-opus-5"

    async def degrade(reason: str) -> Attempt:
        await _record(
            session,
            workspace.id,
            widget_key.id,
            model=model,
            outcome=AiOutcome.degraded,
            reason=reason,
        )
        return Attempt(degraded=True, reason=reason)

    if config is None:
        return await degrade("not_configured")

    resolved = provider or for_config(config)
    if resolved is None:
        return await degrade("not_configured")

    if not await ai_budget.within_budget(session, config):
        return await degrade("over_budget")

    sources = await ai_retrieval.retrieve(session, workspace.id, question)
    if not sources:
        return await degrade("no_sources")

    # Skipped when the workspace points at inference it hosts itself: the
    # text never leaves their deployment, and redacting it would cost
    # answer quality for nothing (spec D6).
    asked = question if config.base_url else ai_redact.redact(question)
    system = SYSTEM.format(
        workspace=workspace.name, context=ai_retrieval.render_context(sources)
    )

    started = time.monotonic()

    async def stream() -> AsyncIterator[str]:
        try:
            async for chunk in resolved.complete(
                system=system, question=asked, model=model
            ):
                yield chunk
        except ProviderUnavailable:
            await _record(
                session,
                workspace.id,
                widget_key.id,
                model=model,
                outcome=AiOutcome.degraded,
                reason="provider_unavailable",
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            await session.commit()
            return

        usage = resolved.usage()
        cited = ai_retrieval.resolve_citations(usage.text, sources)
        await _record(
            session,
            workspace.id,
            widget_key.id,
            model=model,
            outcome=AiOutcome.answered if cited else AiOutcome.refused,
            reason=None if cited else "no_citation",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        await session.commit()

    return Attempt(degraded=False, stream=stream(), sources=sources)
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_answers.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Add the provider-failure and success paths**

```python
# apps/api/tests/test_ai_answers.py — append
from relaydesk.services.ai_provider import FakeProvider


async def _publish(db_session, workspace):
    """One published article, so retrieval has something to find.

    Follow `tests/test_kb_public.py` if these constructors have moved; the
    requirement is only that the article is published and externally
    scoped, because `_visible()` is what retrieval filters on.
    """
    from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbScope

    category = KbCategory(
        workspace_id=workspace.id, name="Billing", slug="billing",
        scope=KbScope.external, position=0,
    )
    db_session.add(category)
    await db_session.flush()
    article = KbArticle(
        workspace_id=workspace.id, category_id=category.id,
        title="Requesting a refund", slug="refunds",
        excerpt="We refund any plan in full within 14 days of a charge.",
        status=ArticleStatus.published,
    )
    db_session.add(article)
    await db_session.flush()
    return article


async def test_a_provider_failure_mid_stream_is_recorded_and_silent(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    attempt = await answer(
        db_session, workspace, key, "refund", provider=FakeProvider(fails=True)
    )
    assert attempt.degraded is False  # retrieval succeeded; the failure is downstream
    assert [chunk async for chunk in attempt.stream] == []

    rows = list(await db_session.scalars(sa.select(AiCall)))
    assert len(rows) == 1
    assert rows[0].outcome == AiOutcome.degraded
    assert rows[0].reason == "provider_unavailable"


async def test_a_cited_answer_is_recorded_as_answered(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    attempt = await answer(
        db_session, workspace, key, "refund",
        provider=FakeProvider(chunks=["Within 14 days [1]."]),
    )
    text = "".join([chunk async for chunk in attempt.stream])

    assert "[1]" in text
    row = await db_session.scalar(sa.select(AiCall))
    assert row.outcome == AiOutcome.answered


async def test_an_uncited_answer_is_recorded_as_refused(db_session) -> None:
    """No citation means nothing to link, which is indistinguishable from not knowing."""
    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    attempt = await answer(
        db_session, workspace, key, "refund",
        provider=FakeProvider(chunks=["I am not sure."]),
    )
    [chunk async for chunk in attempt.stream]

    row = await db_session.scalar(sa.select(AiCall))
    assert row.outcome == AiOutcome.refused
    assert row.reason == "no_citation"

- [ ] **Step 6: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_answers.py -v`
Expected: PASS (7 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/services/ai_answers.py apps/api/tests/test_ai_answers.py
git commit -m "feat(ai): retrieval gates the model, and every exit is recorded"
```

---

### Task 8: `POST /widget/{key}/ask`

**Files:**
- Modify: `apps/api/src/relaydesk/api/widget.py`
- Modify: `apps/api/src/relaydesk/schemas/widget.py`
- Modify: `apps/api/src/relaydesk/config.py`
- Modify: `.env.example`, `docker-compose.yml`
- Test: `apps/api/tests/test_widget_ask.py`

**Interfaces:**
- Consumes: `ai_answers.answer` (Task 7), `widget_keys.resolve`, `ratelimit.check`.
- Produces: `POST /api/widget/{key}/ask`, streaming `text/event-stream`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_widget_ask.py
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_an_unconfigured_workspace_degrades_rather_than_erroring(
    client, db_session
) -> None:
    """A workspace with no AI must see the widget it already had, not a 500."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/ask", json={"question": "how do refunds work"}
    )

    assert response.status_code == 200
    assert "degraded" in response.text


async def test_an_unknown_key_is_refused_like_every_other_widget_route(
    client, db_session
) -> None:
    response = await client.post(
        "/api/widget/rdw_" + "0" * 32 + "/ask", json={"question": "hello"}
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_widget_ask.py -v`
Expected: FAIL — 404 on a route that does not exist

- [ ] **Step 3: Add the setting**

In `config.py`, beside the other widget caps:

```python
    widget_ask_hourly_cap: int = 20
```

In `.env.example`, beside `WIDGET_KEY_HOURLY_CAP`:

```
# Questions one embed may ask the model per hour. Lower than the ticket cap
# because each of these spends the workspace's money.
WIDGET_ASK_HOURLY_CAP=20
```

Add `WIDGET_ASK_HOURLY_CAP: ${WIDGET_ASK_HOURLY_CAP:-20}` to the `api` service's `environment` in `docker-compose.yml`, alongside the other caps.

- [ ] **Step 4: Add the schema and the route**

```python
# apps/api/src/relaydesk/schemas/widget.py — append (import Field from pydantic)
class WidgetAskTurn(CamelModel):
    role: str  # "visitor" | "assistant"
    text: str


class WidgetAskIn(CamelModel):
    question: str
    # The client-held transcript, resent each turn -- the server keeps no
    # session (spec D2). Bounded here rather than trusted: an unbounded
    # history is an unbounded bill, on an endpoint anyone can reach.
    history: list[WidgetAskTurn] = Field(default_factory=list, max_length=10)
```

```python
# apps/api/src/relaydesk/api/widget.py — declared ABOVE the {path:path} catch-all
@router.post("/{key}/ask")
async def ask(
    key: str, body: WidgetAskIn, session: DbSession, request: Request
) -> StreamingResponse:
    """Answer from the knowledge base, or say plainly that this degraded.

    Always 200 once the key resolves. Every failure inside is a degradation
    to the widget that already works (spec D4), not an error -- a visitor
    who asked a question should never see a stack trace, and a workspace
    that has not configured AI should see no change at all.
    """
    widget_key = await widget_keys.resolve(session, key)

    within = await ratelimit.check(
        session,
        "widget_ask",
        str(widget_key.id),
        limit=get_settings().widget_ask_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within:
        return _degraded("rate_limited")

    attempt = await ai_answers.answer(
        session, widget_key.workspace, widget_key, body.question.strip()
    )
    await session.commit()

    if attempt.degraded:
        return _degraded(attempt.reason or "unavailable")

    async def events() -> AsyncIterator[str]:
        assert attempt.stream is not None
        answer_text = ""
        async for chunk in attempt.stream:
            answer_text += chunk
            yield f"event: text\ndata: {json.dumps({'text': chunk})}\n\n"
        cited = ai_retrieval.resolve_citations(answer_text, attempt.sources)
        payload = {
            "outcome": "answered" if cited else "refused",
            "citations": [
                {"title": source.title, "path": source.path} for source in cited
            ],
        }
        yield f"event: done\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


def _degraded(reason: str) -> StreamingResponse:
    """One terminal event and nothing else.

    The reason travels for the audit's sake, and the panel ignores it: a
    visitor learning that a workspace has spent its AI budget is
    information they should not have.
    """

    async def once() -> AsyncIterator[str]:
        yield f"event: done\ndata: {json.dumps({'outcome': 'degraded'})}\n\n"

    return StreamingResponse(once(), media_type="text/event-stream")
```

Add the imports this needs at the top of `widget.py`: `json`, `AsyncIterator`
from `collections.abc`, `StreamingResponse` from `fastapi.responses`,
`ai_answers` and `ai_retrieval` from `relaydesk.services`, and `WidgetAskIn`
from `relaydesk.schemas.widget`.

- [ ] **Step 5: Run tests**

Run: `docker compose exec -T api pytest tests/test_widget_ask.py tests/test_widget_api.py -v`
Expected: PASS — including the existing widget routes, which must not regress

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/relaydesk/api/widget.py apps/api/src/relaydesk/schemas/widget.py apps/api/src/relaydesk/config.py .env.example docker-compose.yml apps/api/tests/test_widget_ask.py
git commit -m "feat(ai): ask the knowledge base, and degrade rather than fail"
```

---

### Task 9: The console screen for AI configuration

**Files:**
- Create: `apps/api/src/relaydesk/services/ai_configs.py`
- Create: `apps/api/src/relaydesk/schemas/ai_config.py`
- Create: `apps/api/src/relaydesk/api/ai_configs.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Create: `apps/web/app/(console)/settings/ai/page.tsx`
- Create: `apps/web/components/settings/ai-settings.tsx`
- Modify: `apps/web/components/console/sidebar.tsx`
- Test: `apps/api/tests/test_ai_configs_api.py`, `apps/web/components/settings/ai-settings.test.tsx`

**Interfaces:**
- Consumes: `AiConfig` (Task 1).
- Produces: `GET`/`PUT /api/ai-config`, admin-gated. `AiConfigOut` carries `provider`, `model`, `baseUrl`, `dailyTokenBudget`, `enabled`, and `keySuffix` — never `apiKey`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ai_configs_api.py
from relaydesk.models import Role
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


async def test_the_key_is_never_returned(client, db_session) -> None:
    """Write-only means write-only: a masked suffix, never the value."""
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    await client.put(
        "/api/ai-config",
        json={"enabled": True, "apiKey": "sk-ant-secret-tail1234"},
        headers=headers,
    )
    read = await client.get("/api/ai-config", headers=headers)

    assert read.status_code == 200
    assert "sk-ant-secret-tail1234" not in read.text
    assert read.json()["keySuffix"] == "1234"


async def test_an_agent_cannot_read_or_write_it(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await agent_headers(client, db_session, workspace)

    assert (await client.get("/api/ai-config", headers=headers)).status_code == 403
    assert (
        await client.put("/api/ai-config", json={"enabled": True}, headers=headers)
    ).status_code == 403


async def test_omitting_the_key_leaves_the_installed_one_alone(client, db_session) -> None:
    """Editing the budget must not silently discard the key."""
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    await client.put(
        "/api/ai-config", json={"enabled": True, "apiKey": "sk-keep-me-9999"}, headers=headers
    )

    await client.put("/api/ai-config", json={"dailyTokenBudget": 50_000}, headers=headers)
    read = await client.get("/api/ai-config", headers=headers)

    assert read.json()["keySuffix"] == "9999"
    assert read.json()["dailyTokenBudget"] == 50_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ai_configs_api.py -v`
Expected: FAIL — 404, the route does not exist

- [ ] **Step 3: Write the service, schema and routes**

```python
# apps/api/src/relaydesk/schemas/ai_config.py
from relaydesk.schemas.base import CamelModel


class AiConfigIn(CamelModel):
    provider: str | None = None
    model: str | None = None
    # Omitted leaves the installed key alone; sending "" clears it.
    api_key: str | None = None
    base_url: str | None = None
    daily_token_budget: int | None = None
    enabled: bool | None = None


class AiConfigOut(CamelModel):
    provider: str
    model: str
    base_url: str | None
    daily_token_budget: int
    enabled: bool
    # The last four characters, so an admin can tell which key is installed
    # without being handed it back. Never the key itself.
    key_suffix: str | None
```

```python
# apps/api/src/relaydesk/services/ai_configs.py
"""Reading and writing one workspace's model configuration.

The key is write-only throughout: ``get_or_create`` returns the row, and it
is the schema layer that refuses to serialise ``api_key``. Keeping that
refusal in one place -- ``AiConfigOut`` has no field for it -- is what stops
a future endpoint leaking it by accident.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models.ai_config import AiConfig


async def get_or_create(session: AsyncSession, workspace_id: uuid.UUID) -> AiConfig:
    config = await session.get(AiConfig, workspace_id)
    if config is None:
        config = AiConfig(workspace_id=workspace_id)
        session.add(config)
        await session.flush()
    return config


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    daily_token_budget: int | None = None,
    enabled: bool | None = None,
) -> AiConfig:
    config = await get_or_create(session, workspace_id)
    if provider is not None:
        config.provider = provider
    if model is not None:
        config.model = model.strip()
    if api_key is not None:
        # An empty string is how the console clears a key; omitting the
        # field entirely leaves the installed one alone.
        config.api_key = api_key.strip() or None
    if base_url is not None:
        config.base_url = base_url.strip() or None
    if daily_token_budget is not None:
        if daily_token_budget < 0:
            raise Invalid("A budget cannot be negative.")
        config.daily_token_budget = daily_token_budget
    if enabled is not None:
        config.enabled = enabled
    await session.flush()
    return config
```

```python
# apps/api/src/relaydesk/api/ai_configs.py
from fastapi import APIRouter

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models.ai_config import AiConfig
from relaydesk.schemas.ai_config import AiConfigIn, AiConfigOut
from relaydesk.services import ai_configs

router = APIRouter()


def _out(config: AiConfig) -> AiConfigOut:
    return AiConfigOut(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        daily_token_budget=config.daily_token_budget,
        enabled=config.enabled,
        key_suffix=config.api_key[-4:] if config.api_key else None,
    )


@router.get("", response_model=AiConfigOut)
async def read_route(scope: Scope, session: DbSession) -> AiConfigOut:
    scope.require_admin()
    config = await ai_configs.get_or_create(session, scope.workspace.id)
    await session.commit()
    return _out(config)


@router.put("", response_model=AiConfigOut)
async def write_route(
    body: AiConfigIn, scope: Scope, session: DbSession
) -> AiConfigOut:
    scope.require_admin()
    config = await ai_configs.update(
        session,
        scope.workspace.id,
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        daily_token_budget=body.daily_token_budget,
        enabled=body.enabled,
    )
    await session.commit()
    return _out(config)
```

Register in `api/router.py` beside the others:

```python
from relaydesk.api.ai_configs import router as ai_configs_router

api_router.include_router(ai_configs_router, prefix="/ai-config", tags=["ai"])
```

- [ ] **Step 4: Run the API tests**

Run: `docker compose exec -T api pytest tests/test_ai_configs_api.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Build the console screen**

```tsx
// apps/web/components/settings/ai-settings.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AiSettings } from "@/components/settings/ai-settings";

const base = {
  provider: "anthropic",
  model: "claude-opus-5",
  baseUrl: null,
  dailyTokenBudget: 200000,
  enabled: false,
  keySuffix: null,
};

describe("AiSettings", () => {
  it("says the widget keeps working when AI is off", () => {
    render(<AiSettings config={base} />);
    expect(screen.getByText(/search and the message form/i)).toBeTruthy();
  });

  it("shows which key is installed without showing the key", () => {
    render(<AiSettings config={{ ...base, enabled: true, keySuffix: "1234" }} />);
    expect(screen.getByText(/…1234/)).toBeTruthy();
  });
});
```

Build `AiSettings` following `components/settings/widget-keys.tsx` for house
style. It must carry two pieces of copy, because both are otherwise
surprises: **turning AI off leaves the widget working** — visitors get search
and the message form, not an error — and **the daily budget is a hard stop**,
after which the widget degrades silently for the rest of the day.

Add the page at `app/(console)/settings/ai/page.tsx` with `requireAdmin()`
following `settings/widget/page.tsx`, and a sidebar entry beside the Widget
one in `components/console/sidebar.tsx`.

- [ ] **Step 6: Run the web tests**

Run: `cd apps/web && pnpm vitest run components/settings/ai-settings.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/services/ai_configs.py apps/api/src/relaydesk/schemas/ai_config.py apps/api/src/relaydesk/api/ai_configs.py apps/api/src/relaydesk/api/router.py apps/api/tests/test_ai_configs_api.py apps/web/app/\(console\)/settings/ai apps/web/components/settings/ai-settings.tsx apps/web/components/settings/ai-settings.test.tsx apps/web/components/console/sidebar.tsx
git commit -m "feat(ai): configure a model without ever handing the key back"
```

---

### Task 10: The panel's conversation view

**Files:**
- Create: `apps/web/app/(widget)/widget/ask/route.ts`
- Create: `apps/web/components/widget/ask.tsx`
- Modify: `apps/web/components/widget/panel.tsx`
- Test: `apps/web/components/widget/ask.test.tsx`

**Interfaces:**
- Consumes: `POST /api/widget/{key}/ask` (Task 8).
- Produces: an `ask` view in `panel.tsx`'s state machine.

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/components/widget/ask.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Ask } from "@/components/widget/ask";

describe("Ask", () => {
  it("falls back to search and the form when the answer degrades", async () => {
    // Every AI failure must look like the widget that already works, not
    // like an error -- spec D4.
    const onDegrade = vi.fn();
    render(<Ask widgetKey="rdw_test" onDegrade={onDegrade} onCompose={() => {}} />);
    // Drive one question through a mocked fetch that yields only a
    // `done` event with outcome `degraded`, then:
    // expect(onDegrade).toHaveBeenCalled();
  });

  it("renders a citation as a link to the article", async () => {
    // Drive a mocked stream of one `text` event and a `done` event whose
    // citations carry {title, path}, then assert an anchor with that title
    // and an href ending in that path.
  });
});
```

Complete both tests by mocking `fetch` to return a `ReadableStream` of
SSE-framed bytes. `panel.test.tsx` already establishes how this project
drives a component through an async transition — follow it.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm vitest run components/widget/ask.test.tsx`
Expected: FAIL — cannot resolve `@/components/widget/ask`

- [ ] **Step 3: Build the route handler**

```typescript
// apps/web/app/(widget)/widget/ask/route.ts
import { NextRequest } from "next/server";

/**
 * The panel's question, proxied server-side and streamed straight through.
 *
 * `Ask` is a client component and this app's API client is `server-only`,
 * so every client-side call goes through a route like this one -- same as
 * `widget/kb/search/route.ts`. The body is passed on unchanged and the
 * upstream stream is returned as-is: nothing here interprets the events,
 * so a new event type needs no change on this hop.
 */
export async function POST(request: NextRequest) {
  const { key, question } = await request.json();
  if (!key || !question) return new Response(null, { status: 404 });

  const upstream = await fetch(
    `${process.env.API_URL ?? "http://api:8000"}/api/widget/${encodeURIComponent(key)}/ask`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
    },
  );

  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": "text/event-stream" },
  });
}
```

- [ ] **Step 4: Build `Ask` and wire it into the panel**

`Ask` holds the transcript in component state — nothing is persisted, and a
reload starts fresh (spec D2). It reads the SSE stream, appends `text`
events to the answer as they arrive, and on `done` either renders the
citations as links to `/help/{path}` on the workspace's portal, or calls
`onDegrade`.

`onDegrade` must land the panel on the existing `home` view, so a visitor
whose question could not be answered gets search and the message form rather
than an error. Add `ask` to `panel.tsx`'s `View` union and make it the
initial view when `articleCount > 0` and AI is configured; keep the existing
empty-KB rule from slice 8 untouched — `articleCount === 0` still opens
`compose` and never mounts a search field.

Keep the accessibility work slice 8 established: the answer region is
`aria-live="polite"`, and focus management is unchanged.

- [ ] **Step 5: Run tests**

Run: `cd apps/web && pnpm vitest run`
Expected: PASS — the whole web suite, since `panel.tsx` changed

- [ ] **Step 6: Run both suites**

Run: `docker compose exec -T api pytest` then `cd apps/web && pnpm vitest run`
Expected: API at the 11-failure baseline (12 if `test_imap_poll` is having a
GreenMail day); web green

- [ ] **Step 7: Commit**

```bash
git add apps/web/app/\(widget\)/widget/ask apps/web/components/widget/ask.tsx apps/web/components/widget/ask.test.tsx apps/web/components/widget/panel.tsx
git commit -m "feat(ai): the panel answers, and falls back to what already worked"
```

---

### Task 11: Escalation carries the transcript, and the circuit breaker

Spec D8 and the third control in D5. Both were missing from the tasks above;
this closes them.

**Files:**
- Modify: `apps/api/src/relaydesk/api/widget.py` (the existing `POST /{key}/tickets`)
- Modify: `apps/api/src/relaydesk/schemas/widget.py`
- Modify: `apps/api/src/relaydesk/services/ai_budget.py`
- Modify: `apps/web/components/widget/ask.tsx`, `apps/web/components/widget/compose.tsx`
- Test: `apps/api/tests/test_widget_ask.py`, `apps/api/tests/test_ai_budget.py`

**Interfaces:**
- Consumes: `AiCall`/`AiOutcome` (Task 2), `Attempt` (Task 7), the existing `tickets.submit`.
- Produces: `async breaker_open(session, workspace_id) -> bool`; an optional `transcript` form field on ticket submission.

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_ai_budget.py — append
from relaydesk.services.ai_budget import breaker_open


async def test_the_breaker_opens_after_repeated_provider_failures(db_session) -> None:
    """An outage must not become a retry storm billed to the customer."""
    workspace = await make_workspace(db_session)
    for _ in range(5):
        db_session.add(
            AiCall(
                workspace_id=workspace.id,
                model="claude-opus-5",
                input_tokens=0,
                output_tokens=0,
                cost_micros=0,
                latency_ms=1,
                outcome=AiOutcome.degraded,
                reason="provider_unavailable",
            )
        )
    await db_session.flush()

    assert await breaker_open(db_session, workspace.id) is True


async def test_other_degradations_do_not_open_the_breaker(db_session) -> None:
    """A workspace with no key configured is not an outage."""
    workspace = await make_workspace(db_session)
    for _ in range(5):
        db_session.add(
            AiCall(
                workspace_id=workspace.id,
                model="claude-opus-5",
                input_tokens=0,
                output_tokens=0,
                cost_micros=0,
                latency_ms=1,
                outcome=AiOutcome.degraded,
                reason="not_configured",
            )
        )
    await db_session.flush()

    assert await breaker_open(db_session, workspace.id) is False
```

```python
# apps/api/tests/test_widget_ask.py — append
import sqlalchemy as sa

from relaydesk.models.message import Message
from relaydesk.models.conversation import Conversation


async def test_a_resolved_question_writes_no_conversation(client, db_session) -> None:
    """An inbox full of questions the AI answered is a triage problem."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    await client.post(f"/api/widget/{key.key}/ask", json={"question": "refund"})

    count = await db_session.scalar(
        sa.select(sa.func.count()).select_from(Conversation)
    )
    assert count == 0


async def test_an_escalated_question_carries_its_transcript(client, db_session) -> None:
    """The agent must see what the visitor was already told."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={
            "email": "wren@lantern.co",
            "message": "This did not help.",
            "transcript": "Visitor: how do refunds work\nAssistant: Within 14 days.",
        },
    )
    assert response.status_code == 201

    body = await db_session.scalar(sa.select(Message.body))
    assert "how do refunds work" in body
    assert "This did not help." in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/test_ai_budget.py tests/test_widget_ask.py -v`
Expected: FAIL — `breaker_open` does not exist; the ticket route ignores `transcript`

- [ ] **Step 3: Add the breaker**

```python
# apps/api/src/relaydesk/services/ai_budget.py — append
BREAKER_THRESHOLD = 5
BREAKER_WINDOW = timedelta(minutes=15)


async def breaker_open(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    """Whether recent provider failures should stop us calling out again.

    Counts only ``provider_unavailable``. A workspace that has not
    configured a key degrades on every request by design, and treating that
    as an outage would mean a breaker permanently open on a workspace that
    never had a provider to begin with.

    Closes on its own when the window rolls forward: there is no half-open
    probe because the next question after the window *is* the probe, and a
    visitor waiting on one is a cheaper test than a background job.
    """
    since = datetime.now(UTC) - BREAKER_WINDOW
    failures = await session.scalar(
        sa.select(sa.func.count())
        .select_from(AiCall)
        .where(
            AiCall.workspace_id == workspace_id,
            AiCall.reason == "provider_unavailable",
            AiCall.created_at >= since,
        )
    )
    return int(failures or 0) >= BREAKER_THRESHOLD
```

In `ai_answers.answer`, check it immediately after the budget check:

```python
    if await ai_budget.breaker_open(session, workspace.id):
        return await degrade("breaker_open")
```

- [ ] **Step 4: Carry the transcript into the ticket**

In `api/widget.py`'s existing `submit` route, add an optional form field
beside `company`:

```python
    transcript: Annotated[str, Form()] = "",
```

and prepend it to the message body before calling `tickets.submit`:

```python
    # The agent must see what the visitor was already told. Answering a
    # question the AI has already answered differently is worse than never
    # having answered it (spec D8).
    body = message
    if transcript.strip():
        body = f"{message}\n\n--- Before contacting support ---\n{transcript.strip()}"
```

then pass `message=body`. Cap the transcript at 4000 characters and truncate
rather than refuse — a visitor who has had a long conversation and then needs
a human must not be blocked by their own transcript.

- [ ] **Step 5: Send it from the panel**

In `ask.tsx`, when the visitor escalates, pass the transcript to `Compose`;
in `compose.tsx`, include it as a hidden `transcript` field on the
submission. An escalation with no prior conversation sends nothing, and the
ticket looks exactly as it does today.

- [ ] **Step 6: Run tests**

Run: `docker compose exec -T api pytest tests/test_ai_budget.py tests/test_widget_ask.py tests/test_widget_tickets.py -v`
Expected: PASS — including the existing ticket tests, which must not regress

- [ ] **Step 7: Run both suites**

Run: `docker compose exec -T api pytest` then `cd apps/web && pnpm vitest run`
Expected: API at the 11-failure baseline; web green

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/relaydesk/services/ai_budget.py apps/api/src/relaydesk/services/ai_answers.py apps/api/src/relaydesk/api/widget.py apps/api/src/relaydesk/schemas/widget.py apps/api/tests/test_ai_budget.py apps/api/tests/test_widget_ask.py apps/web/components/widget/ask.tsx apps/web/components/widget/compose.tsx
git commit -m "feat(ai): the agent sees what the visitor was already told"
```
