# Password Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user who has forgotten their password recover their account through a single-use link mailed only to their own address, and give every system email a shared HTML layout on the way.

**Architecture:** A `password_resets` table shaped like `invites` — a hashed, short-lived, mailed capability. `services/password_reset.py` holds the two halves (`request`, `confirm`); two unauthenticated routes on the existing `/api/auth` router expose them; a new `services/mail_templates.py` renders one HTML layout that all three system emails go through. Nothing about the mail transport changes — this rides on the SMTP path slice 2 built.

**Tech Stack:** FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 / pydantic-settings, argon2 via `security/passwords.py`, pytest + httpx `AsyncClient`, Next.js App Router (React server + client components), Tailwind.

**Spec:** `docs/superpowers/specs/2026-09-07-password-reset-design.md`

## Global Constraints

- **Python:** the API is async end to end. Service functions are `async def` taking `session: AsyncSession` as the first positional argument.
- **Password minimum is 8 characters**, expressed as `Annotated[str, Field(min_length=8)]`. Reuse it; do not restate the number anywhere else.
- **Token discipline:** `security.tokens.generate_token()` for the secret, `security.tokens.hash_token()` for what persists. The plaintext token may appear in exactly two places — the return value of `generate_token()` and the body of one email. Never in a response body, a log line, a database column, a URL path, or a query string.
- **The reset link uses a URL fragment:** `{web_url}/reset-password#{token}`. A fragment is never sent to any server, so it cannot reach an access log.
- **Uniform response:** `POST /api/auth/password-reset` returns `202` with an empty body for every input, including rate-limited ones. Never `429`, never a distinguishing message.
- **Rate-limit keys come from `services.client_ip.resolve(request)`**, never `api.deps.client_ip`. See Task 5.
- **`ratelimit.check` commits.** Call it before any write that might otherwise want to roll back.
- **Errors:** services raise from `relaydesk.errors`; routers map them. Do not raise `HTTPException` in a service.
- **Test naming:** files are `apps/api/tests/test_<area>.py`, tests are `async def test_<sentence>(...)`, and they use the `db_session`, `client`, and `outbox` fixtures from `conftest.py`.
- **Run tests with:** `docker compose exec api pytest -m "not integration"`. Lint with `docker compose exec api ruff check .` and `docker compose exec web pnpm lint`.
- **Migrations** are hand-numbered sequentially (`0014_...`), with a prose docstring explaining *why* the table exists, matching `0012_rate_limits.py`.
- **Commit style:** lowercase conventional prefix, imperative subject, a body explaining the reasoning that is not obvious from the diff.

---

### Task 1: The `password_resets` table

**Files:**
- Create: `apps/api/src/relaydesk/models/password_reset.py`
- Create: `apps/api/migrations/versions/0014_password_resets.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py` (import and `__all__`)
- Modify: `apps/api/src/relaydesk/config.py` (three settings)
- Modify: `.env.example` (three settings)
- Test: `apps/api/tests/test_password_reset_model.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `relaydesk.models.PasswordReset` with fields `id`, `user_id`, `token_hash`, `expires_at`, `created_at`, `updated_at`. Settings `password_reset_ttl_minutes: int = 60`, `password_reset_ip_hourly_cap: int = 5`, `password_reset_email_hourly_cap: int = 3`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_password_reset_model.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.config import get_settings
from relaydesk.models import PasswordReset, User
from relaydesk.security.tokens import generate_token, hash_token
from tests.factories import make_member, make_workspace


async def test_a_reset_row_round_trips(db_session) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    token = generate_token()

    row = PasswordReset(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(row)
    await db_session.flush()

    found = await db_session.scalar(
        sa.select(PasswordReset).where(PasswordReset.token_hash == hash_token(token))
    )
    assert found is not None
    assert found.user_id == user.id
    # The plaintext is not what was stored -- only its digest.
    assert found.token_hash != token


async def test_two_rows_cannot_share_a_token_hash(db_session) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    digest = hash_token(generate_token())

    db_session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=digest,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db_session.flush()

    db_session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=digest,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_the_user_takes_the_reset_with_it(db_session) -> None:
    """A live capability must never outlive the account it unlocks."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    db_session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=hash_token(generate_token()),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db_session.flush()

    await db_session.execute(sa.delete(User).where(User.id == user.id))
    await db_session.flush()

    remaining = await db_session.scalar(
        sa.select(sa.func.count()).select_from(PasswordReset)
    )
    assert remaining == 0


def test_the_reset_settings_have_defaults() -> None:
    settings = get_settings()
    assert settings.password_reset_ttl_minutes == 60
    assert settings.password_reset_ip_hourly_cap == 5
    assert settings.password_reset_email_hourly_cap == 3
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec api pytest tests/test_password_reset_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'PasswordReset' from 'relaydesk.models'`

- [ ] **Step 3: Create the model**

Create `apps/api/src/relaydesk/models/password_reset.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class PasswordReset(UUIDMixin, TimestampMixin, Base):
    """A single-use capability to set one user's password.

    Shaped like ``invites`` because it is the same kind of object: a
    short-lived secret that is mailed, hashed at rest, and consumed once.

    No ``email`` column. The row points at a user and the address is read
    from that user when the mail is composed; storing a second copy would
    let the two disagree after an address change.

    ``ON DELETE CASCADE`` so deleting a user cannot leave a live capability
    pointing at an account that no longer exists.
    """

    __tablename__ = "password_resets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
```

- [ ] **Step 4: Export the model**

In `apps/api/src/relaydesk/models/__init__.py`, add the import next to the other model imports (keep alphabetical order — it goes after `models.membership`, before `models.message`):

```python
from relaydesk.models.password_reset import PasswordReset
```

and add `"PasswordReset",` to `__all__` in alphabetical position (after `"Message"`-group entries, before `"PollState"`).

- [ ] **Step 5: Add the settings**

In `apps/api/src/relaydesk/config.py`, directly below `login_lockout_minutes: int = 15`:

```python
    # A reset link is a password in transit. One hour is long enough to
    # find the mail and short enough that a link left sitting in an inbox
    # or a mail archive stops being useful quickly.
    password_reset_ttl_minutes: int = 60
    # Both caps are deliberately low. They are what bounds the residual
    # timing channel documented in section 6.2 of the design: telling two
    # addresses apart through a noisy timing difference needs repeated
    # samples per address, and these deny the sample volume.
    password_reset_ip_hourly_cap: int = 5
    password_reset_email_hourly_cap: int = 3
```

In `.env.example`, below `SESSION_TTL_DAYS=30`:

```
PASSWORD_RESET_TTL_MINUTES=60
PASSWORD_RESET_IP_HOURLY_CAP=5
PASSWORD_RESET_EMAIL_HOURLY_CAP=3
```

- [ ] **Step 6: Write the migration**

Create `apps/api/migrations/versions/0014_password_resets.py`:

```python
"""password resets

Adds ``password_resets``, the single-use capability behind the forgot-password
flow. Before this table the only path that ever set a password was
``accept_invite``, so a user who forgot theirs needed an operator with
database access.

``token_hash`` is unique and is all that persists -- the plaintext exists
only in the email. A consumed row is deleted rather than flagged, so a
replayed token is indistinguishable from one that never existed; there is
deliberately no ``consumed_at`` column to preserve evidence that a given
token was once valid.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-07 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_password_resets_user_id", "password_resets", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_password_resets_user_id", table_name="password_resets")
    op.drop_table("password_resets")
```

