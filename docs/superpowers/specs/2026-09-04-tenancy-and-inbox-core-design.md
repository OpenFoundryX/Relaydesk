# Tenancy & Inbox Core — Design

Date: 2026-09-04
Status: Approved, ready for implementation planning
Scope: Sub-project 1 of the Relaydesk backend

## 1. Context

The repository ships a complete Next.js console driven entirely by in-memory
mock stores under `apps/web/lib/mock/`, and a FastAPI skeleton with a health
endpoint, an async session module, and Alembic wired to `target_metadata =
None`. No models, no auth, no domain logic exist yet.

`apps/web/lib/mock/types.ts` states its own intent: the types are "deliberately
shaped like the API responses we expect to fetch later, so wiring the real
backend means changing the body of each getter in `lib/mock/*` rather than
touching any page." This design honours that seam: no page or component changes
shape, and the type file gains exactly one type (`SavedView`, which the mock
declares inline today) and otherwise stays as written.

### Backend decomposition

The console spans roughly seven independent subsystems. Each gets its own
spec, plan, and implementation cycle. This document covers only the first.

| # | Sub-project | Covers |
|---|---|---|
| 1 | **Tenancy, identity & inbox core** (this spec) | Models, migrations, workspaces, users, sessions, team, invites, conversations, messages, labels, activity, saved views |
| 2 | Ingress & egress channels | Portal intake, Tickets API, API keys, email (IMAP/Gmail/webhook), Discord, outbound send, portal ticket list |
| 3 | Knowledge base | Internal/external articles, categories, retrieval index |
| 4 | Agentic layer | LLM abstraction, job runner, AI triage, summaries, draft generation, custom webhook + MCP tool calling |
| 5 | Settings & portal surface | Portal settings, appearance, ticket form, snippets, automations |
| 6 | Analytics | `MetricSeries` aggregation |
| 7 | Billing & integrations | Plans, Stripe, integration grid |

### Out of scope for this slice

Email and every other channel; AI generation of any kind; knowledge base;
analytics; billing; integrations; the settings pages still backed by
`lib/mock/{analytics,settings,knowledge-base}.ts`, which remain mocks and
remain compiling.

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Auth ownership | Owned by FastAPI: argon2id passwords, opaque session tokens, hand-rolled Google OAuth | One source of truth for identity; no library user-model leaking into the multi-tenant layer; self-hosters get working auth with zero configuration |
| Tenancy | Multi-tenant, shared schema, `workspace_id` on every domain row | One codebase serves self-host (one workspace) and managed cloud (many); avoids per-tenant migration complexity |
| Web to API transport | Server-side only; mock getter bodies swapped for fetches | Preserves the seam the console was built for; browser never holds a token; no CORS surface; pages untouched |
| AI-dependent inbox surfaces | Modelled and served, never generated | `drafts` table and `summary`/`summary_state` columns exist now, so slice 4 needs no migration or response-schema change |
| Slice edges | Seed data, invites, Google OAuth, and saved views all in scope | Confirmed with the project owner |

## 3. Architecture

### Module layout

```
apps/api/src/relaydesk/
  main.py
  config.py
  cli.py                 seed / bootstrap commands
  db/
    base.py              DeclarativeBase, UUID primary key + timestamp mixins
    session.py           async engine, sessionmaker, get_session dependency
  models/
    __init__.py          imports every model so Alembic metadata is complete
    workspace.py user.py membership.py session.py invite.py
    contact.py conversation.py message.py label.py activity.py
    draft.py saved_view.py
  schemas/               Pydantic request/response models
  services/              domain logic; never imports FastAPI
  api/
    router.py
    deps.py              get_session, current_user, workspace_scope
    health.py auth.py workspace.py team.py conversations.py labels.py views.py
  security/
    passwords.py         argon2id hashing
    tokens.py            opaque token generation and hashing
    oauth_google.py
  errors.py              AppError hierarchy
```

### Boundaries

Routers handle HTTP. Services hold domain logic. Models handle persistence.

