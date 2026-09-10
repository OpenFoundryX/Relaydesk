# Support widget — design

**Date:** 2026-09-10
**Status:** approved in chat, pending written review
**Slice:** 8 (follows slice 7, custom webhooks)

Builds on `2026-09-04-tenancy-and-inbox-core-design.md` (slice 1), which
remains binding for multi-tenancy, admin gating and the error envelope; on
`2026-09-05-knowledge-base-design.md` (slice 3), whose published-article
visibility rules this slice reuses unchanged; on
`2026-09-06-public-ticket-submission-design.md` (slice 4), whose submission
path and rate limits this slice reuses; and on
`2026-09-08-api-keys-and-public-api-design.md` (slice 6), whose
credential-handling patterns this slice follows where it can and departs from
once, deliberately (D1). Where this document is silent, slice 1 governs.

## 1. What this builds

A workspace pastes one `<script>` tag into its own website. Its customers get
a launcher in the corner that opens a panel: they search the workspace's
published knowledge base, read an article, and — only if that did not answer
them — send a message that becomes a conversation in the inbox. The reply
arrives by email, through the channel that already exists.

This is the shortest path Relaydesk has from signup to a working support
channel. Email, the only channel today, requires a domain, forwarding rules
and deliverability that works. The widget requires a copy and a paste. For
the audience this product is for — small teams, little tolerance for setup —
that difference is the product.

It is also the first honest measurement of deflection. Sessions that
searched, sessions that read an article, and sessions that filed a message
are recorded here, so the ratio exists before any AI does. A deflection
number produced later by an AI slice can then be compared against a baseline
this workspace actually observed, rather than against a vendor's published
figure.

## 2. What already exists, and what it obliges

Unusually for a slice this size, the entire backend is already built and
tested. `apps/api/src/relaydesk/api/public.py` exposes every call the widget
makes:

| Endpoint | Widget use |
|---|---|
| `GET /public/workspaces/{slug}` | workspace name and monogram |
| `GET /public/{slug}/kb` | collection index |
| `GET /public/{slug}/kb/search` | server-side search |
| `GET /public/{slug}/kb/search/index` | prebuilt client-side search index |
| `GET /public/{slug}/kb/{path}` | article |
| `POST /public/{slug}/tickets` | submit |

So this slice adds a credential, a way to address a workspace by it, a
front-end, and nothing else to the domain. The services underneath —
`kb_public`, `tickets`, `contacts` — are reused as they are.

Three things constrain the design rather than merely enabling it.

**The search endpoints already exist** because the portal needs them —
both a query endpoint and a prebuilt index the help site scores in the
browser. The widget uses the query endpoint and leaves the index alone; D8
records why the reverse would cost more than it saves here.

**`Contact` is `UniqueConstraint(workspace_id, email)`.** Email is identity.
A submission with a new address creates a contact; a repeat submission
attaches to the existing one. The widget does not need to know which.

**The portal's own client-IP handling is broken behind a proxy**, and the
widget inherits it (D9). This slice has to fix it, because the widget is the
surface where it bites hardest.

There is no widget UI shell in `apps/web/lib/mock/settings.ts` — unlike
`settings/ai-triage` and `settings/mcp-servers`, nothing here has been
pre-drawn, so no published contract constrains the console screens.

## 3. Decisions

**D1 — A widget key is published, not secret, and is stored in plaintext.**

`ApiKey` keeps only a SHA-256 digest and shows its secret exactly once.
That is correct for a bearer token and impossible here: a widget key is
printed in the page source of every site that embeds it, and an admin must be
able to read it back forever to re-paste the snippet. A digest cannot serve a
credential that is public by construction.

The alternative — reusing `ApiKey` with a `public` scope — was rejected on
both counts. It cannot re-display the key, and a public credential sharing a
table with bearer tokens invites exactly one mistake: an `rd_live_` secret
pasted into a `<script>` tag because the two looked like the same kind of
thing. A separate model makes the categories unconfusable.

This is the second deliberate departure from slice 6's credential handling,
after `Webhook.secret` (slice 7, D2), and like that one it is recorded in the
model's docstring rather than left for a reader to infer.

**D2 — The origin allowlist is enforced with `frame-ancestors`, and it is
abuse control, not authorization.**

The panel is an iframe served from Relaydesk's own origin (D5), so the
customer's page never makes a cross-origin request and CORS is not involved.
What the allowlist governs is *who may embed the frame*, which is
`Content-Security-Policy: frame-ancestors`, sent per-request from the key's
`allowed_origins`.

Both `frame-ancestors` and CORS are enforced by the browser and by nothing
else. A script that is not a browser ignores them. The allowlist therefore
constrains honest embedders and casual copying; it stops no determined
caller. That is acceptable **only** because every endpoint reachable through
a widget key is already public: the knowledge base is a public help site and
ticket submission is already an open, unauthenticated endpoint. Holding a
widget key grants no privilege that anonymity did not already grant.