**Check the `created_at`/`updated_at` column definitions against `TimestampMixin` in `apps/api/src/relaydesk/db/base.py` and match it exactly** — if the mixin differs from what is written above, the mixin wins, and an earlier migration such as `0011_knowledge_base.py` shows the established form.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/test_password_reset_model.py -v`
Expected: PASS, 4 tests.

The suite recreates and re-migrates the test database each session, so the new migration is exercised by running any test at all.

- [ ] **Step 8: Verify the whole suite and lint still pass**

Run: `docker compose exec api pytest -m "not integration" -q && docker compose exec api ruff check .`
Expected: PASS, no lint findings.

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/relaydesk/models/password_reset.py \
        apps/api/src/relaydesk/models/__init__.py \
        apps/api/src/relaydesk/config.py \
        apps/api/migrations/versions/0014_password_resets.py \
        apps/api/tests/test_password_reset_model.py \
        .env.example
git commit -m "feat(api): add the password_resets table

Shaped like invites because it is the same kind of object: a short-lived
secret that is mailed, hashed at rest, and consumed once. No email column,
so the address cannot drift from the user's. ON DELETE CASCADE so a live
capability cannot outlive the account it unlocks.

No consumed_at column, deliberately: a deleted row makes a replayed token
indistinguishable from one that never existed, which is what read_invite
already does and for the same reason."
```

---

### Task 2: One shared HTML layout for every system email

**Files:**
- Create: `apps/api/src/relaydesk/services/mail_templates.py`
- Modify: `apps/api/src/relaydesk/services/notifications.py` (both existing notifiers)
- Modify: `apps/api/tests/conftest.py:104-112` (the `outbox` fixture)
- Test: `apps/api/tests/test_mail_templates.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `mail_templates.render(*, heading: str, paragraphs: Sequence[str], action_label: str | None = None, action_url: str | None = None) -> tuple[str, str]` returning `(text, html)`. The `outbox` fixture entries gain an `"html"` key.

**Why this comes before the reset flow:** it puts the layout under test before a security-sensitive flow depends on it, and it is independent of every other task.

**Note on wording:** the two existing text constants embed their URL mid-body (`"Accept the invitation: {url}"`). Converting them to `paragraphs` + `action_url` moves the URL to the end of the text part. This is a deliberate, small change and keeps one source of truth for both parts. Every existing assertion still holds — `test_invites.py` asserts `"/invites#" in outbox[0]["text"]`, which remains true.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_mail_templates.py`:

```python
from relaydesk.services import mail_templates


def test_the_text_part_carries_the_paragraphs_and_the_action() -> None:
    text, _ = mail_templates.render(
        heading="Reset your password",
        paragraphs=["Somebody asked to reset it.", "The link expires in 60 minutes."],
        action_label="Choose a new password",
        action_url="http://localhost:3000/reset-password#abc",
    )

    assert "Somebody asked to reset it." in text
    assert "The link expires in 60 minutes." in text
    assert "Choose a new password: http://localhost:3000/reset-password#abc" in text
    # The heading is an HTML affordance; the subject line is the text
    # part's heading, so repeating it here would just read as a stutter.
    assert "Reset your password" not in text
    assert "<p" not in text


def test_the_html_part_shows_the_url_as_text_as_well_as_a_link() -> None:
    """A client that strips links must still leave the user a usable URL."""
    _, html = mail_templates.render(
        heading="Reset your password",
        paragraphs=["Somebody asked to reset it."],
        action_label="Choose a new password",
        action_url="http://localhost:3000/reset-password#abc",
    )

    assert 'href="http://localhost:3000/reset-password#abc"' in html
    assert html.count("http://localhost:3000/reset-password#abc") >= 2
    assert "<h1" in html
    assert "Reset your password" in html


def test_the_html_part_escapes_its_content() -> None:
    _, html = mail_templates.render(
        heading="Join Ben & Co",
        paragraphs=["<script>alert(1)</script> invited you."],
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Ben &amp; Co" in html


def test_the_html_part_pulls_in_nothing_from_the_network() -> None:
    """No remote images, no web fonts, no tracking pixel: a mail client that
    blocks remote content must render this identically, and Relaydesk must
    not learn whether a reset mail was opened."""
    _, html = mail_templates.render(
        heading="Reset your password",
        paragraphs=["Somebody asked to reset it."],
        action_label="Choose a new password",
        action_url="http://localhost:3000/reset-password#abc",
    )

    assert "<img" not in html
    assert "<style" not in html
    assert "@import" not in html
    assert "url(" not in html


def test_an_action_is_optional() -> None:
    text, html = mail_templates.render(
        heading="Assigned to you",
        paragraphs=["Nilesh assigned a conversation to you."],
    )

    assert "Nilesh assigned a conversation to you." in text
    assert "<a " not in html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec api pytest tests/test_mail_templates.py -v`
Expected: FAIL — `ImportError: cannot import name 'mail_templates'`

- [ ] **Step 3: Write the renderer**

Create `apps/api/src/relaydesk/services/mail_templates.py`:

```python
"""The one HTML layout every system email uses.

Constraints, all chosen so the mail arrives and so it does not look like a
phishing attempt:

* Inline styles only. Gmail strips ``<style>`` blocks, so a layout that
  depends on one renders unstyled for a large share of recipients.
* Nothing loaded from the network -- no images, no web fonts, no tracking
  pixel. A client that blocks remote content must render this identically,
  and Relaydesk has no business learning whether a password-reset mail was
  opened.
* The action URL is shown as text as well as wrapped in a link, because a
  client that strips links must still leave the reader something usable.

The text part is generated from the same ``paragraphs`` the HTML part uses,
rather than kept as a separate constant, so the two cannot drift into
saying different things.
"""

from collections.abc import Sequence
from html import escape

_WRAPPER = (
    "margin:0;padding:24px;background-color:#f5f5f4;"
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;"
)
_CARD = (
    "max-width:520px;margin:0 auto;padding:32px;background-color:#ffffff;"
    "border:1px solid #e7e5e4;border-radius:12px;"
)
_HEADING = (
    "margin:0 0 16px;font-size:20px;line-height:28px;font-weight:600;color:#1c1917;"
)
_PARAGRAPH = "margin:0 0 16px;font-size:15px;line-height:24px;color:#44403c;"
_BUTTON = (
    "display:inline-block;padding:10px 18px;background-color:#1c1917;color:#ffffff;"
    "font-size:15px;font-weight:500;text-decoration:none;border-radius:8px;"
)
_FALLBACK = "margin:16px 0 0;font-size:13px;line-height:20px;color:#78716c;"
_FOOTER = (
    "max-width:520px;margin:16px auto 0;font-size:12px;line-height:18px;color:#a8a29e;"
)


def render(
    *,
    heading: str,
    paragraphs: Sequence[str],
    action_label: str | None = None,
    action_url: str | None = None,
) -> tuple[str, str]:
    """Return ``(text, html)`` for one system email.

    ``heading`` is rendered in the HTML part only. The text part's heading
    is the message's subject line, so repeating it in the body reads as a
    stutter.
    """
    lines = list(paragraphs)
    if action_label and action_url:
        lines.append(f"{action_label}: {action_url}")
    text = "\n\n".join(lines) + "\n"

    body = "".join(
        f'<p style="{_PARAGRAPH}">{escape(paragraph)}</p>' for paragraph in paragraphs
    )
    action = ""
    if action_label and action_url:
        safe_url = escape(action_url, quote=True)
        action = (
            f'<p style="{_PARAGRAPH}">'
            f'<a href="{safe_url}" style="{_BUTTON}">{escape(action_label)}</a>'
            f"</p>"
            f'<p style="{_FALLBACK}">'
            f"If the button does not work, paste this into your browser:<br />"
            f"{escape(action_url)}"
            f"</p>"
        )

    html = (
        f'<div style="{_WRAPPER}">'
        f'<div style="{_CARD}">'
        f'<h1 style="{_HEADING}">{escape(heading)}</h1>'
        f"{body}{action}"
        f"</div>"
        f'<p style="{_FOOTER}">Relaydesk</p>'
        f"</div>"
    )
    return text, html
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/test_mail_templates.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Teach the `outbox` fixture about HTML**

In `apps/api/tests/conftest.py`, replace the `record` function inside the `outbox` fixture:

```python
    def record(to: str, subject: str, text_body: str, html_body=None) -> None:
        sent.append(
            {"to": to, "subject": subject, "text": text_body, "html": html_body}
        )
