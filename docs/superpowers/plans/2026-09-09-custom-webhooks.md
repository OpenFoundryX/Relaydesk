# Custom webhooks — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A workspace can register a described HTTP endpoint as a tool, and an admin can fire a signed test request at it from the console and see what came back.

**Architecture:** Three services with no knowledge of each other — `url_guard` (pure, decides whether a URL may be dispatched to), `webhook_dispatch` (takes a model instance and an argument dict, signs, sends, returns a value), and `webhooks` (CRUD over the table). A thin admin-only router composes them. The console follows the existing api-keys pair: a server-only `lib/api` module plus a `"use server"` actions file.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, httpx, pytest/pytest-asyncio; Next.js App Router, React 19, TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-09-custom-webhooks-design.md`

## Global Constraints

- Every route is admin-only via `scope.require_admin()`; a row in another workspace is `NotFound`, never `Forbidden` (slice-1 isolation contract).
- Console request/response schemas inherit `CamelModel` — snake_case in Python, camelCase on the wire.
- Services raise `relaydesk.errors` types (`Invalid` 422, `NotFound` 404, `TooManyRequests` 429); routers do not translate.
- Enum columns use `Enum(..., native_enum=False, create_constraint=True)` — a CHECK constraint, not a Postgres enum type.
- Webhook name pattern: `^[a-z][a-z0-9_]{0,63}$`. Secret format: `whsec_` + `generate_token()`. Signature header: `Relaydesk-Signature: t=<unix>,v1=<hex>`; id header: `Relaydesk-Webhook-Id`.
- Signed payload is exactly `{timestamp}.{method}.{full_url}.{body}` (D4). The empty body is `""`.
- Dispatch: `https` only unless `RELAYDESK_WEBHOOK_ALLOW_PRIVATE=true`, no redirects, 10s timeout, 64 KiB read cap, 4 KiB stored body.
- Test-invoke limit: 60 per workspace per hour, bucket `webhook_test`, charged before dispatch.
- Migration head is `0021`; the new revision is `0022`.

**Running the suite** (Postgres runs in docker compose; the venv is local):

```bash
cd apps/api
DATABASE_URL=postgresql+asyncpg://relaydesk:relaydesk@localhost:5432/relaydesk \
  .venv/bin/python -m pytest tests/test_url_guard.py -q
```

---

## File structure

| File | Responsibility |
|---|---|
| `apps/api/src/relaydesk/services/url_guard.py` | **Create.** Decide whether a URL may be dispatched to. Pure + DNS. |
| `apps/api/src/relaydesk/models/webhook.py` | **Create.** The `Webhook` row and `WebhookMethod`. |
| `apps/api/migrations/versions/0022_webhooks.py` | **Create.** The table. |
| `apps/api/src/relaydesk/services/webhook_dispatch.py` | **Create.** Arguments → signed request → `DispatchResult`. No DB. |
| `apps/api/src/relaydesk/services/webhooks.py` | **Create.** CRUD, secret minting, rotation. No HTTP. |
| `apps/api/src/relaydesk/schemas/webhook.py` | **Create.** Console wire types. |
| `apps/api/src/relaydesk/api/webhooks.py` | **Create.** Six admin-only routes. |
| `apps/api/src/relaydesk/config.py` | **Modify.** `webhook_allow_private`, `webhook_timeout_seconds`, `webhook_test_hourly_cap`. |
| `apps/api/src/relaydesk/models/__init__.py` | **Modify.** Register `Webhook`, `WebhookMethod`. |
| `apps/api/src/relaydesk/api/router.py` | **Modify.** Mount at `/webhooks`. |
| `apps/web/lib/api/webhooks.ts` | **Create.** Server-only `apiFetch` calls. |
| `apps/web/app/(console)/settings/custom-webhooks/actions.ts` | **Create.** Server actions. |
| `apps/web/components/settings/webhook-actions.tsx` | **Create.** Per-row test / rotate / delete. |
| `apps/web/components/settings/webhook-dialog.tsx` | **Modify.** Real create; secret shown once. |
| `apps/web/app/(console)/settings/custom-webhooks/page.tsx` | **Modify.** Read the API. |
| `apps/web/lib/types.ts` | **Modify.** `Webhook.createdAt`, `WebhookCreated`, `WebhookTestResult`. |
| `apps/web/lib/mock/settings.ts` | **Modify.** Delete `webhooks` and `getWebhooks`. |

---

### Task 1: The URL guard

**Files:**
- Create: `apps/api/src/relaydesk/services/url_guard.py`
- Modify: `apps/api/src/relaydesk/config.py`
- Test: `apps/api/tests/test_url_guard.py`

**Interfaces:**
- Consumes: `relaydesk.errors.Invalid`, `relaydesk.config.get_settings`.
- Produces: `ensure_dispatchable_url(url: str) -> None` — raises `Invalid`. Reads the allow-private flag from settings itself, so callers pass nothing.

- [ ] **Step 1: Write the failing tests.** Table-driven, no network — monkeypatch the resolver.

```python
import pytest
from relaydesk.errors import Invalid
from relaydesk.services import url_guard