Service functions take an `AsyncSession` and an explicit `workspace_id`, and
know nothing about requests. This is the boundary that matters: slice 2's
channel ingest and slice 4's job runner call the same
`services.conversations.create()` the HTTP layer calls, rather than
duplicating conversation creation per entry point.

### Wire format

Pydantic schemas set `alias_generator=to_camel` and `populate_by_name=True`.
Python stays snake_case; JSON matches `lib/mock/types.ts` field for field.

### Sessions

Login returns a 256-bit URL-safe random token in the JSON body. Only its
SHA-256 hash is stored, in `sessions`, alongside `expires_at`, `last_seen_at`,
user agent, and IP. Next.js stores the token in its own HttpOnly, SameSite=Lax
cookie (Secure when `APP_ENV != development`) and sends it as
`Authorization: Bearer <token>` on every server-side call.

Bearer rather than an API-set cookie because the browser only ever talks to the
web origin: cross-origin `Set-Cookie` forwarding is fragile, and a bearer header
means slice 2's Tickets API keys authenticate through the same dependency.

Session TTL is 30 days, configurable. `last_seen_at` is updated at most once per
hour to avoid a write on every request.

### Google OAuth

1. Web requests `GET /api/auth/google/url?redirectUri=` and receives an
   authorization URL plus a `state` value it stores in a short-lived cookie.
2. Google redirects to a callback on the **web** origin. That URL is what gets
   registered in the Google Cloud console.
3. The web posts the code and state to `POST /api/auth/google/exchange`.
4. The API exchanges the code at Google's token endpoint, reads the profile
   from the userinfo endpoint, and requires `email_verified`.

The userinfo call is server-to-server over TLS, so no `id_token` JWKS
verification and therefore no additional auth dependency is needed.

Identity is upserted into `user_identities` keyed on
`(provider, provider_account_id)`. A Google login for an email that already has
a password account links to that user rather than creating a second one.

Because there is no self-serve signup, Google login succeeds only for an email
that already has an active membership; anything else is rejected with
`unauthorized`. Invite acceptance is password-only in this slice. Accepting an
invite with Google is a deliberate omission, not an oversight: it would require
carrying the invite token through the OAuth round trip, and an invited user can
set a password and link Google afterwards.

### Tenancy enforcement

A `workspace_scope` dependency resolves bearer token to session, session to
user, user to active membership, and membership to workspace, and yields all
of them. Cross-workspace identifiers return **404, not 403**, so identifiers
cannot be probed for existence.

Every domain table carries `workspace_id` directly, including `messages` and
`drafts`, which could otherwise reach it through `conversation_id`. The
redundancy buys a single-predicate tenant filter on every query and turns a
leak into a visibly missing `WHERE` clause rather than a missing join.

## 4. Data model

Postgres. UUID primary keys, `created_at` / `updated_at` on every table.
Enums use `sa.Enum(..., native_enum=False)`, compiling to `VARCHAR + CHECK`, so
adding a status or channel later is a constraint swap rather than an
`ALTER TYPE` migration.

### Identity and tenancy

**workspaces** — `name`, `slug` (unique), `monogram`, `timezone`,
`conversation_seq` (integer counter).

**users** — `email` (citext, unique), `name`, `password_hash` (nullable;
Google-only users have none), `monogram`, `timezone`, `failed_login_count`,
`locked_until`.

**user_identities** — `user_id`, `provider`, `provider_account_id`,
unique on `(provider, provider_account_id)`.

**memberships** — `workspace_id`, `user_id`, `role` (`admin` | `agent`),
`status` (`active` | `invited`), unique on `(workspace_id, user_id)`.

**sessions** — `user_id`, `token_hash` (unique), `expires_at`, `last_seen_at`,
`user_agent`, `ip`.

**invites** — `workspace_id`, `email`, `role`, `token_hash`, `invited_by`,
`expires_at`, `accepted_at`.

### Inbox

**contacts** — `workspace_id`, `email`, `name`, unique on
`(workspace_id, email)`.