This is a load-bearing property, not an implementation note. If a future
slice gives the widget anything a stranger should not have — a thread view,
an account lookup, a customer's own tickets — this model is wrong for it and
must be replaced by a verified identity, not extended by adding origins.

**D3 — The widget addresses its workspace by key, never by slug.**

`/widget/{key}/…` mirrors `/public/{slug}/…`. The embed carries no slug, so a
workspace can rename itself without every customer re-pasting a script tag.
The key is also the only place a per-embed origin list, revocation and usage
metering can hang; a slug has nowhere to put them.

`data-workspace="canny"` was rejected despite being simpler and leaking
nothing — the slug is already public as a portal subdomain. It fails on
irreversibility (D6): a slug-shaped embed cannot later grow an origin list
without a second embed format.

**D4 — v1 is write-only. The widget files a message; it never reads a
conversation.**

There is no thread view and no `Authorization` on any widget call. The
consequence is the one that matters: an email supplied by the host page
(`data-email`) is **prefill, not an authentication claim**. Nothing can be
read with it, so impersonating an address achieves only what the existing
public ticket form already allows, and signed identity (HMAC of the user id,
as Intercom requires) is not needed.

Shipping a thread view in v1 was rejected. It converts the key into a read
credential over customer conversations, which makes D2's honest limit
unacceptable and forces verified identity, per-viewer authorization and a
session concept into a slice that otherwise has none.

**D5 — The panel is an iframe, not Shadow DOM.**

The widget renders inside strangers' websites, against CSS and JavaScript it
has never seen. An iframe gets its own origin, its own stylesheet, its own
CSP, and cannot be restyled or broken by the host page.

Shadow DOM was rejected. It isolates CSS but shares the JavaScript global
scope, and the host page's CSP still governs the styles injected into it — so
its failure mode is "the widget looks wrong on this one customer's site",
which arrives as a support ticket that is expensive to reproduce and
impossible to fix generally.

The cost is `postMessage` for open, close and resize, and a launcher button
that lives outside the frame and must therefore be styled by the loader with
inline styles only.

**D6 — The loader is deliberately dumb, and its contract is frozen.**

The `<script>` tag is the only part of this system that cannot be changed
after it ships: it is pasted into sites Relaydesk does not control and will
not be re-pasted. So the loader reads the key, draws a launcher, and injects
an iframe. Nothing else. Every decision that might need revisiting lives
inside the frame, which is served fresh on every open.

This is also why the loader is served from a stable, unversioned URL
(`/widget.js`) while the code it loads is versioned internally. A versioned
embed URL would freeze customers on whatever shipped the day they installed.

**D7 — An empty knowledge base is a first-class state, not an edge case.**

Every workspace installs the widget with zero articles, because a team
drowning in support is precisely a team that has not written a help centre.
So the widget detects an empty or near-empty knowledge base and renders the
message form directly, with no search field at all.

The alternative — search over nothing, returning "no results" — was rejected
because it makes the product look broken on the one day a new customer is
deciding whether to keep it.

**D8 — Search runs on submit, through the server.**

The panel's search field submits rather than searching as you type, and the
frame asks the server for each submitted query. There is therefore no
request per keystroke to avoid.

This reverses an earlier draft of this decision, which had the frame fetch
`/kb/search/index` once on open and score it in the browser the way the
public help site does. That is right for the help site, where a visitor has
already committed to a full page load, and wrong here: the index is the
whole published knowledge base, and shipping it on panel open contradicts
the one number this widget is sold on — a loader under 3 KB and nothing
else fetched until someone clicks (D6). A workspace with several hundred
articles would pay for instant search with exactly the weight the embed
promises not to add.

`GET /widget/{key}/kb/search/index` remains, unused by the frame today. It
is what an instant-search pass would adopt for workspaces whose index is
small enough to be worth shipping, and it already serves the portal.

The residual cost is that search is an anonymous endpoint with no cap of
its own, reached once per submitted query. It reads only published
articles — the same rows the public help site serves to anyone — so the
exposure is load, not disclosure. If that load ever matters, the per-key
hourly cap in §8 is the place to extend.

**D9 — Submission goes through a server action, and the client-IP chain must
be repaired first.**

The frame is a Next route, so its form follows the portal's pattern from
slice 4: a server action forwards the submission and the caller's address to
the API, and the API believes `X-Forwarded-For` only from a peer in
`TRUSTED_PROXY_IPS`.