@pytest.fixture(autouse=True)
def resolve_to(monkeypatch):
    """Pin DNS so the table asserts policy, not the internet."""
    def _set(*addresses: str) -> None:
        monkeypatch.setattr(url_guard, "_resolve", lambda host: list(addresses))
    _set("93.184.216.34")
    return _set


def test_a_public_https_url_is_dispatchable():
    url_guard.ensure_dispatchable_url("https://api.example.com/hook")


@pytest.mark.parametrize("url", ["http://api.example.com/hook", "ftp://x/y", "not a url", "https:///nohost"])
def test_only_https_with_a_host_is_dispatchable(url):
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url(url)


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254", "::1", "fc00::1", "224.0.0.1", "0.0.0.0"],
)
def test_an_address_off_the_public_internet_is_refused(resolve_to, address):
    resolve_to(address)
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("https://internal.example.com/hook")


def test_one_private_answer_among_public_ones_refuses_the_whole_url(resolve_to):
    resolve_to("93.184.216.34", "127.0.0.1")
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("https://split.example.com/hook")


def test_a_host_that_does_not_resolve_is_refused(monkeypatch):
    monkeypatch.setattr(url_guard, "_resolve", lambda host: [])
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("https://nxdomain.example.com/hook")


def test_the_allow_private_flag_admits_private_addresses(monkeypatch, resolve_to):
    resolve_to("10.0.0.5")
    monkeypatch.setattr(url_guard, "_allow_private", lambda: True)
    url_guard.ensure_dispatchable_url("https://internal.example.com/hook")


def test_the_allow_private_flag_does_not_admit_plain_http(monkeypatch):
    monkeypatch.setattr(url_guard, "_allow_private", lambda: True)
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("http://internal.example.com/hook")
```

- [ ] **Step 2: Run and watch it fail.** `pytest tests/test_url_guard.py -q` → `ModuleNotFoundError: relaydesk.services.url_guard`.

- [ ] **Step 3: Implement.** `_resolve` and `_allow_private` are module-level seams so the tests above can pin them.

```python
"""Whether a workspace-supplied URL may be dispatched to.

Separate from the dispatcher because a deny list is exactly the kind of code
that should be testable by a table of addresses with no server anywhere near
it. See spec D8: this runs on every dispatch, not only on save, because DNS
is mutable between the two.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

from relaydesk.config import get_settings
from relaydesk.errors import Invalid


def _allow_private() -> bool:
    return get_settings().webhook_allow_private


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return []
    return [info[4][0] for info in infos]


def _is_off_limits(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return (
        ip.is_private          # 10/8, 172.16/12, 192.168/16, ::1, fc00::/7
        or ip.is_loopback
        or ip.is_link_local    # 169.254/16, where instance metadata lives
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def ensure_dispatchable_url(url: str) -> None:
    """Raise ``Invalid`` unless this URL is safe for the server to call."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise Invalid("A webhook URL must be an absolute https:// URL.")

    if _allow_private():
        return

    addresses = _resolve(parts.hostname)
    if not addresses:
        raise Invalid(f"{parts.hostname} does not resolve.")
    if any(_is_off_limits(address) for address in addresses):
        raise Invalid(
            f"{parts.hostname} resolves to an address that is not on the public "
            "internet. Set RELAYDESK_WEBHOOK_ALLOW_PRIVATE=true if this is "
            "deliberate."
        )
