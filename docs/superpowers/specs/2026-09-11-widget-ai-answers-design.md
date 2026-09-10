# AI answers in the widget — design

**Date:** 2026-09-11
**Status:** draft, pending review
**Slice:** 9 (follows slice 8, the support widget)

Builds on `2026-09-04-tenancy-and-inbox-core-design.md` (slice 1), binding for
multi-tenancy and the error envelope; on `2026-09-05-knowledge-base-design.md`
(slice 3), whose published-article visibility rules bound what may be
retrieved; and on `2026-09-10-support-widget-design.md` (slice 8), whose D2
and D4 this slice deliberately preserves rather than retires. Where this
document is silent, slice 1 governs.

## 1. What this builds

The widget's panel becomes a conversation. A visitor asks a question in plain
language; Relaydesk retrieves the workspace's published articles, answers
from them, and links the articles it used. When it cannot answer, it hands
the visitor to the message form that exists today, and the transcript travels
with the ticket so the human sees what the visitor was already told.

The panel keeps a single session. There is no list of past conversations, no
history to return to, and nothing the widget can read back. That is a
deliberate limit, not an oversight — §3 D2 explains what it buys.

## 2. What already exists, and what it obliges

Slice 8 left this slice a working surface. `api/widget.py` already serves KB
collections, search, a prebuilt search index, article resolution, ticket
submission and deflection counters, all addressed by a publishable key and
reachable anonymously. The panel already renders, escalates and counts.

Three things constrain the design rather than merely enabling it.

**Nothing in this codebase calls a model.** No provider dependency, no key
configuration, no retrieval index, no inference of any kind. The AI-shaped
console pages that exist — `settings/ai-triage`, `settings/mcp-servers`,
`settings/automations` — render from `lib/mock/settings.ts` and have no
backend. `Conversation.summary`, `Conversation.summary_state` and
`MessageRole.ai` are columns and an enum member that nothing writes. This
slice is the first that does.

**The widget is anonymous and its key is published in page source.** Every
endpoint added here is reachable by anyone who views a customer's HTML. Slice
8 could accept that because everything reachable was already public. An
endpoint that *spends the workspace's money* is not, which is why cost is
treated as an abuse surface in D5 rather than as an operational detail.

**Slice 8's D2 states the condition under which its security model breaks:**
"If a future slice gives the widget anything a stranger should not have — a
thread view, an account lookup, a customer's own tickets — this model is
wrong for it and must be replaced by a verified identity, not extended by
adding origins." This slice adds none of those, deliberately (D2 below), so
slice 8's model holds unchanged and no identity work is required.

## 3. Decisions

**D1 — One provider interface, Anthropic first, key and model per
workspace.**

A single `Provider` protocol with one implementation. The default model is
`claude-opus-5`; the workspace may choose another. Model choice and spend are
the customer's call, not ours — a workspace that wants `claude-haiku-4-5` at
a fifth of the input price should be able to say so without editing code.

Bring-your-own-key is the point rather than a convenience. This is an AGPL,
self-hostable support desk whose customers' transcripts are the input; a
deployment that could only send them to a vendor Relaydesk chose would be
unusable for exactly the teams most likely to self-host. The same interface
is what a self-hosted-inference implementation plugs into later.

The API key is **write-only**: set through the console, never returned by any
endpoint, displayed only as a masked suffix. This departs from `Webhook.secret`,
which is stored in plaintext and *is* returned, because a webhook signature
needs the same key at both ends and a model key does not — nothing but the
server ever needs to read it. It cannot be a digest either, since the value
must be replayed to the provider, so the exposure a database compromise
carries is real and is recorded in the model's docstring, as slice 7 recorded
its own.

**D2 — The widget stays write-only. No conversation list, no history.**

The panel holds one session in the browser. Nothing is read back, and a
reload starts fresh.

The alternative — the conversation list every commercial messenger shows —
was rejected for this slice on cost, not taste. Reading a visitor's past
conversations requires knowing *which* visitor, which requires verified
identity: an HMAC of the user id signed by the host application, per-viewer
authorization on every read, and a session concept the widget does not have.
Slice 8's D4 named that price in advance. It also lands on the customer, who
must sign an identifier server-side — a long way from the copy-and-paste
onboarding that justified building a widget at all.

The history list is separable and can be built later without redoing this
slice. What it cannot be is retrofitted quietly: the day the widget reads a
conversation, `data-email` stops being prefill and becomes an impersonation
vector, and identity must already be in place.

**D3 — An answer is grounded or it is not given.**