That pattern is currently correct only when Next is exposed directly to the
internet. `apps/web/middleware.ts` deletes `x-forwarded-for` so that Next
refills it from `socket.remoteAddress` — which, behind the reverse proxy any
production deployment requires, is the proxy's address and not the visitor's.
Every submission then shares one bucket, and `TICKET_IP_HOURLY_CAP` throttles
the entire internet to five messages an hour rather than five per visitor.
The failure is silent and fails *closed*.

The fix is in three parts and belongs to this slice:

1. The reverse proxy trusts only its own upstream edge and derives
   `X-Forwarded-For` from it.
2. The web container is reachable only from the proxy and publishes no port,
   which is what makes the incoming header trustworthy.
3. Given (2), the middleware stops deleting `x-forwarded-for` and preserves
   it. The comment above that deletion is sound reasoning for a
   directly-exposed Next server and simply does not hold once a proxy exists;
   it should be rewritten, not removed silently.

Submitting straight from the frame's JavaScript to the API — which would give
the API the visitor's address with no chain at all — was rejected for
consistency with slice 4. The defect above has to be fixed for the portal
regardless, so the widget gains nothing by routing around it.

**D10 — Configuration is per key, not per workspace.**

Launcher colour, position, greeting and whether the message form is enabled
hang off the `WidgetKey`. A workspace running a marketing site and a
logged-in app can then embed two keys with different settings and revoke one
without touching the other.