```

Settings additions (`config.py`, beside the other feature flags):

```python
    # A URL a workspace supplies is fetched by the server, so the default
    # assumes it is hostile. See spec D8.
    webhook_allow_private: bool = False
    webhook_timeout_seconds: float = 10.0
    webhook_test_hourly_cap: int = 60
```

- [ ] **Step 4: Run and watch it pass.** `pytest tests/test_url_guard.py -q` → all green.
- [ ] **Step 5: Commit.** `git commit -m "feat(webhooks): guard which URLs the server may dispatch to"`

---

### Task 2: The model and its migration

**Files:**
- Create: `apps/api/src/relaydesk/models/webhook.py`, `apps/api/migrations/versions/0022_webhooks.py`
- Modify: `apps/api/src/relaydesk/models/__init__.py`
- Test: `apps/api/tests/test_webhook_model.py`

**Interfaces:**
- Produces: `Webhook` (`workspace_id`, `name`, `description`, `method`, `url`, `params`, `secret`, `created_by_user_id`) and `WebhookMethod` (StrEnum: `get`/`post`/`put`/`patch`/`delete`, values uppercase — `GET`, `POST`, …, because the value is used verbatim as the HTTP method and appears verbatim in the console).

- [ ] **Step 1: Write the failing test.** Uses the existing `session` fixture and `tests/factories.py` for a workspace.

```python
import pytest
from sqlalchemy.exc import IntegrityError

from relaydesk.models import Webhook, WebhookMethod


async def _webhook(workspace_id, name="refund_order", **kwargs):
    return Webhook(
        workspace_id=workspace_id,
        name=name,
        description="Refunds an order by its order_id.",
        method=WebhookMethod.post,
        url="https://api.example.com/refund",
        params=[{"name": "order_id", "type": "string", "description": "The order.", "required": True}],
        secret="whsec_test",
        **kwargs,
    )


async def test_params_round_trip_as_json(session, workspace):
    hook = await _webhook(workspace.id)
    session.add(hook)
    await session.commit()
    await session.refresh(hook)
    assert hook.params[0]["name"] == "order_id"
    assert hook.params[0]["required"] is True


async def test_two_webhooks_in_one_workspace_cannot_share_a_name(session, workspace):
    session.add(await _webhook(workspace.id))
    await session.commit()
    session.add(await _webhook(workspace.id))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_two_workspaces_may_each_have_the_same_name(session, workspace, other_workspace):
    session.add(await _webhook(workspace.id))
    session.add(await _webhook(other_workspace.id))
    await session.commit()  # no IntegrityError
```

Check `tests/conftest.py` for the actual fixture names before writing this; if `other_workspace` does not exist, build the second workspace with `tests/factories.py` the way the api-keys tests do.

- [ ] **Step 2: Run and watch it fail.** `ImportError: cannot import name 'Webhook'`.

- [ ] **Step 3: Implement the model.** The docstring carries D2 — the reader has likely just read `ChannelAccount`'s opposite promise.

```python
import enum
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class WebhookMethod(enum.StrEnum):
    """Values are the HTTP method verbatim -- they are sent on the wire and
    shown in the console, so there is no mapping layer to keep in step."""

    get = "GET"
    post = "POST"
    put = "PUT"
    patch = "PATCH"
    delete = "DELETE"


