# Custom webhooks — design

**Date:** 2026-09-09
**Status:** approved in chat, pending written review
**Slice:** 7 (follows slice 6, API keys and the public API)

Builds on `2026-09-04-tenancy-and-inbox-core-design.md` (slice 1), which
remains binding for multi-tenancy, sessions, admin gating and the error
envelope, and on `2026-09-08-api-keys-and-public-api-design.md` (slice 6),
whose credential-handling patterns this slice follows where it can and
departs from once, deliberately (D2). Where this document is silent, slice 1
governs.

## 1. What this builds

A workspace can register an HTTP endpoint it controls, describe it in plain
language, declare the arguments it takes, and have Relaydesk call it with an
HMAC signature the receiver can verify. An admin can fire a test request from
the console and see the status, timing and response body that came back.

What this does **not** build is the thing that will eventually make those
calls on its own. There is no agent runtime in this repository — no model
client, no tool-calling loop, nothing that reads a webhook's description and
decides to invoke it. This slice builds the registry and the delivery
mechanism so that when slice 8 introduces an agent, the tool it calls already
exists, is already signed, and is already guarded.

That ordering is deliberate. A tool-calling loop written against an
unimplemented dispatcher would have to invent one, and the invented one would
be the part nobody tested.

## 2. What already exists, and what it obliges

`settings/custom-webhooks` was built as a UI shell against
`apps/web/lib/mock/settings.ts`. Its copy is a contract:

> "Register endpoints you control as tools the agent can call. Every request
> is signed with your webhook secret."
>
> "The agent picks a tool by reading its description, so write them
> carefully."

Three obligations follow. The registry is a **tool** registry, not an event
subscription list. Every request is **signed**. And `description` is not a
convenience field for humans — it is the input to a future tool-selection
decision, which is why §4 makes it `NOT NULL` rather than nullable.

`apps/web/components/settings/webhook-dialog.tsx` settles the shape of a
webhook: a name, a description, an HTTP method, a URL, and a list of
parameters each with a name, a type of `string | number | boolean`, a
description and a required flag. The dialog's placeholders (`refund_order`,
"Refunds an order by its order_id.") settle that the name is an identifier in
the shape of a function, not a title. `apps/web/lib/types.ts` already declares
`Webhook`, `WebhookParam` and `HttpMethod`; this slice makes those types
describe a real API response rather than a mock.

## 3. Decisions

**D1 — "Webhook" names two different features, and this is the tool one.**

Slice 6 §1 sketched a roadmap in which slice 3 was "signed webhooks,
delivered from a domain event stream, managed and consumed through the public
API", and noted that `settings/custom-webhooks` would be claimed by that work.
That conflated two features that share a word:

- **Event delivery** — something happened in Relaydesk (a ticket was opened, a
  reply was sent), so Relaydesk POSTs a described event to a subscribed URL.
  The workspace does not choose when it fires; the event does. Retries,
  ordering and a delivery log are essential to it.
- **Tool invocation** — this slice. The workspace declares an endpoint and
  what it does, and something inside Relaydesk decides to call it, with
  arguments, to accomplish a task. Timing is a decision, not a fact. A retry
  is a second refund, so retries are a hazard rather than a feature.

The page that exists describes the second. This document claims it. Event
delivery remains unbuilt and will need its own surface, its own model and its
own subscription semantics; it must not be folded into this table because the
two disagree about the thing that matters most — whether repeating a call is
safe.

**D2 — The signing secret is stored in plaintext, and this is a departure.**

A signature the receiver can verify requires the same key at both ends, so
Relaydesk must be able to read the secret at dispatch time. That rules out
slice 6's pattern — `ApiKey` stores only a SHA-256 digest and the plaintext
exists for exactly one response — and it rules out the reasoning in
`ChannelAccount`'s docstring, which holds no credentials by design so that a
database compromise grants no mailbox access.

The alternatives were considered and rejected:

- *Encryption at rest (Fernet).* Adds the `cryptography` dependency and a
  required key in the environment of every deployment, including every
  self-hoster. It defends only against a compromise that yields the database
  and not the environment — a leaked backup, a SQL injection — and it buys
  that with a key-rotation story in which a lost key silently breaks every
  webhook in every workspace. Worth revisiting if a secrets manager ever
  enters this stack; not worth a required env var today.
- *No secret at all: a static bearer token the receiver checks.* The same
  storage problem with a weaker guarantee — nothing binds the token to the
  request body, so it authenticates the caller but not the call.