Retrieval runs first. It asks for the top 5 published articles and keeps
those at or above a relevance floor, which starts at the midpoint of
Postgres's `ts_rank` for this corpus and is a tunable, not a constant — the
right value is a property of a workspace's writing, and the deflection
counters are what will eventually set it. If nothing clears the floor the
model is never called and the visitor is offered the message form. When the
model is called, its instructions permit only the retrieved articles as
source material, and it must return the identifiers of the articles it used.

Citations are **resolved server-side** from those identifiers to real
published paths. A model that invents an article id produces no link, because
the id resolves to nothing. This is what makes the links in the panel
references rather than plausible-looking URLs — the difference between
citing and appearing to cite.

**D4 — Every failure degrades to the widget that exists today.**

No key configured, provider unreachable, budget exhausted, retrieval below
the floor, the model declining to answer, or the model returning no usable
citation: in every case the panel falls back to search and the message form,
exactly as slice 8 shipped them.

Note what is *not* in that list: a confidence score. The provider does not
give us one, and inventing a proxy would be a number that looks like
evidence and is not. What stands in for it is two things that can actually
be observed — whether retrieval cleared its threshold before the call, and
whether the answer cited an article that resolves after it.

This is the load-bearing property of the whole slice. The AI is additive; the
widget without it is the widget that already works. It also means a workspace
that never configures a key sees no degradation and no error — it simply has
the product it had before.

**D5 — Cost is an abuse surface, and is capped like one.**

An anonymous endpoint that spends money on each call is a materially
different thing from an anonymous endpoint that reads public rows. Anyone who
views a customer's page source holds the key.

Three controls, all of which degrade per D4 rather than erroring:

- a per-key hourly call cap, following the pattern `POST /tickets` already
  uses;
- a per-workspace **daily token budget** with a hard stop, configured by the
  workspace. It defaults to 200,000 tokens a day — roughly a dollar at
  `claude-opus-5` input rates, and enough for a few hundred grounded answers
  — so that a workspace which enables the feature and forgets about it
  cannot wake up to a surprising bill;
- a circuit breaker on repeated provider failures, so an outage does not
  become a retry storm billed to the customer.

The budget is a spend ceiling, not an estimate. When it is reached the widget
stops calling the model until the window rolls over, and says nothing about
why — a visitor learning that a workspace has exhausted its AI budget is
information they should not have.

**D6 — The visitor's message is redacted before it leaves the deployment.**

Email addresses, telephone numbers and card-like digit runs are replaced with
placeholders before any text is sent to a provider. This is best-effort
pattern matching and the docstring must say so: it reduces routine leakage of
data a visitor volunteered, and it is not a guarantee.

Redaction is skipped when the configured provider is a self-hosted endpoint
the workspace controls, because the data never leaves their deployment and
redacting it would degrade the answer for no gain.

**D7 — Both the visitor's message and the knowledge base are untrusted
input.**

The visitor's text is attacker-controlled by definition. Article bodies are
written by workspace staff, which is not the same as trustworthy — a
workspace with many authors, or one that imported its help centre, cannot
vouch for every paragraph.

The mitigations are structural rather than a prompt asking nicely: the model
is given **no tools** in this slice, so there is nothing for an injected
instruction to invoke; citations resolve server-side (D3), so a fabricated
link cannot render; and the answer is rendered as text through the existing
`DocRenderer` path, which has no `dangerouslySetInnerHTML` anywhere.

**D8 — A resolved question creates no conversation. An escalated one carries
its transcript.**

Answering a visitor's question does not write a `Conversation`. A support
desk whose inbox fills with questions the AI already resolved has replaced a
support problem with a triage problem.

When the visitor escalates — by choosing to, or because D3/D4 sent them —
the ticket is created through the existing `tickets.submit` path with the
transcript included in the message body. The agent must be able to see what
the visitor was already told; answering a question the AI has already
answered differently is worse than not having answered at all.

**D9 — Answers stream.**

A grounded answer over retrieved articles takes seconds. In a chat surface
that reads as broken without token-by-token output, and the panel already
has the component structure to render it.

Streaming also bounds a real failure: a non-streamed call that exceeds the
HTTP timeout is billed and discarded.

**D10 — Retrieval starts with the Postgres full-text search that exists.**

`kb_public.search` and the prebuilt index already return published,
externally-scoped articles. Embeddings and a vector column are deferred until
measurement shows FTS is the limit — which is a question the deflection
counters from slice 8 can actually answer, because they record what visitors
searched and whether they escalated.

**D11 — Every inference call is recorded.**