class Webhook(UUIDMixin, TimestampMixin, Base):
    """An endpoint a workspace owns, registered as a tool something inside
    Relaydesk can call.

    ``secret`` is stored in plaintext, and that is a departure from every
    other credential here -- ``ApiKey`` keeps only a digest, and
    ``ChannelAccount`` deliberately keeps nothing at all so that a database
    compromise grants no mailbox access. A signature the receiver can verify
    needs the same key at both ends, so this table cannot make that promise:
    **a database compromise discloses every webhook secret, and with it the
    ability to forge requests to endpoints that trust them.** Spec D2 records
    what was weighed. The mitigations shipped are a secret per webhook rather
    than per workspace, so a leak is scoped to one integration, and rotation
    as a first-class operation.

    ``description`` is not decoration and is not nullable: it is the text a
    future agent reads to decide whether this is the tool for a job.

    ``name`` is an identifier, unique per workspace, because a tool is
    selected by name and two ``refund_order``s have no correct resolution.

    ``created_by_user_id`` is SET NULL for ``ApiKey``'s reason -- the webhook
    belongs to the workspace and must outlive whoever registered it.
    """

    __tablename__ = "webhooks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_webhooks_workspace_name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[WebhookMethod] = mapped_column(
        SAEnum(
            WebhookMethod,
            name="ck_webhooks_method",
            native_enum=False,
            length=8,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # JSONB rather than a child table: params are read and written as a unit
    # and never queried across webhooks. Spec D5.
    params: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    secret: Mapped[str] = mapped_column(String(70), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
```

Register both names in `models/__init__.py`'s imports and `__all__` (keep alphabetical order).

- [ ] **Step 4: Generate the migration**, then hand-edit its docstring to explain the table the way `0019_snippets.py` does.

```bash
docker compose exec api alembic revision --autogenerate -m "webhooks"
```

Rename the file to `0022_webhooks.py`, set `revision = "0022"` and `down_revision = "0021"`. Verify the autogenerated body has: the unique constraint, the CHECK constraint for `method`, `server_default="[]"` on `params`, and both foreign keys with the right `ondelete`.

- [ ] **Step 5: Run the tests.** The suite migrates from scratch each session, so a broken migration fails everything, not just this file.
- [ ] **Step 6: Commit.** `git commit -m "feat(webhooks): add the webhooks table"`

---

### Task 3: The dispatcher

**Files:**
- Create: `apps/api/src/relaydesk/services/webhook_dispatch.py`
- Test: `apps/api/tests/test_webhook_dispatch.py`

**Interfaces:**
- Consumes: `Webhook`, `WebhookMethod` (Task 2); `ensure_dispatchable_url` (Task 1).
- Produces:
  - `DispatchResult` — frozen dataclass: `ok: bool`, `status: int | None`, `duration_ms: int`, `response_body: str`, `error: str | None`.
  - `async def dispatch(webhook: Webhook, arguments: dict[str, object], *, client: httpx.AsyncClient | None = None) -> DispatchResult`
  - `def sign(secret: str, timestamp: int, method: str, url: str, body: str) -> str` — hex HMAC-SHA256, exported because the test pins a vector against it and the docs quote it.
  - `def prepare_arguments(webhook: Webhook, arguments: dict[str, object]) -> dict[str, object]` — raises `Invalid`; drops undeclared keys, coerces declared ones.

- [ ] **Step 1: Write the failing tests.** `httpx.MockTransport` throughout — no socket is opened.

```python
import httpx
import pytest

from relaydesk.errors import Invalid
from relaydesk.models import Webhook, WebhookMethod
from relaydesk.services import webhook_dispatch


def make_webhook(method=WebhookMethod.post, params=None, url="https://api.example.com/refund"):
    return Webhook(
        name="refund_order",
        description="Refunds an order.",
        method=method,
        url=url,
        secret="whsec_fixed",
        params=params if params is not None else [
            {"name": "order_id", "type": "string", "description": "", "required": True},
            {"name": "amount", "type": "number", "description": "", "required": False},
        ],
    )


def client_capturing(captured, *, status=200, body="ok"):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status, text=body)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def allow_any_url(monkeypatch):
    monkeypatch.setattr(webhook_dispatch, "ensure_dispatchable_url", lambda url: None)


def test_the_signature_is_a_fixed_vector():
    """Pinned so that changing the scheme has to be deliberate. Spec D4."""
    signature = webhook_dispatch.sign(
        "whsec_fixed", 1757376000, "POST", "https://api.example.com/refund", '{"order_id":"A1"}'
    )
    assert signature == (
        "REPLACE WITH THE VALUE THE IMPLEMENTATION PRODUCES, AFTER CHECKING IT "
        "BY HAND AGAINST hmac.new(b'whsec_fixed', b'1757376000.POST."
        "https://api.example.com/refund.{\"order_id\":\"A1\"}', 'sha256').hexdigest()"
    )


async def test_a_post_sends_arguments_as_json_and_signs_them():
    captured = []
    result = await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1"}, client=client_capturing(captured)
    )
    request = captured[0]
    assert result.ok and result.status == 200
    assert request.headers["content-type"] == "application/json"
    assert request.read() == b'{"order_id": "A1"}'
    t, v1 = (part.split("=", 1)[1] for part in request.headers["relaydesk-signature"].split(","))
    assert v1 == webhook_dispatch.sign("whsec_fixed", int(t), "POST", str(request.url), request.read().decode())
    assert request.headers["relaydesk-webhook-id"]