*Un-deferred in a later slice.* `name`, `greeting`, `accentColour` and
`position` are validated in `services/widget_keys.py` (a hex colour, a
`left`/`right` literal, capped string lengths -- this is admin input that
ends up in an inline style and in the loader's own attributes, on a
stranger's page), editable from a Branding section in the console's
`WidgetKeyDialog`, and rendered: the configured name and greeting replace
the workspace name and default copy in the panel (`components/widget/`),
and `data-accent`/`data-position` on the generated `<script>` tag replace
the loader's hard-coded launcher colour and corner (`public/widget.js`) --
read from the tag itself, not the bootstrap call, so the launcher's first
paint still costs no request (D6). The console says plainly that changing
either one means re-pasting the snippet.

`iconUrl` is validated the same way but not rendered anywhere yet: reusing
the knowledge-base image pipeline (`services/blobs.py`, `KbImage`) would
need a new upload endpoint, a nullable `article_id` or a sibling model, and
a new serving route, which is more than this pass added -- see that
slice's report. Whether the message form itself can be disabled per key
remains deferred, unchanged.

## 4. Schema

Two tables.

```
widget_keys
  id                 uuid, pk
  workspace_id       uuid, fk -> workspaces, on delete cascade, indexed
  name               varchar(120), not null
  key                varchar(64), unique, not null       -- "rdw_" + 32 hex
  allowed_origins    jsonb, not null, default '[]'
  settings           jsonb, not null, default '{}'
  active             boolean, not null, default true
  created_by_user_id uuid, fk -> users, nullable
  last_seen_at       timestamptz, nullable
  created_at         timestamptz, not null
  updated_at         timestamptz, not null
```

`key` is stored in plaintext (D1) and its docstring must say so, and say why,
next to a note that `ApiKey` does the opposite.

`allowed_origins` holds exact origins — scheme, host and port, no path, no
wildcard. `https://acme.com` and `https://www.acme.com` are two entries.
Wildcard patterns are rejected in v1: `*.acme.com` matchers are where origin
checking quietly breaks, and an empty list is treated as "not yet
configured", which refuses embedding rather than allowing it.

`settings` is a JSONB blob rather than columns because none of it is queried
and all of it is presentational (D10).

`revoked_at` is deliberately absent. Unlike a bearer token, a widget key
carries no history worth auditing after revocation — deleting the row is the
revocation, and the embed then fails closed.

The second table is what makes §1's deflection claim real.

```
widget_sessions
  id             uuid, pk            -- minted by the frame, opaque
  workspace_id   uuid, fk -> workspaces, on delete cascade, indexed
  widget_key_id  uuid, fk -> widget_keys, on delete cascade
  searched       boolean, not null, default false
  read_article   boolean, not null, default false
  submitted      boolean, not null, default false
  started_at     timestamptz, not null
  updated_at     timestamptz, not null
```

One row per panel open, with flags raised as the session progresses, rather
than one row per event. A visitor who searches four times writes one row, the
ratio is a single query, and there is no event stream to prune.

It exists because deflection cannot be measured retroactively. A workspace
that installs the widget in March and adds an AI slice in June can only
compare the two if March was instrumented, and the whole argument for
building this before the AI work is that it produces a baseline the customer
observed rather than one a vendor published.

The honest ratio is: of sessions that tried to self-serve — `searched or
read_article` — the share that did not go on to `submit`. Sessions that did
neither are not deflection either way and are excluded from the denominator.

`ActivityEvent` was the obvious home and cannot serve: its `conversation_id`
is `NOT NULL`, and the sessions worth counting are precisely the ones that
never produced a conversation.

The row holds no address, no email, no query text and no article content —
only three booleans and an opaque id the frame mints. There is nothing here
to attribute to a person, which is what keeps a table recording the behaviour
of other companies' customers proportionate.

## 5. API surface

A `/widget/{key}` router. Every route resolves the key to a workspace,
refuses an inactive or unknown key with the standard error envelope, and then
delegates to the same service functions the public router uses.

```
GET  /widget/{key}                 workspace name, monogram, settings, kb emptiness
GET  /widget/{key}/kb              collections
GET  /widget/{key}/kb/search/index prebuilt search index
GET  /widget/{key}/kb/search       server-side search, for oversized indexes (D8)
GET  /widget/{key}/kb/{path}       article
POST /widget/{key}/tickets         submit
```

The response to `GET /widget/{key}` carries an `article_count` so the frame
can choose the empty-KB rendering (D7) in its first paint rather than after a
second request.

Console routes, admin-gated per slice 1: list, create, update and delete
widget keys under `/workspaces/{id}/widget-keys`.

An unknown key returns the same shape as an inactive one. Distinguishing them
would let a caller probe which keys exist.

## 6. The embed contract

```html
<script async src="https://app.relaydesk.dev/widget.js" data-key="rdw_…"></script>
```

Optional `data-email` and `data-name` prefill the form (D4).

The loader is under 3 KB, loads asynchronously, and draws only the launcher.
React and the panel load inside the iframe on first open, so a site that
embeds the widget and is never clicked pays one small request. That budget is
a requirement, not an aspiration: it is the argument for choosing this over
Intercom's messenger, and a regression in it is a regression in the pitch.

`frame-ancestors` is sent on the frame response, computed from
`allowed_origins` (D2).

## 7. Interface design

The design is drafted across nine states — launcher, home, search results,
article, message form, sent, empty knowledge base, dark, and mobile. It
follows `apps/web/tailwind.config.ts` exactly: the `ink` scale for every
neutral, `accent` citron confined to focus rings, marks and active states,
`rounded-md` controls at `h-9`, `rounded-xl` cards on `border-ink-200`, and
the portal's `bg-ink-950` band with its `accent-600/20` glow. The widget is
the portal one size smaller: same tokens, less chrome.

Three rules the states encode.

**Search outranks the message form on every screen.** On home, "Send a
message" is a secondary, outlined control. After a search returns results, or
at the foot of an article, it becomes the primary filled button — the visitor
has tried to self-serve, so escalation is now the right action. The
progression is the deflection strategy expressed as hierarchy, and flattening
it removes the strategy.

**Dark mode follows `prefers-color-scheme`.** Cross-origin, the frame cannot
read the host page's theme; there is no other signal. A light widget on a
dark site is therefore possible and is documented rather than worked around.
In dark, citron carries the primary action, because `ink-900` on `ink-800`
does not exist as a button.

**Mobile is a full-screen takeover**, not a shrunken panel, with 44px minimum
targets and no painted status bar.

Accessibility is not optional here: this markup is injected into other
people's sites, and an inaccessible widget becomes their compliance problem.
Focus is trapped while the panel is open, `Esc` closes and returns focus to
the launcher, results are announced with `aria-live`, the launcher is
labelled, and the open transition respects `prefers-reduced-motion`.

The launcher's `z-index` sits high but well below the maximum, so a host
page's own modals can still cover it.

## 8. Abuse and rate limiting

Submission reuses slice 4's per-IP cap unchanged, which works correctly only
once D9 lands.

A per-key hourly cap is added alongside it, so one abused embed exhausts its
own budget rather than the workspace's. Search costs nothing (D8), and the
read endpoints are cacheable and already public.

`last_seen_at` is written at most once a minute per key — enough to answer
"is this embed still installed?" without a write per page view.

## 9. Testing

Origin matching carries the risk and gets the most tests: exact match,
trailing slash, explicit and implicit ports, scheme mismatch, the `null`
origin a sandboxed iframe sends, and an empty allowlist refusing rather than
permitting.

Beyond that: key resolution for unknown, inactive and deleted keys returning
identical responses; `frame-ancestors` present and correct on the frame
response; submission through the widget route creating a conversation
attributed to the right workspace; both rate limits; and a regression test
for D9 asserting that two submissions from different addresses through a
trusted proxy land in different buckets.

## 10. Out of scope

Live chat, agent presence and typing indicators. A thread view, and with it
signed identity (D4). Proactive or outbound messages. AI answers in the
widget — when the inference substrate exists, the widget is where the answer
gets rendered, and it needs nothing from this slice to become that. Wildcard
origins. Per-key analytics beyond the deflection counters in §1.
