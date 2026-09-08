# Analytics — design

**Date:** 2026-09-08
**Status:** approved in chat, pending written review
**Slice:** 7 (follows slice 6, API keys and the public API)

Builds on `2026-09-04-tenancy-and-inbox-core-design.md` (slice 1), which
remains binding for multi-tenancy, sessions, the conversation and message
model, and the error envelope. Where this document is silent, slice 1 governs.

## 1. What this builds

`/analytics` becomes a real page: six trend cards and a per-agent table,
computed from the workspace's own conversations, messages and activity
events, filtered by date range and assignee.

Nothing new is recorded to make this work. Every number here is derived from
rows the product already writes — with one exception, §6, which is a bug fix
the accuracy of one metric depends on.

## 2. What already exists, and what it obliges

`apps/web/app/(console)/analytics/page.tsx` is an admin-gated shell reading
`apps/web/lib/mock/analytics.ts`. The mock is not neutral: it settles the
shape of the response and the vocabulary of the page.

`MetricSeries` (`apps/web/lib/types.ts:99`) fixes what a card is:

```ts
{ id, label, hint?, headline, delta: number | null, format: "count" | "duration", points: MetricPoint[] }
```

`headline` is a **preformatted string** ("412", "8m 24s") and `delta` is a
percentage against the previous period, `null` when there is nothing to
compare against. `format` drives axis rendering, not the headline. This slice
keeps that contract exactly; the API returns the same shape, so
`MetricCard` is untouched.

`AnalyticsFilters` (`apps/web/components/analytics/analytics-filters.tsx`)
settles the two filters and their options: ranges `7d | 30d | 90d | 12m`, and
an assignee select whose first option is "All assignees" and whose last is
"Unassigned". It holds both in `useState` and does nothing with either.

The mock's six cards are kept, with one substitution decided in chat:
`ai-resolved` ("Resolved without an agent") is replaced by `resolution-time`
("Avg time to resolve"). Nothing in the codebase writes `MessageRole.ai` —
that card would read `0` in perpetuity.

## 3. Decisions

**D1 — Computed live, not rolled up.**
One request runs the aggregate queries against `conversations`, `messages`
and `activity_events`. There is no `daily_metrics` table and no Celery task.

The alternative — a nightly rollup — is faster at twelve months and was
rejected as premature. It costs a table, a migration, a beat task and a
backfill command; it is stale until the job runs; and the assignee filter
forces either a per-agent × per-day row explosion or a second table. A
workspace here holds thousands of conversations, not millions. If this
becomes slow, a rollup slots in behind the endpoint defined in §5 without
the console noticing.

**D2 — Bucket count is bounded, so the range does not change the cost shape.**
`7d` and `30d` bucket by day, `90d` by week, `12m` by month. Every response
carries between 7 and 30 points. Without this, twelve months means 365
points the card renders as a smear and the database scans a year of events
to produce.

**D3 — The assignee filter selects by current assignee; the per-agent table
attributes by who acted.**
These answer different questions and the page shows both.

The filter restricts the conversation set to `assignee_id = :user` (or
`IS NULL`). That is the only reading under which the control's own last
option, "Unassigned", parses — and "tickets created by Sara" is meaningless,
so an author-based filter cannot cover all six cards.

The table is a team view, and a team view that credited work to whoever a
ticket happens to be assigned to *now* would be wrong: a ticket Sara
answered and handed to Nilesh is Sara's reply. Its columns therefore count
actions, via `messages.author_user_id` and `activity_events.actor_user_id`,
and are labelled as actions ("Replied to", "Resolved").

Because the two differ, the table is computed over the *unfiltered*
conversation set and the assignee select does not narrow it. Filtering a
per-agent breakdown to one agent leaves a table with one row.

**D4 — Buckets are UTC days.**
`Workspace` has no timezone column and `CurrentUser.timeZone` is a personal
display preference. Bucketing by a viewer's zone would make two admins in
different countries disagree about the same workspace's numbers. UTC is the
one answer that is the same for everyone; adding a workspace timezone later
changes this without changing the API's shape.

**D5 — Duration headlines are means over conversations, not means of daily
means.**
A day with one slow reply and a day with two hundred fast ones weigh
equally in a mean of daily means, which reports a number no conversation
experienced. The headline is the mean over every qualifying conversation in
the window. The daily points remain per-day means — that is what a trend
line is — so the headline is deliberately not the average of the plotted
points.

**D6 — Backlog is reconstructed backwards from a known-true anchor.**
Detail in §4.6. Today's backlog is counted directly from `conversations`,
and history is walked backwards from it. Replaying forwards from zero would
put the accumulated error at the right-hand edge, where the reader is
looking.

## 4. The metrics

`BACKLOG_STATUSES = {open, pending, on_hold}`. The rest — `resolved`,
`ignored`, `trash` — are terminal.