async def test_a_get_sends_arguments_in_the_query_string_and_signs_the_url():
    captured = []
    hook = make_webhook(method=WebhookMethod.get, url="https://api.example.com/sub")
    await webhook_dispatch.dispatch(hook, {"order_id": "A1"}, client=client_capturing(captured))
    request = captured[0]
    assert request.url.params["order_id"] == "A1"
    assert request.read() == b""
    t, v1 = (part.split("=", 1)[1] for part in request.headers["relaydesk-signature"].split(","))
    assert v1 == webhook_dispatch.sign("whsec_fixed", int(t), "GET", str(request.url), "")


async def test_a_missing_required_argument_fails_before_any_request():
    captured = []
    with pytest.raises(Invalid):
        await webhook_dispatch.dispatch(make_webhook(), {}, client=client_capturing(captured))
    assert captured == []


async def test_an_undeclared_argument_is_dropped():
    captured = []
    await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1", "sneaky": "x"}, client=client_capturing(captured)
    )
    assert b"sneaky" not in captured[0].read()


async def test_a_value_that_will_not_coerce_is_refused():
    with pytest.raises(Invalid):
        await webhook_dispatch.dispatch(
            make_webhook(), {"order_id": "A1", "amount": "not a number"},
            client=client_capturing([]),
        )


async def test_a_number_arrives_as_a_number():
    captured = []
    await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1", "amount": "250"}, client=client_capturing(captured)
    )
    assert b'"amount": 250' in captured[0].read()


async def test_a_redirect_is_not_followed():
    def handler(request):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await webhook_dispatch.dispatch(make_webhook(), {"order_id": "A1"}, client=client)
    assert result.status == 302 and result.ok is False


async def test_a_failing_receiver_is_a_result_not_an_exception():
    def handler(request):
        return httpx.Response(500, text="boom")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await webhook_dispatch.dispatch(make_webhook(), {"order_id": "A1"}, client=client)
    assert result.ok is False and result.status == 500 and "boom" in result.response_body


async def test_a_timeout_is_a_result_not_an_exception():
    def handler(request):
        raise httpx.ConnectTimeout("too slow")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await webhook_dispatch.dispatch(make_webhook(), {"order_id": "A1"}, client=client)
    assert result.ok is False and result.status is None and result.error


async def test_a_guarded_url_is_a_result_not_an_exception(monkeypatch):
    def refuse(url):
        raise Invalid("nope")
    monkeypatch.setattr(webhook_dispatch, "ensure_dispatchable_url", refuse)
    result = await webhook_dispatch.dispatch(make_webhook(), {"order_id": "A1"})
    assert result.ok is False and result.error == "nope"


async def test_an_oversized_response_body_is_truncated():
    def handler(request):
        return httpx.Response(200, text="x" * 100_000)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await webhook_dispatch.dispatch(make_webhook(), {"order_id": "A1"}, client=client)
    assert len(result.response_body) <= webhook_dispatch.BODY_LIMIT