```

- [ ] **Step 6: Write the failing test for the two existing emails**

First extend the imports at the **top** of `apps/api/tests/test_mail_templates.py` — ruff rejects a module-level import further down the file (E402):

```python
from relaydesk.services import mail_templates, notifications
from tests.factories import make_conversation, make_member, make_workspace
```

Then append the tests:

```python
def test_an_invite_email_has_both_parts(outbox) -> None:
    notifications.notify_invite(
        email="sara@example.com",
        token="tok",
        workspace_name="Chronon",
        inviter_name="Nilesh Pant",
    )

    assert len(outbox) == 1
    assert "Nilesh Pant invited you to join Chronon" in outbox[0]["text"]
    # Still a fragment, still not a path segment.
    assert "/invites#tok" in outbox[0]["text"]
    assert "/invites/tok" not in outbox[0]["text"]
    assert outbox[0]["html"] is not None
    assert "/invites#tok" in outbox[0]["html"]


async def test_an_assignment_email_has_both_parts(db_session, outbox) -> None:
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    assignee = await make_member(
        db_session, workspace, email="sara@example.com", name="Sara Vidal"
    )
    conversation = await make_conversation(db_session, workspace)
    await db_session.refresh(conversation, ["contact"])

    notifications.notify_assignment(conversation, assignee, actor)

    assert len(outbox) == 1
    assert outbox[0]["to"] == "sara@example.com"
    assert outbox[0]["html"] is not None
    assert "<h1" in outbox[0]["html"]
```

- [ ] **Step 7: Run them to verify they fail**

Run: `docker compose exec api pytest tests/test_mail_templates.py -v`
Expected: FAIL on the two new tests — `outbox[0]["html"]` is `None`, because nothing passes an `html_body` yet.

- [ ] **Step 8: Rewire the two existing notifiers**

Rewrite `apps/api/src/relaydesk/services/notifications.py` so both notifiers build their bodies through `mail_templates.render`. Replace the two module-level text constants and both function bodies:

```python
from relaydesk.config import get_settings
from relaydesk.models.conversation import Conversation
from relaydesk.models.user import User
from relaydesk.services import mail_templates, queue
from relaydesk.services.team import INVITE_TTL


def notify_assignment(
    conversation: Conversation, assignee: User, actor: User
) -> None:
    """Fire-and-forget. Never raises into the caller's request: an email that
    fails to enqueue must not fail the assignment itself."""
    if assignee.id == actor.id or not assignee.notify_on_assignment:
        return

    customer = conversation.contact.name if conversation.contact else "a customer"
    url = f"{get_settings().web_url}/conversations/{conversation.id}"
    text, html = mail_templates.render(
        heading="Assigned to you",
        paragraphs=[
            f"{actor.name} assigned a conversation to you.",
            f"{conversation.subject}\nFrom {customer}",
        ],
        action_label="Open it",
        action_url=url,
    )
    queue.enqueue_system_email(
        to=assignee.email,
        subject=f"Assigned to you: {conversation.subject}",
        text_body=text,
        html_body=html,
    )


def notify_invite(
    email: str, token: str, workspace_name: str, inviter_name: str
) -> None:
    """The token is delivered here and nowhere else — never in a response
    body, never in a log line.

    The token goes in the URL *fragment* (``#token``), not a path segment or
    query string: a fragment is never sent to any server, including the web
    app's own, so it never reaches an access log. ``/invites/{token}`` as a
    path segment was the mistake this replaces — see the block comment on
    the invite routes in ``relaydesk.api.team``.
    """
    url = f"{get_settings().web_url}/invites#{token}"
    text, html = mail_templates.render(
        heading=f"Join {workspace_name}",
        paragraphs=[
            f"{inviter_name} invited you to join {workspace_name} on Relaydesk.",
            f"This link expires in {INVITE_TTL.days} days. If you weren't "
            "expecting it, ignore this message — no account is created until "
            "you accept.",
        ],
        action_label="Accept the invitation",
        action_url=url,
    )
    queue.enqueue_system_email(
        to=email,
        subject=f"Join {workspace_name} on Relaydesk",
        text_body=text,
        html_body=html,
    )
```

- [ ] **Step 9: Run the full suite**

Run: `docker compose exec api pytest -m "not integration" -q`
Expected: PASS. If `test_invites.py` or `test_assignment_notifications.py` assert on exact body wording rather than substrings, update those assertions to match the new text — the URL now sits at the end of the body. Do not weaken an assertion that is checking the fragment (`/invites#`); that one must keep passing as written.

- [ ] **Step 10: Lint**

Run: `docker compose exec api ruff check .`
Expected: no findings.

- [ ] **Step 11: Commit**

```bash
git add apps/api/src/relaydesk/services/mail_templates.py \
        apps/api/src/relaydesk/services/notifications.py \
        apps/api/tests/test_mail_templates.py \
        apps/api/tests/conftest.py
git commit -m "feat(api): give system email a shared HTML layout

mailer.build has promoted messages to multipart/alternative since slice 2
and send_system_email has forwarded an html_body just as long -- nothing
ever passed one, so every system email went out as bare text.

One layout for all three, generated from the same paragraphs as the text
part so the two cannot drift. Inline styles only (Gmail strips <style>),
and nothing loaded from the network: no images, no web fonts, no tracking
pixel. A client that blocks remote content renders it identically, and
Relaydesk does not learn whether a reset mail was opened.

The action URL moves to the end of the text body as a consequence of
having one source for both parts. It is still a fragment."
```

---

### Task 3: Requesting a reset

**Files:**
- Create: `apps/api/src/relaydesk/services/password_reset.py`
- Modify: `apps/api/src/relaydesk/services/notifications.py` (add `notify_password_reset`)
- Test: `apps/api/tests/test_password_reset_request.py`

**Interfaces:**
- Consumes: `models.PasswordReset` (Task 1); `mail_templates.render` (Task 2).
- Produces: `password_reset.request(session: AsyncSession, email: str, ip_bucket: str) -> None` and `notifications.notify_password_reset(email: str, name: str, token: str) -> None`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_password_reset_request.py`:

```python
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from relaydesk.models import PasswordReset, User
from relaydesk.security.tokens import hash_token
from relaydesk.services import password_reset
from tests.factories import make_member, make_workspace

IP = "203.0.113.9"


async def _member(db_session, **kwargs) -> User:
    workspace = await make_workspace(db_session)
    return await make_member(db_session, workspace, **kwargs)


async def test_a_request_mails_a_token_that_matches_the_stored_hash(
    db_session, outbox
) -> None:
    user = await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    await password_reset.request(db_session, "nilesh@example.com", IP)

    assert len(outbox) == 1
    assert outbox[0]["to"] == "nilesh@example.com"
    assert "/reset-password#" in outbox[0]["text"]

    token = outbox[0]["text"].split("/reset-password#")[1].split()[0]
    row = await db_session.scalar(
        sa.select(PasswordReset).where(PasswordReset.token_hash == hash_token(token))
    )
    assert row is not None
    assert row.user_id == user.id
    # The plaintext never lands in the row.
    assert token not in row.token_hash