What is shipped instead is blast-radius control (D3), rotation as a
first-class operation, and this paragraph, so that the tradeoff is a recorded
decision rather than an accident. **A database compromise discloses every
webhook secret, and therefore lets the attacker forge requests to endpoints
that trust them.** That is the cost of being able to sign at all.

**D3 — One secret per webhook, not one per workspace.**

The page's copy says "your webhook secret", singular, which reads as
workspace-level. It is per-webhook anyway: the secret is shared with whoever
operates the receiving endpoint, and two endpoints may be operated by two
teams. A workspace-level secret would mean the team running the read-only
subscription lookup can forge calls to the refund endpoint. Rotation is also
per-webhook, so a suspected leak costs one integration's downtime rather than
all of them.

**D4 — The signature binds the method and URL, not only the body.**

The signed payload is:

```
{timestamp}.{method}.{full_url}.{body}
```

HMAC-SHA256, hex-encoded, sent as
`Relaydesk-Signature: t=<unix seconds>,v1=<hex>`, alongside
`Relaydesk-Webhook-Id: <uuid>`.

Stripe's well-known scheme signs `{timestamp}.{body}`, and was rejected here
because half the methods this registry allows carry no body. Under the Stripe
scheme every GET from a workspace would produce a signature valid for every
other GET to any URL with any query string — the signature would attest to a
timestamp and nothing else. Binding the method and the fully-resolved URL
(query string included) makes a captured signature useless for a different
call.

`timestamp` exists so a receiver can reject replays outside a tolerance
window. Relaydesk does not enforce that window — the receiver does, and the
documentation will say so, because a receiver that ignores the timestamp has
no replay protection and should know it.

**D5 — Parameters are a JSONB column, not a child table.**

They are read as a unit, written as a unit, and never queried across
webhooks. A `webhook_params` table would buy referential tidiness and cost a
join on every read plus an ordering column to preserve the sequence the
dialog shows. Validation lives at the Pydantic edge, which is where the
closed set of types (`string | number | boolean`) is enforced.

**D6 — The name is an identifier and is unique per workspace.**

`^[a-z][a-z0-9_]{0,63}$`, unique on `(workspace_id, name)`. A tool is selected
by name; two tools named `refund_order` in one workspace is an ambiguity with
no correct resolution, so the database refuses it. Uniqueness is per
workspace, not global — one workspace's naming has no business constraining
another's.

**D7 — Dispatch is synchronous, unretried, and unlogged.**

The only caller today is an explicit test request from an admin who is
watching, and the useful answer is the one that arrives before they look away.
Enqueueing it through Celery would replace an answer with a poll loop and
would need a delivery table to carry the result.

No retries: this registry's example tool is `refund_order`, and a retried
refund is a second refund. Retry policy is a per-tool question about
idempotency that nothing in the current model can answer, so the honest
default is one attempt and a reported failure.

No delivery log: the test endpoint returns its result to its caller, and
there is no second consumer to persist it for. When the agent runtime lands
and calls arrive unattended, a log becomes necessary — the dispatcher returns
a `DispatchResult` value precisely so persisting it later is an addition
rather than a rewrite.

**D8 — The URL guard runs at dispatch, and redirects are refused.**

Registering a URL and calling it are separated in time, and DNS is mutable in
between, so a check performed only at save is a check an attacker schedules
around. `ensure_dispatchable_url` therefore runs on every dispatch. It
requires `https`, resolves the hostname through `getaddrinfo`, and rejects if
**any** returned address is loopback, private, link-local, reserved or
multicast — the deny list covers `127.0.0.0/8`, `10/8`, `172.16/12`,
`192.168/16`, `169.254/16` (which is where cloud instance metadata lives),
`::1` and `fc00::/7`.

`RELAYDESK_WEBHOOK_ALLOW_PRIVATE=true` disables the address check and nothing
else, for self-hosters whose tools genuinely live on the same private network.
It is off by default because the safe default for software that accepts a URL
and fetches it is to assume the URL is hostile.

Redirects are not followed. A permitted public URL that 302s to
`http://169.254.169.254/` is the guard bypass this exists to prevent, and
"follow redirects" is not a feature a tool endpoint needs.

**D9 — Test invocation is admin-only and rate-limited.**

An endpoint that makes the server issue an arbitrary outbound request is a
request proxy, and the value of an unauthenticated or ungated one to an
attacker is obvious. Admin-only matches the page, which is already behind
`requireAdmin()`. The limit is 60 test requests per workspace per hour,
counted through the existing `services.ratelimit.check` under a
`webhook_test` bucket keyed by workspace id — generous for someone debugging
an endpoint, and far short of useful for anything else.