```

Note the deliberate ordering in the last-but-one test: a URL the guard refuses is a `DispatchResult`, while a bad *argument* raises `Invalid`. Arguments are the caller's mistake and belong in a 422; a refused URL is an outcome of the call the admin asked for.

- [ ] **Step 2: Run and watch it fail.** `ModuleNotFoundError`.
- [ ] **Step 3: Implement.** Compute the fixed vector by hand and paste it into the test from Step 1 before running.

Key points the implementation must honour: `follow_redirects=False`; `timeout=get_settings().webhook_timeout_seconds`; the body serialised **once** with `json.dumps` and passed as `content=` so the bytes signed are the bytes sent (`json=` would re-serialise and could differ); the signed URL is the fully-built one including the query string (build the request with `client.build_request` first, sign `str(request.url)`, then attach the header); `ok` is `200 <= status < 300`.

- [ ] **Step 4: Run and watch it pass.**
- [ ] **Step 5: Commit.** `git commit -m "feat(webhooks): sign and dispatch a tool call"`

---

### Task 4: The registry service

**Files:**
- Create: `apps/api/src/relaydesk/services/webhooks.py`
- Test: `apps/api/tests/test_webhooks_service.py`

**Interfaces:**
- Produces (all `async`, all taking `session` first and scoping by `workspace_id`):
  - `create(session, workspace_id, *, name, description, method, url, params, created_by_user_id) -> Webhook`
  - `list_webhooks(session, workspace_id) -> list[Webhook]` — newest first
  - `get(session, workspace_id, webhook_id) -> Webhook` — raises `NotFound`
  - `update(session, workspace_id, webhook_id, **fields) -> Webhook` — only supplied fields
  - `delete(session, workspace_id, webhook_id) -> None`
  - `rotate_secret(session, workspace_id, webhook_id) -> Webhook`
  - `NAME_PATTERN: re.Pattern`

- [ ] **Step 1: Write the failing tests.**

```python
import pytest
from relaydesk.errors import Conflict, Invalid, NotFound
from relaydesk.models import WebhookMethod
from relaydesk.services import webhooks


async def create(session, workspace, name="refund_order", url="https://api.example.com/refund"):
    return await webhooks.create(
        session, workspace.id, name=name, description="Refunds an order.",
        method=WebhookMethod.post, url=url, params=[], created_by_user_id=None,
    )


async def test_a_new_webhook_gets_a_prefixed_secret(session, workspace):
    hook = await create(session, workspace)
    assert hook.secret.startswith("whsec_") and len(hook.secret) > 30


@pytest.mark.parametrize("name", ["Refund Order", "9lives", "refund-order", "", "a" * 65, "réfund"])
async def test_a_name_that_is_not_an_identifier_is_refused(session, workspace, name):
    with pytest.raises(Invalid):
        await create(session, workspace, name=name)


async def test_a_duplicate_name_in_one_workspace_is_refused(session, workspace):
    await create(session, workspace)
    with pytest.raises(Conflict):
        await create(session, workspace)


async def test_the_same_name_in_two_workspaces_is_allowed(session, workspace, other_workspace):
    await create(session, workspace)
    await create(session, other_workspace)  # no raise


async def test_a_url_that_is_not_https_is_refused_at_registration(session, workspace):
    with pytest.raises(Invalid):
        await create(session, workspace, url="http://api.example.com/refund")


async def test_another_workspaces_webhook_is_not_found(session, workspace, other_workspace):
    hook = await create(session, workspace)
    for call in (webhooks.get, webhooks.delete, webhooks.rotate_secret):
        with pytest.raises(NotFound):
            await call(session, other_workspace.id, hook.id)


async def test_rotation_replaces_the_secret(session, workspace):
    hook = await create(session, workspace)
    before = hook.secret
    rotated = await webhooks.rotate_secret(session, workspace.id, hook.id)
    assert rotated.secret != before


async def test_the_list_is_scoped_to_its_workspace(session, workspace, other_workspace):
    await create(session, workspace)
    assert await webhooks.list_webhooks(session, other_workspace.id) == []