**conversations** — `workspace_id`, `number`, `subject`, `contact_id`,
`channel` (`email` | `discord` | `portal` | `api`), `status` (`open` |
`pending` | `resolved` | `on_hold` | `ignored` | `trash`), `priority`
(`urgent` | `high` | `medium` | `low`), `assignee_id` (nullable),
`preview`, `last_message_at`, `unread`, `summary` (nullable),
`summary_state` (`none` | `ready` | `failed`).

Indexes: `(workspace_id, status, last_message_at DESC)` for the inbox list,
unique `(workspace_id, number)`.

**conversation_labels** — join table on `(conversation_id, label_id)`.

**labels** — `workspace_id`, `name`, `color` (`citron` | `slate` | `amber` |
`rose` | `sky`), unique on `(workspace_id, name)`.

**messages** — `workspace_id`, `conversation_id`, `role` (`customer` |
`agent` | `ai`), `author_name`, `author_user_id` (nullable), `to_address`,
`body`, `sent_at`. Index on `(conversation_id, sent_at)`.

**drafts** — `workspace_id`, `conversation_id` (unique), `body`.
`hasDraft` is the existence of a row.

**activity_events** — `workspace_id`, `conversation_id`, `actor_user_id`
(nullable), `actor_name`, `kind` (`created` | `status` | `priority` |
`assignee` | `label` | `reply`), `verb`, `value`, `status` (nullable), `at`.

**saved_views** — `workspace_id`, `name`, `filters` (JSONB), `position`.

### Model decisions

- **`contacts` exists now**, even though the API flattens it into
  `customerName` / `customerEmail`. Slice 2 needs stable customer identity to
  thread inbound email onto an existing conversation; retrofitting it later
  would mean backfilling every row and changing the response shape.
- **`number` is per-workspace sequential**, allocated inside the create
  transaction by `UPDATE workspaces SET conversation_seq = conversation_seq + 1
  ... RETURNING`. No global sequence, so ticket volume does not leak across
  tenants.
- **`preview` and `last_message_at` are denormalized** onto the conversation and
  written on every message insert. The inbox list is the hottest query in the
  product and must not join to messages to render a row.
- **`age` and `date` are computed server-side** from `last_message_at` in the
  workspace timezone. No console component formats dates today, and the type
  contract asks for the formatted strings.
- **No speculative channel columns.** `direction`, `external_id`,
  `raw_message_id`, `in_reply_to`, `body_html`, and `channel_account_id` belong
  to slice 2 and are added by its own migration. There is no production data to
  backfill, so adding them now would only produce fields nothing writes.

## 5. API surface

All routes are under `/api`, return camelCase JSON, and require a bearer token
except where marked public.

### Auth

```
POST   /auth/login                    { email, password } -> { token, expiresAt }
GET    /auth/google/url?redirectUri   -> { url, state }                 public
POST   /auth/google/exchange          { code, state, redirectUri } -> { token, expiresAt }   public
POST   /auth/logout
GET    /auth/me                       -> { user, workspace, membership }
```

### Workspace

```
GET    /workspace                     -> name, monogram, timezone, seats,
                                         plan, trialDaysLeft,
                                         ticketsThisPeriod, projectedTickets
PATCH  /workspace                     admin only
GET    /workspace/setup-tasks         -> SetupTask[]
```

`seats` is a real count of active memberships. `plan`, `trialDaysLeft`,
`ticketsThisPeriod`, and `projectedTickets` are read by the trial banner, the
trial strip, and the billing page, none of which have a backend until slice 7;
they are served as fixed placeholder values from workspace columns so those
screens render, and slice 7 replaces the source without changing the response.

`setup-tasks` computes the sidebar checklist from real state rather than storing
booleans that drift: team invited is more than one membership, first label
created is a label count, and so on. Channel, portal, triage, and billing tasks
report `done: false` until their slices exist.

### Team

```
GET    /team                          -> TeamMember[]
POST   /team/invites                  { email, role } -> { id, inviteUrl }   admin only
DELETE /team/invites/{id}                                                    admin only
PATCH  /team/members/{id}             { role }                               admin only
DELETE /team/members/{id}                                                    admin only
GET    /invites/{token}               -> { workspaceName, email, role }      public
POST   /invites/{token}/accept        { name, password } -> { token }        public
```

No email is sent in this slice. The console surfaces a copyable invite URL.