`ratelimit.check` commits, as its docstring warns, so the test route charges
for the call before dispatching. Nothing else is pending on that session
there — the route reads a webhook and makes an HTTP request, and writes
nothing — so the ordering costs nothing and keeps the charge from being
refunded by a later rollback.

## 4. Data model

New table `webhooks`, migration `0022_webhooks.py`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `UUIDMixin` |
| `created_at` / `updated_at` | timestamptz | `TimestampMixin` |
| `workspace_id` | UUID FK → `workspaces.id` | `CASCADE`, indexed |
| `name` | `String(64)` | D6; unique with `workspace_id` |
| `description` | `String(500)` | `NOT NULL` — §2 |
| `method` | enum | `GET/POST/PUT/PATCH/DELETE`, `native_enum=False, create_constraint=True`, the repo's CHECK-constraint pattern |
| `url` | `String(2048)` | validated on write and again at dispatch |
| `params` | JSONB | D5; array of `{name, type, description, required}`, default `[]` |
| `secret` | `String(70)` | `whsec_` + `generate_token()`; plaintext, D2 |
| `created_by_user_id` | UUID FK → `users.id` | `SET NULL` — the webhook belongs to the workspace and outlives its author, as `ApiKey` does |

The model docstring carries D2 in full. `ChannelAccount`'s docstring states
the opposite tradeoff for a reason, and a reader who has just read it is owed
an explanation of why this table does the other thing.

Deletion is a real delete, unlike `ApiKey.revoked_at`. A key is preserved
because `activity_events.actor_api_key_id` must keep resolving to a name; a
webhook is referenced by nothing and has no attribution to preserve.

## 5. Argument handling

A dispatch takes the webhook and a `dict[str, object]` of arguments. Before
any request is built:

- every `required` parameter must be present, or the dispatch fails without a
  call;
- values are coerced to their declared type, and a value that will not coerce
  fails the dispatch;
- arguments not declared on the webhook are dropped, not forwarded. The
  declared parameter list is the contract, and a caller that invents a field
  is a caller with a bug — quietly passing it through would make that bug the
  receiver's problem.

Placement follows the method: `GET` and `DELETE` carry arguments in the query
string, everything else in a JSON body with `Content-Type: application/json`.

## 6. Dispatch

`services/webhook_dispatch.py` exposes one function over a `Webhook` and an
argument dict, returning:

```
DispatchResult(ok, status, duration_ms, response_body, error)
```

A timeout of 10 seconds, `follow_redirects=False` (D8), and a read capped at
64 KiB with the stored body truncated to 4 KiB — enough to show what came
back without letting a receiver decide how much memory the API spends.

It does not raise for a failing receiver. A connection refused, a timeout, a
500 and a guard rejection are all outcomes of the question the caller asked,
and are returned as `ok=False` with `error` set. It raises only for a
programming error, and the test endpoint therefore has no failure path of its
own.

The module imports no session and no FastAPI. It takes a model instance and
returns a value, so its tests need `httpx.MockTransport` and nothing else.

`services/url_guard.py` holds `ensure_dispatchable_url` (D8) as a separate
pure module, because a deny list is exactly the kind of code that should be
testable by a table of addresses with no server anywhere near it.

## 7. API surface

Console, session-authenticated, mounted at `/webhooks`. Every route calls
`scope.require_admin()`.

| Route | Behaviour |
|---|---|
| `GET /webhooks` | The workspace's webhooks, newest first. Never the secret. |
| `POST /webhooks` | Create. The **only** response carrying `secret`. |
| `PATCH /webhooks/{id}` | Update name, description, method, url, params. |
| `DELETE /webhooks/{id}` | Delete. `204`. |
| `POST /webhooks/{id}/secret` | Rotate. Returns the new secret, once. |
| `POST /webhooks/{id}/test` | Body `{arguments}`. Returns the `DispatchResult`. |

Errors use the slice-1 envelope. `403` for a non-admin session; `404` for an
id in another workspace, indistinguishable from one that does not exist, per
the slice-1 isolation contract; `422` for a name that is not an identifier, a
URL that is not `https`, or an argument that will not coerce; `429` over the
test limit.

A test request that reaches the receiver and gets a 500 is a `200` from
Relaydesk carrying `ok: false`. The request the admin asked us to make was
made; its outcome is the response.

## 8. Console