```

- [ ] **Step 2: Run and watch it fail.**
- [ ] **Step 3: Implement.** `create` and `update` validate the name against `NAME_PATTERN`, call `ensure_dispatchable_url` for the scheme check at registration time, and translate the unique-constraint `IntegrityError` into `Conflict("A webhook named 'x' already exists.")` rather than letting a 500 escape. Note in a comment that registration-time URL validation is a convenience — the dispatch-time check in Task 1 is the one that is load-bearing (D8).
- [ ] **Step 4: Run and watch it pass.**
- [ ] **Step 5: Commit.** `git commit -m "feat(webhooks): register, update and rotate webhooks"`

---

### Task 5: Schemas and routes

**Files:**
- Create: `apps/api/src/relaydesk/schemas/webhook.py`, `apps/api/src/relaydesk/api/webhooks.py`
- Modify: `apps/api/src/relaydesk/api/router.py`
- Test: `apps/api/tests/test_webhooks_api.py`

**Interfaces:**
- Produces: `WebhookOut` (`id`, `name`, `description`, `method`, `url`, `params`, `createdAt` — never `secret`), `WebhookParamIn` (`name`, `type`, `description`, `required`), `WebhookCreate`, `WebhookUpdate` (all optional), `WebhookCreated` (`webhook`, `secret`), `WebhookTestRequest` (`arguments: dict[str, object] = {}`), `WebhookTestResult` (`ok`, `status`, `durationMs`, `responseBody`, `error`).
- Routes: `GET ""`, `POST ""` (201), `PATCH "/{id}"`, `DELETE "/{id}"` (204), `POST "/{id}/secret"`, `POST "/{id}/test"`.

- [ ] **Step 1: Write the failing tests.** Follow `tests/test_api_keys_api.py` for client/auth fixtures.

```python
async def test_an_admin_creates_a_webhook_and_sees_the_secret_once(admin_client):
    response = await admin_client.post("/api/webhooks", json={
        "name": "refund_order", "description": "Refunds an order.",
        "method": "POST", "url": "https://api.example.com/refund",
        "params": [{"name": "order_id", "type": "string", "description": "The order.", "required": True}],
    })
    assert response.status_code == 201
    assert response.json()["secret"].startswith("whsec_")

    listed = await admin_client.get("/api/webhooks")
    assert "secret" not in listed.json()[0]


async def test_an_agent_may_not_touch_webhooks(agent_client, webhook):
    for method, path in [
        ("get", "/api/webhooks"), ("post", "/api/webhooks"),
        ("patch", f"/api/webhooks/{webhook.id}"), ("delete", f"/api/webhooks/{webhook.id}"),
        ("post", f"/api/webhooks/{webhook.id}/secret"), ("post", f"/api/webhooks/{webhook.id}/test"),
    ]:
        response = await getattr(agent_client, method)(path, json={})
        assert response.status_code == 403


async def test_another_workspaces_webhook_is_404_not_403(other_admin_client, webhook):
    response = await other_admin_client.get(f"/api/webhooks/{webhook.id}")
    assert response.status_code == 404


async def test_a_name_that_is_not_an_identifier_is_422(admin_client):
    response = await admin_client.post("/api/webhooks", json={
        "name": "Refund Order", "description": "x", "method": "POST",
        "url": "https://api.example.com/refund", "params": [],
    })
    assert response.status_code == 422


async def test_rotation_returns_a_new_secret(admin_client, webhook):
    response = await admin_client.post(f"/api/webhooks/{webhook.id}/secret")
    assert response.status_code == 200
    assert response.json()["secret"] != webhook.secret


async def test_a_test_request_reports_the_receivers_failure_as_200(admin_client, webhook, monkeypatch):
    """The request we were asked to make was made; its outcome is the body."""
    from relaydesk.services import webhook_dispatch

    async def failing(hook, arguments, client=None):
        return webhook_dispatch.DispatchResult(
            ok=False, status=500, duration_ms=12, response_body="boom", error=None
        )
    monkeypatch.setattr(webhook_dispatch, "dispatch", failing)

    response = await admin_client.post(f"/api/webhooks/{webhook.id}/test", json={"arguments": {}})
    assert response.status_code == 200
    assert response.json() == {"ok": False, "status": 500, "durationMs": 12, "responseBody": "boom", "error": None}


async def test_the_test_route_is_rate_limited(admin_client, webhook, monkeypatch):
    monkeypatch.setattr(get_settings(), "webhook_test_hourly_cap", 1)  # or override the settings fixture
    ...  # first call passes, second is 429