Workspace, widget key, model, input and output tokens, computed cost,
latency, and the outcome — answered, escalated, refused, or degraded, with
which of D4's reasons applied.

This is what makes the deflection number defensible. Slice 8's §1 argued that
an AI deflection figure is only worth something if the workspace can audit
it; this table plus `widget_sessions` is that audit. It is also the only
honest basis for the cost-per-resolution figure the commercial layer will
eventually want.

## 4. Schema

Two tables.

```
ai_configs                       -- one per workspace
  workspace_id   uuid, pk, fk -> workspaces, on delete cascade
  provider       varchar(32), not null, default 'anthropic'
  model          varchar(64), not null, default 'claude-opus-5'
  api_key        text, nullable          -- write-only, never returned
  base_url       text, nullable          -- set for self-hosted inference
  daily_token_budget  integer, not null, default 200000
  enabled        boolean, not null, default false
  created_at, updated_at
```

`enabled` is separate from `api_key` being present so a workspace can turn
the feature off without discarding its configuration.

```
ai_calls                         -- the audit trail, D11
  id             uuid, pk
  workspace_id   uuid, fk -> workspaces, on delete cascade, indexed
  widget_key_id  uuid, fk -> widget_keys, on delete set null
  model          varchar(64), not null
  input_tokens   integer, not null
  output_tokens  integer, not null
  cost_micros    bigint, not null        -- integer micros, never a float
  latency_ms     integer, not null
  outcome        varchar(16), not null   -- answered | escalated | refused | degraded
  reason         varchar(32), nullable   -- which D4 condition, when degraded
  created_at
```

Cost is stored in integer micros because money in a float is a defect waiting
for a rounding argument. `widget_key_id` is `SET NULL` rather than cascade:
deleting an embed revokes it, and must not erase the record of what it spent.

No message content is stored in either table. The transcript exists in the
browser for the life of the panel and, on escalation only, in the ticket the
visitor chose to send.

## 5. API surface

Added to the existing anonymous `/widget/{key}` router, above its
`{path:path}` catch-all:

```
POST /widget/{key}/ask        streams an answer; body {question, history}
```

`history` is the client-held transcript, sent each turn — the server keeps no
session (D2). It is bounded in length and counts against the token budget
like any other input.

The response streams text, then a terminal event carrying the resolved
citations and the outcome. When any D4 condition applies, the terminal event
says `degraded` and the panel renders the search-and-form view instead.

Console routes, admin-gated: read and write `ai_configs`, with the key
write-only.

## 6. Testing

The parts worth pinning are the ones that fail quietly:

- **D3's grounding**: an answer naming an article id that does not exist
  produces no citation, and a retrieval that returns nothing never reaches
  the provider.
- **D4's degradation**: each of the six conditions independently produces the
  search-and-form view rather than an error.
- **D5's budget**: the call that would cross the ceiling does not happen, and
  the response is indistinguishable from any other degradation.
- **D6's redaction**: an email and a card-like digit run in the visitor's
  message do not appear in the provider payload.
- **D8**: a resolved question writes no `Conversation`; an escalated one
  writes exactly one, containing the transcript.
- **D11**: every call writes exactly one `ai_calls` row, including the
  refused and degraded paths.

The provider is behind a protocol (D1), so all of this is testable against a
fake without a network or a key. A single contract test exercises the real
implementation's request shape.

## 7. Out of scope

Conversation history and the identity work it requires (D2). Tool use — the
webhook tool registry from slice 7 is the natural home for it and stays
unused here (D7). Agent-authored replies on email tickets, conversation
summaries, auto-triage, and AutoQA: all of them want this slice's substrate,
and none of them wants to be designed before it exists. Embeddings (D10).
Per-key AI settings; configuration is per workspace, and a workspace running
two embeds gets the same answering behaviour on both.

## 8. What implementers must read first

The Anthropic SDK's surface has changed in ways that make a remembered
pattern actively wrong — `budget_tokens` is rejected on current models,
assistant prefill returns a 400, and `output_format` is superseded by
`output_config`. Anyone implementing this must load the `claude-api` skill
and read `python/claude-api/README.md` and `python/claude-api/streaming.md`
before writing a request, rather than working from recall.

Two settings this slice cares about: `thinking: {type: "adaptive"}`, and
`output_config: {effort: ...}` — support answering is a chat-shaped workload,
which typically does not repay high effort, so it starts at `low` and is
raised only if measurement justifies it. Prompt caching is worth its
breakpoint here: the system instructions and the retrieved articles are a
stable prefix across a conversation's turns, and the visitor's question is
the only volatile part.