"Outbound reply" means `messages.direction = 'outbound' AND role IN
('agent', 'ai')`, excluding `system` so a bounce notice is never mistaken
for an answer.

### 4.1 `tickets-created` — count

Conversations whose `created_at` falls in the bucket.

### 4.2 `tickets-responded` — count

Conversations whose **first** outbound reply falls in the bucket. Attributed
to the bucket of the reply, not of the conversation, so the number reads as
"tickets we answered that day".

### 4.3 `tickets-resolved` — count

Distinct conversations with a transition into `resolved` in the bucket.
Distinct, so a ticket resolved, reopened and resolved again on one day
counts once that day.

### 4.4 `first-response` — duration

Mean of `first_outbound.sent_at - conversation.created_at`, over
conversations whose first outbound reply falls in the bucket. Conversations
with no reply yet are absent, not zero.

### 4.5 `resolution-time` — duration

Mean of `resolved_at - conversation.created_at`, over conversations resolved
in the bucket, where `resolved_at` is the transition used by §4.3. Measures
from the customer's first contact, so a reopened-then-resolved ticket
reports the whole elapsed ordeal rather than the last leg.

### 4.6 `backlog` — count

The number of conversations in `BACKLOG_STATUSES` at the **end** of each
bucket.

A conversation's status timeline is: `open` at `created_at`, then every
`activity_events` row with `kind = 'status'` ordered by `at`. Each event's
predecessor comes from `lag(status) OVER (PARTITION BY conversation_id ORDER
BY at)`, defaulting to `open`, which gives every event a `(from, to)` pair.

- An **entry** is `from ∉ BACKLOG AND to ∈ BACKLOG`, plus every creation.
- An **exit** is `from ∈ BACKLOG AND to ∉ BACKLOG`.
- Transitions within one set (`open → pending`, `resolved → trash`) are
  neither. Counting destinations alone would score `open → pending` as an
  entry and inflate the backlog on every triage.

Rows with `status IS NULL` are skipped. `services/ingest.py:316` writes a
`kind = 'status'` event for a mail delivery failure without one, and it is
not a status change.

Then, with `B(today)` counted directly from `conversations`:

```
B(bucket - 1) = B(bucket) - entries(bucket) + exits(bucket)
```

### 4.7 The per-agent table

One row per workspace member who **acted** in the window (D3), ordered by
`handled` descending. A member who did nothing in the window has no row; the
table is a record of activity, not a roster.

- **`handled`** — distinct conversations the member sent an outbound reply
  to, via `messages.author_user_id`. Not "assigned to": a ticket answered
  and handed on still counts for whoever answered it.
- **`firstResponseSeconds`** — mean of `sent_at - conversation.created_at`
  over the conversations where this member wrote the **first** outbound
  reply. `null` when there are none, which is the honest answer for someone
  who only ever picks up threads others opened.
- **`resolved`** — distinct conversations this member moved into `resolved`,
  via `activity_events.actor_user_id` on the transitions from §4.3.

There is no "Unassigned" row. Every column counts an action, and an action
has an actor; conversations nobody has touched are absent from the table by
construction. "Unassigned" exists in the filter (D3), where it means
something, and not here, where it would not.

## 5. API surface

Console, session-authenticated, admin-only — matching the page's existing
`requireAdmin`.

```
GET /api/analytics?range=7d|30d|90d|12m&assignee=<uuid>|unassigned
```

`range` defaults to `30d`. `assignee` omitted means all. An unparseable
`range` is a 422; an `assignee` that is not a member of the workspace is a
422, not an empty result, so a stale console cannot silently render zeros.

```json
{
  "series": [ { "id": "...", "label": "...", "hint": "...", "headline": "412",
                "delta": 12, "format": "count",
                "points": [ { "date": "2026-08-30", "value": 19 } ] } ],
  "agents": [ { "userId": "...", "name": "Sara Duval", "handled": 142,
                "firstResponseSeconds": 588, "resolved": 128 } ]
}
```

`agents` is §4.7: a row per member who acted in the window, `handled`
descending, no `Unassigned` row. `firstResponseSeconds` is `null` where the
member never opened a thread, and the console renders that as an em dash —
the API ships seconds and formats nothing.

`agents` ignores `assignee` (D3). Narrowing a per-agent breakdown to one
agent would leave a one-row table.

Camel case on the wire, per `CamelModel`.

## 6. Prerequisite: reopens are not recorded

`services/ingest.py:487` reopens a conversation on an inbound reply by
assigning `conversation.status` directly:

```python
elif conversation.status in REOPENING_STATUSES:
    conversation.status = ConversationStatus.open
```

No `ActivityEvent` is written. Two consequences, one of them pre-existing:

1. §4.6 cannot see the reopen, so every backlog point before it is **over**
   by one. Trace a ticket resolved at D2 (recorded) and reopened at D4
   (unrecorded), still open today: the walk starts from today's anchor,
   which counts it; nothing at D4 tells the walk to take it back out; and
   the recorded exit at D2 then *adds* it on the way past, so every bucket
   before the close carries it twice. ("Short by one" is what you get
   reasoning forwards from zero, which D6 rejects.) Reopening is not rare —
   it is what happens whenever a customer replies to a ticket an agent
   closed.
2. The conversation's own activity feed has never shown reopens either. A
   ticket silently changes state and the timeline does not say so.

The fix is to route this through the existing recorder, exactly as
`conversations._apply_status` does, with `ActivityKind.status` and
`status="open"`, attributed to the contact (the actor already used for the
`created` event on the branch above).

This is in scope for this slice. It is a two-line change to existing code
that one of the six metrics depends on, and it repairs an audit-trail gap on
the way.

## 7. Query strategy and indexes

Six aggregates and one per-agent query, each a single statement grouped by
bucket. Buckets are generated by `date_trunc` over a `generate_series`, left
joined, so a day with no activity is a zero rather than a hole the console
has to interpolate.

Two indexes, both covering the access pattern these queries introduce:

- `ix_activity_events_workspace_kind_at` on `(workspace_id, kind, at)` —
  §4.3, §4.5 and §4.6 all filter exactly this way.
- `ix_messages_workspace_direction_sent_at` on
  `(workspace_id, direction, sent_at)` — §4.2 and §4.4.

`conversations` needs nothing new: `ix_conversations_inbox` already leads
with `workspace_id`, and §4.1 and the §4.6 anchor are covered by it.

## 8. Multi-tenancy

Every query filters on `workspace_id` from `WorkspaceScope`, never from a
parameter. The `assignee` parameter is validated as an active member of the
scoped workspace before it reaches a query, so it cannot be used to probe
another tenant's user ids by timing or error shape.

## 9. Out of scope

- Any rollup, cache or materialized view (D1).
- CSV or scheduled-report export.
- Per-label, per-channel or per-priority breakdowns.
- A workspace timezone (D4).
- SLA targets, and any notion of a breach.
- Making `MessageRole.ai` real. The AI card is dropped, not deferred to a
  stub.

## 10. Testing

Service-level, against a real Postgres, in the style of `test_kb_*`:

- Each metric in §4 gets its own module-level test with a hand-built
  fixture, asserting the bucket a value lands in rather than only its total.
- Bucket granularity per range (D2), including that a 12m response carries
  12 monthly points.
- Duration headlines are means over conversations, not of daily means (D5) —
  a fixture with one slow day and one busy day, whose two answers differ.
- Backlog: an `open → pending` transition moves nothing (§4.6); a
  `resolved → open` reopen restores one; a delivery-failure event with a
  null status is ignored.
- The reopen fix (§6): an inbound reply to a resolved conversation writes a
  status activity event.
- The per-agent table (§4.7): a ticket answered by Sara and reassigned to
  Nilesh counts as Sara's `handled`, not Nilesh's; a member who only replied
  second has `firstResponseSeconds: null`; a member who did nothing in the
  window has no row; the table is unchanged by the `assignee` parameter.
- Empty workspace: every series is all-zero with `delta: null`, and no
  division by zero.
- Tenant isolation: another workspace's conversations never appear, per
  `test_tenant_isolation.py`.

Route-level: admin-only (an agent gets 403), a bad `range` is 422, an
assignee outside the workspace is 422.

Console: `vitest` over the range/assignee filters driving the URL, and
`MetricCard` rendering a `null` delta without a stray arrow.

## 11. Known risks carried

**Backlog history before the §6 fix stays wrong.** Reopens that already
happened left no trace and cannot be recovered. Because the walk is
anchored on today (D6), the error sits in the oldest buckets and shrinks
toward the right-hand edge — the 12-month view of a busy workspace will be
the least trustworthy thing on the page for its first year. The error runs
in one direction: each unrecorded reopen leaves every earlier bucket **over**
by one (§6), so old backlog numbers read worse than the workspace really
was, never better. Not worth a backfill: there is no source to backfill
from.

The same gap is why the walk is floored at zero. An unrecorded status
change can drive the running total negative — a conversation created
inside the window and closed with no `kind = 'status'` event subtracts a
creation the anchor has already excluded — and a backlog of `-4` is not an
approximation a reader can discount, it is a number that cannot exist.
Clamping keeps the series merely uncertain in the oldest buckets rather
than visibly impossible.

**`delta` against a zero previous period is `null`, not `+100%`.** A
workspace's first month shows no deltas at all. This is deliberate — a
percentage change from nothing is not a number — and the card already
handles `null`.