async def test_an_unknown_address_sends_nothing(db_session, outbox) -> None:
    await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    await password_reset.request(db_session, "nobody@example.com", IP)

    assert outbox == []
    assert await db_session.scalar(
        sa.select(sa.func.count()).select_from(PasswordReset)
    ) == 0


async def test_a_google_only_account_gets_no_mail(db_session, outbox) -> None:
    """Decision D1. Such an account has never had a password and its root of
    trust is Google; a reset would mint one from mailbox control alone. The
    caller cannot tell -- the route answers 202 either way (Task 5)."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="sara@example.com")
    user.password_hash = None
    await db_session.commit()

    await password_reset.request(db_session, "sara@example.com", IP)

    assert outbox == []


async def test_a_user_with_no_active_membership_gets_no_mail(
    db_session, outbox
) -> None:
    """auth.default_membership refuses them, so a working link would lead
    somewhere they still cannot go."""
    user = User(
        email="orphan@example.com",
        name="Orphan",
        monogram="OR",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$notarealhash",
    )
    db_session.add(user)
    await db_session.commit()

    await password_reset.request(db_session, "orphan@example.com", IP)

    assert outbox == []


async def test_a_second_request_invalidates_the_first_token(
    db_session, outbox
) -> None:
    """Decision D4. Four clicks must not leave four live links in four
    separate emails."""
    await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    await password_reset.request(db_session, "nilesh@example.com", IP)
    await password_reset.request(db_session, "nilesh@example.com", IP)

    assert len(outbox) == 2
    rows = (await db_session.scalars(sa.select(PasswordReset))).all()
    assert len(rows) == 1

    second = outbox[1]["text"].split("/reset-password#")[1].split()[0]
    assert rows[0].token_hash == hash_token(second)


async def test_the_row_expires_within_the_configured_ttl(db_session, outbox) -> None:
    await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    await password_reset.request(db_session, "nilesh@example.com", IP)

    row = await db_session.scalar(sa.select(PasswordReset))
    assert row is not None
    assert row.expires_at <= datetime.now(UTC) + timedelta(minutes=61)
    assert row.expires_at > datetime.now(UTC) + timedelta(minutes=55)


async def test_the_address_cap_stops_the_fourth_request(db_session, outbox) -> None:
    await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    for _ in range(4):
        await password_reset.request(db_session, "nilesh@example.com", IP)

    assert len(outbox) == 3


async def test_the_ip_cap_covers_several_addresses(db_session, outbox) -> None:
    """The address cap alone would let one host walk a list of addresses,
    three mails each."""
    workspace = await make_workspace(db_session)
    for index in range(6):
        await make_member(db_session, workspace, email=f"user{index}@example.com")
    await db_session.commit()

    for index in range(6):
        await password_reset.request(db_session, f"user{index}@example.com", IP)

    assert len(outbox) == 5


async def test_two_ip_buckets_do_not_share_an_allowance(db_session, outbox) -> None:
    """The regression test for keying on the wrong client_ip helper: behind
    the web container every caller shares one peer address, so a limiter
    keyed on the peer gives the whole deployment five resets an hour."""
    workspace = await make_workspace(db_session)
    for index in range(12):
        await make_member(db_session, workspace, email=f"user{index}@example.com")
    await db_session.commit()

    for index in range(6):
        await password_reset.request(db_session, f"user{index}@example.com", IP)
    for index in range(6, 12):
        await password_reset.request(db_session, f"user{index}@example.com", "198.51.100.4")

    assert len(outbox) == 10
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec api pytest tests/test_password_reset_request.py -v`
Expected: FAIL — `ImportError: cannot import name 'password_reset'`

- [ ] **Step 3: Add the notifier**

Append to `apps/api/src/relaydesk/services/notifications.py`:

```python
def notify_password_reset(email: str, name: str, token: str) -> None:
    """The reset token is delivered here and nowhere else.

    Same fragment rule as ``notify_invite``, and for the same reason: a URL
    fragment is never transmitted to any server, so the token cannot reach
    uvicorn's access log, a proxy log, or a ``Referer`` header. Putting it
    in a path segment or a query string is the mistake that rule exists to
    prevent, and it is available again here.
    """
    settings = get_settings()
    url = f"{settings.web_url}/reset-password#{token}"
    text, html = mail_templates.render(
        heading="Reset your password",
        paragraphs=[
            f"Hi {name},",
            "Somebody asked to reset the password for this Relaydesk account.",
            f"The link expires in {settings.password_reset_ttl_minutes} minutes "
            "and can be used once. If it wasn't you, ignore this message — "
            "your password has not changed.",
        ],
        action_label="Choose a new password",
        action_url=url,
    )
    queue.enqueue_system_email(
        to=email,
        subject="Reset your Relaydesk password",
        text_body=text,
        html_body=html,
    )
```

- [ ] **Step 4: Write the request service**

Create `apps/api/src/relaydesk/services/password_reset.py`:

```python
"""Forgot-password: issue a capability, and spend it.

Every path through ``request`` returns ``None``, including the ones that do
nothing. The caller cannot tell an unknown address from a real one, a
Google-only account from a password account, or a refused rate limit from
an accepted request -- the route answers 202 for all of them.