Following the api-keys pair exactly: `lib/api/webhooks.ts` (server-only,
`apiFetch`) and `app/(console)/settings/custom-webhooks/actions.ts` (`"use server"`,
`revalidatePath`, `ApiError` narrowed to a message).

- `webhook-dialog.tsx` — the "Create webhook" button, whose only handler is
  currently `onClick={() => setOpen(false)}`, calls the create action and
  surfaces the returned secret once, with the same shown-once treatment the
  API key dialog uses.
- `webhook-actions.tsx` — new, per row: send test request, rotate secret,
  delete. Mirrors `api-key-actions.tsx`.
- `page.tsx` — reads `getWebhooks()` from `lib/api/webhooks.ts`.
- `lib/mock/settings.ts` — the `webhooks` array and its getter are deleted.
  The remaining mocks (MCP servers, integrations, plans) stay; they belong to
  shells this slice does not claim.
- `lib/types.ts` — `Webhook` gains `createdAt`; a `WebhookCreated`
  (`{ webhook, secret }`) is added. `WebhookParam` and `HttpMethod` are
  already correct.

## 9. Multi-tenancy

Every query filters on `workspace_id` from the session's scope, never from a
path or body. A webhook id belonging to another workspace resolves to `404`
by the same mechanism slice 1 established, and that is asserted per endpoint
rather than once, matching the existing suite.

## 10. Out of scope

The agent runtime that will call these tools (slice 8). Event-delivery
webhooks and the domain event stream behind them (D1) — a separate feature
that happens to share a word. Retries, backoff and a delivery history table
(D7). An enable/disable toggle per webhook, which the shell does not offer
and delete already covers. The `settings/mcp-servers` and
`settings/automations` shells. Per-webhook custom headers. OAuth or mTLS to
the receiving endpoint. Encryption at rest for the secret (D2).

## 11. Testing

`test_url_guard.py` — a table of URLs and expected verdicts, no network: a
public https URL passes; `http` is refused; each private and loopback range is
refused by v4 and v6; `169.254.169.254` is refused by name and by literal; a
hostname resolving to a mix of public and private addresses is refused; the
allow-private flag flips exactly the address check and does not admit `http`.

`test_webhook_dispatch.py`, on `httpx.MockTransport` — a fixed vector asserts
the signature byte for byte against a known secret, timestamp and body, so
that a change to the scheme has to be deliberate; the timestamp and webhook id
headers are present; GET puts arguments in the query string and POST in a JSON
body; a missing required argument fails without any request being made; an
undeclared argument is dropped; a value that will not coerce fails; a 302 is
not followed; a timeout, a connection error and a 500 each return `ok=False`
with the status or error set rather than raising; an oversized response body
is truncated.

`test_webhooks_service.py` — a name that is not an identifier is refused; a
duplicate name in one workspace is refused; the same name in two workspaces is
allowed; a webhook from another workspace is `NotFound` for read, update,
delete and rotate; rotation changes the secret and the old one no longer
verifies.

`test_webhooks_api.py` — the admin matrix per route (an agent session gets
`403`); the cross-workspace `404` per route; the secret appears in exactly two
responses ever, create and rotate, and never in `GET /webhooks`; the test
route is refused over its rate limit with `429`.

Web: a `lib/api/webhooks` unit test is not warranted — it is four `apiFetch`
calls. The mock deletion is covered by the page compiling against the real
type.

## 12. Known risks carried

**Every webhook secret is readable from a database dump.** D2, stated again
here because it is the largest thing this slice accepts. The mitigations are
per-webhook scoping (D3) and rotation, neither of which helps if the
compromise is not noticed.

**The URL guard has a DNS-rebinding window.** The guard resolves the hostname
and checks the addresses, then hands the URL to httpx, which resolves it
again. A hostname that answers publicly for the first lookup and privately for
the second defeats the check. Closing it requires connecting to the validated
address with an explicit `Host` header, which httpx does not make
straightforward, and is left undone rather than left unsaid. The window is
narrow and the attacker must already hold admin in a workspace.

**A test request is an outbound request from Relaydesk's network.** Rate
limiting (D9) bounds the volume, and the guard bounds the destinations, but an
admin can still use the console to learn which public hosts are reachable and
how fast. This is inherent to a feature whose purpose is calling a
user-supplied URL.

**`description` is written for a consumer that does not exist yet.** Nothing
validates that a description is good enough for tool selection, because
nothing selects tools. Descriptions written now will be judged by slice 8's
agent, and some will be found wanting.