```

- [ ] **Step 2: Run and watch it fail.**
- [ ] **Step 3: Implement the router.** `POST /{id}/test` charges `ratelimit.check(session, "webhook_test", str(scope.workspace_id), limit=..., window=timedelta(hours=1))` **before** dispatching — it commits, and the charge must survive whatever the request does next. Raise `TooManyRequests` when it refuses. Mount in `router.py` with `tags=["webhooks"]` and a comment noting these are tool endpoints, not event subscriptions (D1).
- [ ] **Step 4: Run and watch it pass.** Then run the whole API suite: `pytest -q`.
- [ ] **Step 5: Commit.** `git commit -m "feat(webhooks): admin routes for the webhook registry"`

---

### Task 6: The console

**Files:**
- Create: `apps/web/lib/api/webhooks.ts`, `apps/web/app/(console)/settings/custom-webhooks/actions.ts`, `apps/web/components/settings/webhook-actions.tsx`
- Modify: `apps/web/lib/types.ts`, `apps/web/lib/mock/settings.ts`, `apps/web/components/settings/webhook-dialog.tsx`, `apps/web/app/(console)/settings/custom-webhooks/page.tsx`

**Interfaces:**
- Consumes: the routes from Task 5.
- Produces: `getWebhooks()`, `createWebhook()`, `updateWebhook()`, `deleteWebhook()`, `rotateWebhookSecret()`, `testWebhook()` in `lib/api/webhooks.ts`; matching `…Action` wrappers returning `{ ok: true; … } | { ok: false; message: string }`, exactly as `settings/api-keys/actions.ts` does.

- [ ] **Step 1: Types.** Add `createdAt: string` to `Webhook`; add `WebhookCreated { webhook: Webhook; secret: string }` and `WebhookTestResult { ok: boolean; status: number | null; durationMs: number; responseBody: string; error: string | null }`.
- [ ] **Step 2: `lib/api/webhooks.ts`**, mirroring `lib/api/api-keys.ts` — `import "server-only"`, `cache()` on the list only.
- [ ] **Step 3: `actions.ts`**, mirroring `settings/api-keys/actions.ts` — `"use server"`, `revalidatePath("/", "layout")` after every mutation, `ApiError` narrowed to a message, anything else rethrown.
- [ ] **Step 4: Wire the dialog.** Replace `onClick={() => setOpen(false)}` on the Create button with the create action; on success show the secret with the same shown-once treatment as `api-key-dialog.tsx`; on failure show the message inline and keep the dialog open. Add a `whsec_` reveal panel with a copy button.
- [ ] **Step 5: `webhook-actions.tsx`.** Per row: "Send test request" (opens a small form built from `webhook.params`, then renders status, duration and body), "Rotate secret", "Delete" (confirm inline — **not** `window.confirm`, which blocks the page).
- [ ] **Step 6: Point the page at the API.** `import { getWebhooks } from "@/lib/api/webhooks"`, drop the `getWebhooks` import from `lib/mock/settings`, render `<WebhookActions webhook={webhook} />` per row.
- [ ] **Step 7: Delete the mock.** Remove the `webhooks` array and `getWebhooks` from `lib/mock/settings.ts`; leave the other shells' mocks alone.
- [ ] **Step 8: Verify.** `cd apps/web && pnpm exec tsc --noEmit && pnpm lint`. Then, with `make dev` running, load `/settings/custom-webhooks`, create a webhook, and fire a test request at a real receiver.
- [ ] **Step 9: Commit.** `git commit -m "feat(web): manage custom webhooks against the API"`

---

## Self-review notes

Spec coverage: §3 D1 → Task 5 router comment; D2 → Task 2 docstring; D3 → Task 4 `rotate_secret`; D4 → Task 3 `sign` + vector test; D5 → Task 2 JSONB; D6 → Tasks 2 and 4; D7 → Task 3 (no retry, no log); D8 → Task 1; D9 → Task 5 rate limit. §4 → Task 2. §5 → Task 3 `prepare_arguments`. §6 → Task 3. §7 → Task 5. §8 → Task 6. §9 → Tasks 4 and 5 isolation tests. §11 → the test lists in each task.

Carried from spec §12 and deliberately not implemented: the DNS-rebinding window (needs IP-pinned transport), encryption at rest, retries, a delivery log.