That uniformity is the primary enumeration defense, and it is not
complete: the path that sends mail does two writes and a broker publish
that the silent paths do not, which is measurable in principle. It is not
equalized with dummy work. The ``_DUMMY_PASSWORD_HASH`` trick in
``services.auth`` works there because the asymmetry is one argon2 call,
cheap and exact to pay unconditionally; here it would mean writing rows
nobody reads on a path an attacker triggers, which is a worse thing to own
than the channel it closes. The rate limits below are the mitigation:
distinguishing two addresses through a noisy timing difference needs
repeated samples per address, and three per hour per address denies them.
See section 6.2 of the design.
"""

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.models.membership import Membership, MembershipStatus
from relaydesk.models.password_reset import PasswordReset
from relaydesk.models.user import User
from relaydesk.security.tokens import generate_token, hash_token
from relaydesk.services import notifications, ratelimit

WINDOW = timedelta(hours=1)


async def request(session: AsyncSession, email: str, ip_bucket: str) -> None:
    settings = get_settings()
    address = email.strip().lower()

    # Both limits are charged before anything is written. `ratelimit.check`
    # commits, so it has to come before any write this function might
    # otherwise want to roll back -- the ordering `api.public` documents at
    # its own call site.
    #
    # The IP bucket is charged first and returns on refusal without
    # touching the address bucket. Charging both would let a caller who has
    # already exhausted their own IP allowance keep burning down the
    # allowance of any address they name, which turns a rate limit into a
    # denial-of-service against a chosen user.
    within_ip = await ratelimit.check(
        session,
        "password_reset_ip",
        ip_bucket,
        limit=settings.password_reset_ip_hourly_cap,
        window=WINDOW,
    )
    if not within_ip:
        return

    within_address = await ratelimit.check(
        session,
        "password_reset_email",
        address,
        limit=settings.password_reset_email_hourly_cap,
        window=WINDOW,
    )
    if not within_address:
        return

    user = await session.scalar(sa.select(User).where(User.email == address))
    if user is None:
        return

    # Decision D1: an account that has never had a password is a Google
    # account, and its root of trust is Google. Minting a password from
    # mailbox control alone would convert it into a password account
    # without its owner doing anything.
    if user.password_hash is None:
        return

    # `auth.default_membership` refuses a user with no active membership,
    # so a working link would lead somewhere they still cannot go.
    membership = await session.scalar(
        sa.select(Membership).where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.active,
        )
    )
    if membership is None:
        return

    # Decision D4: one live token per user. Without this, a user who clicks
    # the button four times has four valid links sitting in four separate
    # emails, and each extra copy is another chance for one to leak.
    await session.execute(
        sa.delete(PasswordReset).where(PasswordReset.user_id == user.id)
    )
    token = generate_token()
    session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.password_reset_ttl_minutes),
        )
    )
    await session.commit()

    notifications.notify_password_reset(user.email, user.name, token)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/test_password_reset_request.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 6: Run the full suite and lint**

Run: `docker compose exec api pytest -m "not integration" -q && docker compose exec api ruff check .`
Expected: PASS, no findings.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/services/password_reset.py \
        apps/api/src/relaydesk/services/notifications.py \
        apps/api/tests/test_password_reset_request.py
git commit -m "feat(api): issue password reset tokens

Every path returns None, including the ones that do nothing: an unknown
address, a Google-only account (D1), and a user with no active membership
are all silent, so the route can answer 202 for everything.

Two rate limits, IP first. The IP bucket returning early without charging
the address bucket is deliberate -- charging both would let a caller who
has burned their own allowance keep burning down the allowance of any
address they name, which is a denial of service against a chosen user.

The module docstring states the residual timing channel rather than
implying the uniform response closes it."
```

---

### Task 4: Confirming a reset, and the slice 1 amendment

**Files:**
- Modify: `apps/api/src/relaydesk/services/password_reset.py` (add `confirm`)
- Modify: `apps/api/src/relaydesk/services/team.py:277` (docstring correction, amendment A1)
- Test: `apps/api/tests/test_password_reset_confirm.py`

**Interfaces:**
- Consumes: `password_reset.request` (Task 3) to mint tokens in tests.
- Produces: `password_reset.confirm(session: AsyncSession, token: str, password: str) -> None`, raising `errors.NotFound(INVALID_LINK)`. Module constant `password_reset.INVALID_LINK: str`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_password_reset_confirm.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from relaydesk.errors import NotFound
from relaydesk.models import PasswordReset, Session as SessionRow
from relaydesk.security.passwords import verify_password
from relaydesk.services import auth, password_reset
from tests.factories import make_member, make_workspace

IP = "203.0.113.9"


async def _issue(db_session, outbox, email="nilesh@example.com") -> str:
    await password_reset.request(db_session, email, IP)
    return outbox[-1]["text"].split("/reset-password#")[1].split()[0]


async def test_confirming_sets_the_new_password(db_session, outbox) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    token = await _issue(db_session, outbox)

    await password_reset.confirm(db_session, token, "a-brand-new-password")

    await db_session.refresh(user)
    assert verify_password("a-brand-new-password", user.password_hash)


async def test_confirming_consumes_the_token(db_session, outbox) -> None:
    """Decision D3: the row is deleted, so a replay is indistinguishable
    from a token that never existed."""
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    token = await _issue(db_session, outbox)

    await password_reset.confirm(db_session, token, "a-brand-new-password")

    assert await db_session.scalar(
        sa.select(sa.func.count()).select_from(PasswordReset)
    ) == 0

    with pytest.raises(NotFound) as replayed:
        await password_reset.confirm(db_session, token, "another-password")

    with pytest.raises(NotFound) as never_existed:
        await password_reset.confirm(db_session, "not-a-real-token", "another-password")

    assert str(replayed.value) == str(never_existed.value)


async def test_an_expired_token_is_refused(db_session, outbox) -> None:
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    token = await _issue(db_session, outbox)

    row = await db_session.scalar(sa.select(PasswordReset))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(NotFound):
        await password_reset.confirm(db_session, token, "a-brand-new-password")


async def test_confirming_clears_the_login_lockout(db_session, outbox) -> None:
    """A user who forgot their password and one guessing at it look the same
    to authenticate(), so the user most likely to need a reset is
    disproportionately likely to have tripped the lockout getting here.
    Leaving it set means a correct new password is still refused, with the
    same message, for fifteen minutes."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    user.failed_login_count = 5
    user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db_session.commit()
    token = await _issue(db_session, outbox)

    await password_reset.confirm(db_session, token, "a-brand-new-password")

    await db_session.refresh(user)
    assert user.failed_login_count == 0
    assert user.locked_until is None

    signed_in = await auth.authenticate(
        db_session, "nilesh@example.com", "a-brand-new-password"
    )
    assert signed_in.id == user.id