### Inbox

```
GET    /conversations?status&labelId&assigneeId&viewId&limit&cursor
                                      -> { items: Conversation[], nextCursor }
GET    /conversations/counts          -> { statuses: StatusCount[], drafts }
GET    /conversations/{id}            -> Conversation
PATCH  /conversations/{id}            { status?, priority?, assigneeId? }
POST   /conversations/bulk-status     { ids, status }
GET    /conversations/{id}/messages   -> Message[]
POST   /conversations/{id}/replies    { body, resolve }
GET    /conversations/{id}/draft      -> { body } | 404
DELETE /conversations/{id}/draft
GET    /conversations/{id}/activity   -> ActivityEvent[]
PUT    /conversations/{id}/labels/{labelId}
DELETE /conversations/{id}/labels/{labelId}
GET    /labels                        -> Label[]
POST   /labels                        { name } -> Label
GET    /views                         -> SavedView[]
```

`GET /conversations` is paginated with a default limit of 50. An unbounded
inbox query is a problem that arrives quietly and late. The frontend seam
unwraps `items` and ignores `nextCursor` for now, so paging can be surfaced
later without an API change.

Every mutation writes an `activity_events` row through the service layer, so
the detail panel's history is a consequence of the mutation rather than a
second thing callers must remember to do.

Label toggling is split into `PUT` and `DELETE` rather than a single toggle
endpoint, so a retried request is idempotent.

## 6. Frontend rewiring

- `lib/mock/types.ts` moves to `lib/types.ts`, with a one-line re-export left at
  the old path. `lib/mock/{analytics,settings,knowledge-base}.ts` remain mocks
  belonging to later slices and compile with zero edits.
- New `lib/api/client.ts`: server-only fetch wrapper providing the base URL, the
  bearer header read from the session cookie, `cache: "no-store"`, and mapping
  of the error envelope to typed throws.
- New `lib/api/{conversations,workspace,team,labels}.ts` export the same
  function names and signatures the mock stores export.
  `lib/mock/conversations.ts` is deleted. `lib/mock/workspace.ts` is reduced to
  `getPortalSettings`, which four files including the public portal import and
  which belongs to slice 5.
- `statuses`, the status ordering used by the inbox toolbar, stays a static
  constant and moves to `lib/types.ts`. It is a fixed enumeration, not data, and
  should not become a fetch.
- `middleware.ts` redirects unauthenticated console and user-portal-admin routes
  to `/login`.
- `app/(auth)/login/actions.ts` performs a real credential exchange, sets the
  cookie, and returns field errors on failure.
- `app/(console)/conversations/actions.ts` keeps its shape; bodies call the API
  and `revalidatePath` stays.

Three knock-on edits, all mechanical but worth naming because they are the only
places a page body changes:

- `workspace` and `currentUser` are synchronous module constants today, imported
  across ten files (both console and settings layouts, the user-portal layout,
  the team, billing, account, knowledge-base, analytics, conversations, and
  conversation-detail pages). They become awaited getters at each call site.
- `savedViews` is imported directly by `components/console/sidebar.tsx`, which
  is a **client component** and therefore cannot await. It becomes a prop passed
  down from the console layout, exactly as `labels` and `statusCounts` already
  are, and `SavedView` joins `lib/types.ts`.
- `generateSummaryAction` remains a no-op stub with a TODO until slice 4,
  because nothing generates summaries yet.

## 7. Errors and security

An `AppError` hierarchy — `NotFound`, `Unauthorized`, `Forbidden`, `Conflict`,
`Invalid` — is raised by services and mapped by FastAPI exception handlers to:

```json
{ "error": { "code": "not_found", "message": "Conversation not found" } }
```

Services stay HTTP-free; only the handler knows status codes. The web client
turns non-2xx into typed throws so server actions can distinguish an expired
session, which redirects to login, from a real failure.

Login throttling: `failed_login_count` and `locked_until` on the user row, with
an exponential lockout window. An open-source product has its `/auth/login`
scanned within hours of being exposed, and unlimited argon2 attempts is also a
cheap CPU denial of service.