async def test_confirming_revokes_every_session(db_session, outbox) -> None:
    """Decision D5. If the reset answered a compromise, not revoking means
    the attacker's session survives the exact action taken to evict them --
    for up to session_ttl_days, which defaults to 30."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    membership = await auth.default_membership(db_session, user)
    first, _ = await auth.create_session(db_session, user, membership)
    second, _ = await auth.create_session(db_session, user, membership)
    assert await db_session.scalar(
        sa.select(sa.func.count()).select_from(SessionRow)
    ) == 2

    token = await _issue(db_session, outbox)
    await password_reset.confirm(db_session, token, "a-brand-new-password")

    assert await db_session.scalar(
        sa.select(sa.func.count()).select_from(SessionRow)
    ) == 0
    for stale in (first, second):
        with pytest.raises(Exception):
            await auth.resolve_session(db_session, stale)


async def test_one_users_reset_does_not_touch_another(db_session, outbox) -> None:
    workspace = await make_workspace(db_session)
    nilesh = await make_member(db_session, workspace, email="nilesh@example.com")
    sara = await make_member(
        db_session, workspace, email="sara@example.com", name="Sara Vidal"
    )
    await db_session.commit()

    sara_membership = await auth.active_membership(db_session, sara, workspace.id)
    await auth.create_session(db_session, sara, sara_membership)
    sara_hash = sara.password_hash

    token = await _issue(db_session, outbox)
    await password_reset.confirm(db_session, token, "a-brand-new-password")

    await db_session.refresh(sara)
    assert sara.password_hash == sara_hash
    remaining = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(SessionRow)
        .where(SessionRow.user_id == sara.id)
    )
    assert remaining == 1
    assert nilesh.id != sara.id
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec api pytest tests/test_password_reset_confirm.py -v`
Expected: FAIL — `AttributeError: module 'relaydesk.services.password_reset' has no attribute 'confirm'`

- [ ] **Step 3: Write `confirm`**

Add to `apps/api/src/relaydesk/services/password_reset.py`. Extend the imports at the top:

```python
from relaydesk.errors import NotFound
from relaydesk.models.session import Session
from relaydesk.security.passwords import hash_password
```

and append:

```python
INVALID_LINK = "This reset link is not valid."


async def confirm(session: AsyncSession, token: str, password: str) -> None:
    """Spend a reset token.

    A missing row and an expired one raise the same message, per decision
    D3: a consumed row is deleted, so there is nothing left to distinguish
    a replay from a token that never existed, and no reason to confirm to a
    caller that a given token used to be valid.
    """
    row = await session.scalar(
        sa.select(PasswordReset).where(PasswordReset.token_hash == hash_token(token))
    )
    if row is None or row.expires_at <= datetime.now(UTC):
        raise NotFound(INVALID_LINK)

    user = await session.get(User, row.user_id)
    if user is None:
        raise NotFound(INVALID_LINK)

    user.password_hash = hash_password(password)

    # Forgetting a password and guessing at one are the same activity from
    # `authenticate`'s point of view, so the user most likely to arrive
    # here is disproportionately likely to have tripped the five-attempt
    # lockout on the way. Leaving it set produces the worst outcome
    # available: a correct, just-chosen password refused with the same
    # BAD_CREDENTIALS message for the next fifteen minutes.
    user.failed_login_count = 0
    user.locked_until = None

    await session.delete(row)

    # Decision D5. This logs the user out of devices they are using
    # happily, which is a real cost on a flow reached through simple
    # forgetfulness. It is paid because the server cannot tell that case
    # from a compromise, and the two are asymmetric: forgetfulness costs a
    # few sign-ins with a password the user just chose, whereas not
    # revoking lets an attacker's session survive the exact action taken to
    # evict them -- for up to `session_ttl_days`, which defaults to 30.
    await session.execute(sa.delete(Session).where(Session.user_id == user.id))

    await session.commit()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/test_password_reset_confirm.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Apply amendment A1 to `accept_invite`'s docstring**

In `apps/api/src/relaydesk/services/team.py`, inside `accept_invite`'s docstring, find the sentence ending:

```
      real invitee's typed password has to win, because there is no
      password-reset flow to recover from it losing.
```

Replace that clause so the paragraph reads:

```
      real invitee's typed password has to win: nobody else is relying on
      the row, and the alternative silently discards what they typed.
```

Then add, as a new paragraph immediately after the two bullets:

```
    Slice 5 added a password-reset flow (see
    ``docs/superpowers/specs/2026-09-07-password-reset-design.md``). An
    earlier version of this docstring justified the adoption above partly
    on there being no way to recover from the wrong password winning. That
    is no longer true, and it was never the load-bearing reason — the
    squatting defense below is. The behaviour is unchanged.
```

- [ ] **Step 6: Confirm the amendment broke nothing**

Run: `docker compose exec api pytest -m "not integration" -q && docker compose exec api ruff check .`
Expected: PASS, no findings.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/services/password_reset.py \
        apps/api/src/relaydesk/services/team.py \
        apps/api/tests/test_password_reset_confirm.py
git commit -m "feat(api): spend a password reset token

Confirming sets the password, clears the login lockout, deletes the row,
and revokes every session for that user.

Clearing the lockout is not incidental: forgetting a password and guessing
at one are the same activity to authenticate(), so the user most likely to
arrive here has probably tripped the five-attempt lock on the way, and
leaving it set refuses their correct new password with the same message
for fifteen minutes.

Revoking sessions costs a user their other devices on a flow they may have
reached through plain forgetfulness. Paid because the server cannot tell
that from a compromise and the two are asymmetric -- not revoking lets an
attacker's session outlive the eviction by up to session_ttl_days.

Amends slice 1: accept_invite's docstring justified adopting unclaimed
rows partly on there being no password-reset flow. Behaviour unchanged,
rationale corrected."
```

---

### Task 5: The two routes

**Files:**
- Modify: `apps/api/src/relaydesk/schemas/auth.py` (two schemas)
- Modify: `apps/api/src/relaydesk/api/auth.py` (two routes)
- Test: `apps/api/tests/test_password_reset_api.py`

**Interfaces:**
- Consumes: `password_reset.request` (Task 3), `password_reset.confirm` (Task 4).
- Produces: `POST /api/auth/password-reset` → `202`; `POST /api/auth/password-reset/confirm` → `204`. Schemas `PasswordResetRequest` (`email`) and `PasswordResetConfirm` (`token`, `password`).

The `/auth` prefix is already registered in `api/router.py:18`, so no router wiring is needed.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_password_reset_api.py`:

```python
import sqlalchemy as sa

from relaydesk.models import RateLimitHit
from relaydesk.security.passwords import verify_password
from tests.factories import make_member, make_workspace, sign_in


async def test_every_address_gets_the_same_answer(db_session, client, outbox) -> None:
    """The whole enumeration defense: a real address, an unknown one and a
    Google-only one must be indistinguishable from outside."""
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    google_only = await make_member(
        db_session, workspace, email="sara@example.com", name="Sara Vidal"
    )
    google_only.password_hash = None
    await db_session.commit()

    answers = []
    for address in ("nilesh@example.com", "nobody@example.com", "sara@example.com"):
        response = await client.post(
            "/api/auth/password-reset", json={"email": address}
        )
        answers.append((response.status_code, response.text))

    assert answers[0] == answers[1] == answers[2]
    assert answers[0][0] == 202
    # Only the real password account was mailed.
    assert len(outbox) == 1
    assert outbox[0]["to"] == "nilesh@example.com"


async def test_the_response_never_carries_the_token(db_session, client, outbox) -> None:
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    response = await client.post(
        "/api/auth/password-reset", json={"email": "nilesh@example.com"}
    )

    assert response.status_code == 202
    assert response.text.strip() == ""
    token = outbox[0]["text"].split("/reset-password#")[1].split()[0]
    assert token not in response.text


async def test_a_rate_limited_request_still_answers_202(
    db_session, client, outbox
) -> None:
    """A 429 is itself a signal, and one an attacker can provoke against a
    chosen address."""
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    statuses = []
    for _ in range(5):
        response = await client.post(
            "/api/auth/password-reset", json={"email": "nilesh@example.com"}
        )
        statuses.append(response.status_code)

    assert statuses == [202, 202, 202, 202, 202]
    assert len(outbox) == 3


async def test_the_limiter_keys_on_the_forwarded_client_not_the_peer(
    db_session, client, outbox, monkeypatch
) -> None:
    """Behind the web container every request arrives from one peer. Keyed
    on the peer, the whole deployment would share a single five-per-hour
    bucket. This is the regression test for using api.deps.client_ip here."""
    from relaydesk.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "trusted_proxy_ips", "127.0.0.1")

    workspace = await make_workspace(db_session)
    for index in range(2):
        await make_member(db_session, workspace, email=f"user{index}@example.com")
    await db_session.commit()

    await client.post(
        "/api/auth/password-reset",
        json={"email": "user0@example.com"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    await client.post(
        "/api/auth/password-reset",
        json={"email": "user1@example.com"},
        headers={"X-Forwarded-For": "198.51.100.4"},
    )

    keys = (
        await db_session.scalars(
            sa.select(RateLimitHit.key).where(RateLimitHit.bucket == "password_reset_ip")
        )
    ).all()
    assert set(keys) == {"203.0.113.9", "198.51.100.4"}


async def test_confirming_through_the_api_changes_the_password(
    db_session, client, outbox
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    await client.post("/api/auth/password-reset", json={"email": "nilesh@example.com"})
    token = outbox[0]["text"].split("/reset-password#")[1].split()[0]

    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "a-brand-new-password"},
    )

    assert response.status_code == 204
    await db_session.refresh(user)
    assert verify_password("a-brand-new-password", user.password_hash)

    headers = await sign_in(
        client, db_session, "nilesh@example.com", "a-brand-new-password"
    )
    assert "Authorization" in headers


async def test_a_short_password_is_refused(db_session, client, outbox) -> None:
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    await client.post("/api/auth/password-reset", json={"email": "nilesh@example.com"})
    token = outbox[0]["text"].split("/reset-password#")[1].split()[0]

    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "short"},
    )

    assert response.status_code == 422


async def test_an_unknown_token_is_a_404(db_session, client) -> None:
    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "password": "a-brand-new-password"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec api pytest tests/test_password_reset_api.py -v`
Expected: FAIL — every request 404s; the routes do not exist.

- [ ] **Step 3: Add the schemas**

Append to `apps/api/src/relaydesk/schemas/auth.py`:

```python
class PasswordResetRequest(CamelModel):
    email: EmailStr


class PasswordResetConfirm(CamelModel):
    token: str
    # The same minimum as accepting an invite (`schemas.team`), which is the
    # only other way a password is ever set. Stated by reference rather than
    # by a second literal so the two cannot drift apart.
    password: Annotated[str, Field(min_length=8)]
```

`Annotated` and `Field` are already imported at the top of the file; `EmailStr` is too.

- [ ] **Step 4: Add the routes**

In `apps/api/src/relaydesk/api/auth.py`, extend the imports:

```python
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
```

```python
from relaydesk.schemas.auth import (
    GoogleExchangeRequest,
    GoogleUrlResponse,
    LoginRequest,
    MembershipOut,
    MePatch,
    MeResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserOut,
    WorkspaceOut,
)
```

```python
from relaydesk.services import auth, client_ip, password_reset, workspaces
```

Note the existing `from relaydesk.api.deps import DbSession, Scope, bearer_token, client_ip` line already binds the name `client_ip` to the *dependency*. Rename the service import to avoid the collision and to make the choice explicit:

```python
from relaydesk.services import client_ip as ip_buckets
```

Then add the routes after `logout`:

```python
@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    payload: PasswordResetRequest, request: Request, session: DbSession
) -> Response:
    """Always 202, with an empty body, for every input.

    An unknown address, a Google-only account, a user with no membership
    and a caller over the rate limit are all answered identically — a 429
    would itself be a signal, and one an attacker can provoke deliberately
    against a chosen address.

    The rate-limit key comes from ``services.client_ip.resolve``, not the
    ``api.deps.client_ip`` dependency this module already imports. They are
    different values and only one of them is a limiter key: ``deps`` returns
    the immediate peer, which is correct for the ``sessions.ip`` record it
    fills in on login, but the browser reaches this API through the Next
    server, so as a bucket it puts every user on earth in one. Five resets
    per hour for the whole deployment, refusing the sixth real person
    because five others already asked, with nothing logged and nothing
    raised. ``resolve`` honours ``X-Forwarded-For`` only from a peer in
    ``TRUSTED_PROXY_IPS`` and buckets IPv6 on its /64.
    """
    await password_reset.request(
        session, str(payload.email), ip_buckets.resolve(request)
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: PasswordResetConfirm, session: DbSession
) -> Response:
    """No session is minted here.

    Unlike ``accept_invite``, which signs the new member in because their
    token proved possession of an address that had no account yet, a reset
    ends at the login page: the user has just chosen a password, and
    signing in with it is what confirms it works.
    """
    await password_reset.confirm(session, payload.token, payload.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose exec api pytest tests/test_password_reset_api.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 6: Run the full suite and lint**

Run: `docker compose exec api pytest -m "not integration" -q && docker compose exec api ruff check .`
Expected: PASS, no findings.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/relaydesk/api/auth.py \
        apps/api/src/relaydesk/schemas/auth.py \
        apps/api/tests/test_password_reset_api.py
git commit -m "feat(api): expose the password reset routes

POST /auth/password-reset answers 202 with an empty body for every input,
including one the rate limiter refused: a 429 is itself a signal, and one
an attacker can provoke against a chosen address.

The limiter keys on services.client_ip.resolve, not the api.deps.client_ip
dependency this module already imports. deps returns the immediate peer,
which is right for the sessions.ip record it fills on login and wrong as a
bucket -- behind the web container it would give the whole deployment five
resets an hour. There is a regression test for exactly that."
```

---

### Task 6: The web pages

**Files:**
- Create: `apps/web/lib/api/password-reset.ts`
- Create: `apps/web/app/(auth)/forgot-password/actions.ts`
- Create: `apps/web/app/(auth)/forgot-password/page.tsx`
- Create: `apps/web/app/(auth)/reset-password/actions.ts`
- Create: `apps/web/app/(auth)/reset-password/page.tsx`
- Modify: `apps/web/app/(auth)/login/page.tsx:84` (repoint the existing link)

**Interfaces:**
- Consumes: the two routes from Task 5.
- Produces: nothing later tasks depend on.

**Do not add these paths to `middleware.ts`.** Its `matcher` is an allowlist and `/invites` is deliberately absent from it for the same reason — a signed-out user must be able to reach these pages. Adding them would redirect the user to login, which is where they came from.

- [ ] **Step 1: Write the API client**

Create `apps/web/lib/api/password-reset.ts`:

```typescript
import "server-only";

import { apiFetch } from "./client";

/**
 * Reached without a session -- whoever is asking cannot sign in, which is
 * the point -- so `auth: false` is deliberate rather than an oversight.
 *
 * Always resolves. The API answers 202 for every address, so there is
 * nothing here to branch on and nothing to report back that would not
 * itself say whether the address has an account.
 */
export async function requestPasswordReset(email: string): Promise<void> {
  await apiFetch<void>("/auth/password-reset", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email }),
  });
}

/**
 * The token travels in the request body, never a path or query parameter,
 * which is what would otherwise land it verbatim in an access log. Same
 * rule as the invite routes.
 */
export async function confirmPasswordReset(
  token: string,
  password: string,
): Promise<void> {
  await apiFetch<void>("/auth/password-reset/confirm", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ token, password }),
  });
}
```

Check `apps/web/lib/api/client.ts` for how `apiFetch` handles a `204`/`202` with an empty body. If it unconditionally parses JSON, use whatever the codebase's existing no-content convention is — `apps/web/lib/api/channels.ts` has a `DELETE` returning `204` and shows the established form.

- [ ] **Step 2: Write the forgot-password action**

Create `apps/web/app/(auth)/forgot-password/actions.ts`:

```typescript
"use server";

import { requestPasswordReset } from "@/lib/api/password-reset";

/**
 * Returns nothing and reports nothing. The API answers 202 for every
 * address; surfacing anything else here — an error, a "no such account",
 * even a different spinner duration — would reintroduce the enumeration
 * oracle the API is careful not to be.
 */
export async function requestPasswordResetAction(email: string): Promise<void> {
  await requestPasswordReset(email);
}
```

- [ ] **Step 3: Write the forgot-password page**

Create `apps/web/app/(auth)/forgot-password/page.tsx`:

```tsx
"use client";

import { useState, useTransition } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { requestPasswordResetAction } from "./actions";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [isPending, startTransition] = useTransition();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    startTransition(async () => {
      await requestPasswordResetAction(email.trim());
      // Shown whatever the address was. See the action's comment.
      setSent(true);
    });
  }

  if (sent) {
    return (
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-lg font-semibold text-ink-900">Check your email</h1>
        <p className="text-sm text-ink-600">
          If that address has a Relaydesk account with a password, we have sent
          it a link to choose a new one. The link expires in an hour.
        </p>
        <Link
          href="/login"
          className="inline-block text-sm font-medium text-ink-900 underline underline-offset-4"
        >
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="w-full max-w-sm space-y-4">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-ink-900">Reset your password</h1>
        <p className="text-sm text-ink-600">
          We will email you a link to choose a new one.
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="email" className="text-sm">
          Email
        </Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <Button type="submit" variant="primary" size="lg" className="w-full" disabled={isPending}>
        {isPending ? "Sending…" : "Send the link"}
      </Button>
      <Link
        href="/login"
        className="block text-sm font-medium text-ink-900 underline underline-offset-4"
      >
        Back to sign in
      </Link>
    </form>
  );
}
```

Match the class names and the `Button`/`Input`/`Label` props against `apps/web/app/(auth)/login/page.tsx` — that file is the reference for this layout, and its variants are the ones that exist.

- [ ] **Step 4: Write the reset-password action**

Create `apps/web/app/(auth)/reset-password/actions.ts`:

```typescript
"use server";

import { ApiError } from "@/lib/api/client";
import { confirmPasswordReset } from "@/lib/api/password-reset";

export type ConfirmResult =
  | { ok: true }
  | { ok: false; invalid: true }
  | { ok: false; invalid: false; message: string };

/**
 * The token lives only in the URL fragment (see page.tsx), so the client
 * component passes it as a plain argument — never a query string — keeping
 * it out of this request's own URL too.
 */
export async function confirmPasswordResetAction(
  token: string,
  password: string,
): Promise<ConfirmResult> {
  try {
    await confirmPasswordReset(token, password);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) return { ok: false, invalid: true };
      return { ok: false, invalid: false, message: error.message };
    }
    throw error;
  }
}
```

- [ ] **Step 5: Write the reset-password page**

Create `apps/web/app/(auth)/reset-password/page.tsx`:

```tsx
"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { confirmPasswordResetAction } from "./actions";

/**
 * The reset link is `{web_url}/reset-password#<token>` -- the token lives in
 * the URL fragment, which browsers never send to any server, so uvicorn's
 * access log never sees it. That only holds if this page reads the fragment
 * itself: a Server Component cannot see it at all, so this has to be a
 * client component, and the token has to stay out of every link and every
 * rendered string from here on. Same rule as app/invites/page.tsx.
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  // Starts null on both the server render and the client's first
  // (hydrating) render -- neither has read the fragment yet, so they agree.
  // Reading window.location.hash during render would desync hydration.
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    setToken(window.location.hash.slice(1) || null);
    setReady(true);
  }, []);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError(null);
    startTransition(async () => {
      const result = await confirmPasswordResetAction(token, password);
      if (result.ok) {
        // No session is minted by the reset, so this ends at sign-in.
        router.push("/login");
        return;
      }
      setError(
        result.invalid
          ? "This link is no longer valid. Ask for a new one."
          : result.message,
      );
    });
  }

  if (!ready) return null;

  if (!token) {
    return (
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-lg font-semibold text-ink-900">
          This link is not valid
        </h1>
        <p className="text-sm text-ink-600">
          It may have expired or already been used.
        </p>
        <Link
          href="/forgot-password"
          className="inline-block text-sm font-medium text-ink-900 underline underline-offset-4"
        >
          Ask for a new link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="w-full max-w-sm space-y-4">
      <h1 className="text-lg font-semibold text-ink-900">Choose a new password</h1>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      <div className="space-y-2">
        <Label htmlFor="password" className="text-sm">
          New password
        </Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="text-xs text-ink-500">At least 8 characters.</p>
      </div>
      <Button type="submit" variant="primary" size="lg" className="w-full" disabled={isPending}>
        {isPending ? "Saving…" : "Save and sign in"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 6: Repoint the existing "Forgot password?" link**

`apps/web/app/(auth)/login/page.tsx:84` already renders a "Forgot password?" link pointing at `/contact` — a placeholder from before this flow existed. Change that `href` to `/forgot-password`. Leave the link's classes and text alone.

- [ ] **Step 7: Lint and build**

Run: `docker compose exec web pnpm lint && docker compose exec web pnpm build`
Expected: both pass.

- [ ] **Step 8: Walk the flow by hand**

With the stack up:

1. Go to `http://localhost:3000/login` and click "Forgot password?" — it should land on `/forgot-password`, not `/contact`.
2. Submit the seeded address `nilesh@relaydesk.dev`.
3. Open GreenMail's inbox to read the mail — `docker compose logs -f worker` confirms the send, and the message is readable through the GreenMail service configured in `docker-compose.yml`. Confirm the mail renders with the HTML layout and that the link is `…/reset-password#<token>`.
4. Open the link, set a new password of at least 8 characters, and confirm it redirects to `/login`.
5. Sign in with the new password.
6. Submit an address that has no account and confirm the page says exactly the same thing as it did in step 2.

- [ ] **Step 9: Commit**

```bash
git add apps/web/lib/api/password-reset.ts \
        "apps/web/app/(auth)/forgot-password" \
        "apps/web/app/(auth)/reset-password" \
        "apps/web/app/(auth)/login/page.tsx"
git commit -m "feat(web): add the forgot and reset password pages

The reset page reads its token from the URL fragment, which means it has to
be a client component -- a Server Component cannot see a fragment at all.
Same constraint and same reason as app/invites/page.tsx.

The forgot page shows one confirmation whatever was typed, and its server
action reports nothing back: the API answers 202 for every address, and
surfacing anything else here would reintroduce the enumeration oracle the
API is careful not to be.

Neither path goes in middleware.ts. Its matcher is an allowlist and a
signed-out user has to be able to reach both.

The login page's Forgot password? link pointed at /contact, from before
there was anywhere better to send someone."
```

---

### Task 7: Document the flow

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing.

- [ ] **Step 1: Add a README section**

In `README.md`, after the "Team invites are sent by email…" paragraph in **Project status**, add:

```markdown
A user who forgets their password can recover it themselves: **Forgot
password?** on the sign-in page mails a single-use link that expires in an
hour. Like invites, the link is only ever mailed to the address it belongs
to, so this also requires SMTP to be configured — the development stack
provides it through GreenMail.

Two behaviours are deliberate and will look like bugs otherwise:

- **The page says the same thing whatever you type.** A different answer
  for an address that has no account would turn the form into a way to
  discover who has one.
- **An account that only signs in with Google gets no reset mail**, and is
  told no differently. Such an account has never had a password and its
  root of trust is Google; minting one from mailbox control alone would
  convert it into a password account without its owner doing anything. A
  Google-only user who loses Google access needs an operator — see
  `relaydesk bootstrap`.

Completing a reset signs the user out everywhere. If the reset was the
answer to a compromise, leaving the other sessions alive would let the
attacker outlast the eviction by up to `SESSION_TTL_DAYS`.
```

Then, in the **Self-hosting your own workspace** area or wherever settings are listed, note the three new environment variables alongside their defaults:

```markdown
`PASSWORD_RESET_TTL_MINUTES` (default 60), `PASSWORD_RESET_IP_HOURLY_CAP`
(default 5) and `PASSWORD_RESET_EMAIL_HOURLY_CAP` (default 3) bound the
flow. The caps are low on purpose: they are what makes the timing
difference between "this address has an account" and "it does not"
impractical to measure, since the uniform response does not by itself
erase it.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: describe the password reset flow

Documents the two behaviours that read as bugs without the reasoning: one
answer for every address, and no mail at all for a Google-only account."
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| 5 Data model | 1 |
| 6 Requesting (order, silent paths) | 3 |
| 6.1 Rate limits, correct IP helper | 3 (service), 5 (route + regression test) |
| 6.2 Timing residual, stated | 3 (module docstring) |
| 7 Confirming, lockout, session revocation | 4 |
| 8 API surface, 202/204, no session minted | 5 |
| 9 Notifications, fragment, shared layout | 2, 3 |
| 3 / A1 amendment | 4 |
| 11 Web changes | 6 |
| 12 Security | distributed; each property has a named test |
| 13 Testing | every listed case appears in Tasks 1–5 |
| 14 Build order | Tasks follow it, with A1 folded into Task 4 |
| 10 Next slice (SMTP findings) | none — recorded in the spec, deliberately not built |

**Type consistency:** `render(*, heading, paragraphs, action_label, action_url) -> tuple[str, str]` is defined in Task 2 and called with those exact keywords in Tasks 2 and 3. `password_reset.request(session, email, ip_bucket)` is defined in Task 3 and called with three positional arguments in Tasks 4, 5. `password_reset.confirm(session, token, password)` is defined in Task 4 and called in Task 5. `notifications.notify_password_reset(email, name, token)` is defined in Task 3 and called there. `INVALID_LINK` is defined in Task 4 and used in its tests only.

**Known follow-ups, deliberately out of scope:** the `Session` model import in Task 4 shadows nothing but sits next to a parameter named `session`; `services/auth.py` already does this and the plan follows it rather than diverging. Old `password_resets` rows are never swept — unlike `rate_limit_hits` there is no beat job for them, and one live row per user bounds the table at the user count, so a sweep would be work with no growth to prevent.