Password hashing is argon2id with the `argon2-cffi` defaults. Session and invite
tokens are compared by hash, never by plaintext lookup.

## 8. Testing

pytest with pytest-asyncio and httpx `ASGITransport`, so no live server is
needed, running against **real Postgres**. asyncpg, citext, JSONB, and enum
check constraints all behave differently on SQLite, and a green suite that lies
is worse than no suite.

A session-scoped fixture creates a test database and runs `alembic upgrade head`
against it, so the migrations themselves are what is tested rather than
`create_all`. Each test runs inside a transaction rolled back at teardown.
Fixtures are plain factory helpers; no `factory_boy`.

Coverage expectations:

- Service-level tests for every mutation, asserting the activity event it emits.
- Router tests for auth, invites, and the full conversation surface.
- A dedicated tenant-isolation module asserting that every conversation, label,
  and team endpoint returns 404 for an identifier belonging to another
  workspace. This is the failure mode with the worst consequences and the least
  chance of being caught by hand.
- Login throttling and session expiry.

Development follows TDD, per the repository workflow.

## 9. Dependencies, migrations, and seeding

New runtime dependencies: `argon2-cffi`, `email-validator`, and `httpx`
promoted from the dev group. New dev dependency: `pytest-asyncio`.

Alembic gets `target_metadata = Base.metadata`, with every model imported in
`models/__init__.py`. The API container runs `alembic upgrade head` on start.
`make migrate` and `make revision m="..."` are added for humans.

`make seed` builds the demo workspace: "Chronon", an admin and an agent, the
four labels, the saved views, and the same ten conversations with their
threads, activity, and drafts that `lib/mock/conversations.ts` holds today. A
fresh clone therefore presents the console exactly as it looks now.

`relaydesk bootstrap` creates an empty workspace and a first admin from
environment variables. This is what a self-hoster actually runs.

New settings in `config.py` and `.env.example`: `SESSION_TTL_DAYS`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `WEB_URL`.

## 10. Delivery order

1. `db/base`, Alembic metadata wiring, test harness
2. Workspaces, users, memberships, sessions, password login, `/auth/me`
3. Web: middleware, real login, cookie handling — first end-to-end vertical
4. Google OAuth
5. Team, invites, accept flow
6. Contacts, conversations, messages, labels, activity, drafts — models and reads
7. Web: console reads rewired (list, detail, sidebar counts)
8. Mutations and activity-event generation
9. Saved views
10. Seed and bootstrap commands, README updates

Step 3 is early on purpose. It is the first point at which a real login lands in
a real console, and it proves the cookie and bearer seam before nine further
steps are built on top of it.

## 11. Known future consumers

Recorded so later slices can be checked against this model rather than
rediscovering its constraints.

**Email, slice 2.** Every source — IMAP polling, the Gmail API, an inbound
webhook, the portal form, the Tickets API — normalizes to one `InboundMessage`
and runs a single pipeline: normalize, dedupe, resolve thread, upsert contact,
create or append conversation and message, emit activity, enqueue AI jobs.
Deduplication is a unique index on `(channel_account_id, external_id)`, making
replayed webhooks and re-polled UIDs no-ops. Thread resolution tries, in order:
a reply-address token (`support+c_9d6d5cd1@`), RFC 5322
`References` / `In-Reply-To` matched against stored message identifiers, and
finally the same contact with a subject-stripped match inside a short window.
Outbound sending must store the Message-ID returned by the SMTP server, or
customer replies have nothing to thread onto. Slice 2 adds `channel_accounts`,
`attachments`, `raw_messages`, and the six message columns listed in section 4.

**Portal ticket list, slice 2.** Customers will see their own tickets and
threads in the portal, authenticated by emailed magic link rather than a
password. It needs portal contact sessions, per-contact authorization scoped
through `contacts.id`, and outbound email to deliver the link, so it belongs
with the channels slice.

**AI surfaces, slice 4.** Drafts and summaries are stored and served by this
slice but never generated. Slice 4 fills `drafts.body` and
`conversations.summary` / `summary_state` and implements
`generateSummaryAction`, requiring no migration or response-schema change.
