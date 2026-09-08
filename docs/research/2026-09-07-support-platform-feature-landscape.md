# The support platform feature landscape

_Research note, 2026-09-07. What Zendesk, Freshdesk, Intercom and the
open-source desks actually ship, measured against what Relaydesk has today,
and what that implies about build order._

## 1. Where Relaydesk stands

Read from the code, not the README.

**Built.** Multi-tenant workspaces with `admin`/`agent` memberships, sessions,
Google OAuth, emailed invites, password reset. Conversations carry a
per-workspace `number`, subject, contact, channel, status
(`open`/`pending`/`resolved`/`on_hold`/`ignored`/`trash`), priority
(`urgent`…`low`), assignee, labels, unread flag and a per-conversation draft.
Messages carry role (`customer`/`agent`/`ai`/`system`), direction, RFC-822
threading (`external_id`, `in_reply_to`), delivery state with bounce capture,
and attachments. Email is a complete channel: IMAP poll on Celery beat, SMTP
delivery with retry, catch-all ingest addressing per workspace. Saved views
store JSONB filters. The knowledge base has internal/external scopes, a
draft→ready→published workflow, categories, per-workspace subdomain help sites
with full-text search, and image upload. The public portal accepts tickets with
a honeypot field and IP-keyed rate limiting.

**Scaffolded but empty.** `Conversation.summary` / `summary_state` and
`MessageRole.ai` exist with nothing writing them. `Channel.discord` and
`Channel.api` are enum values with no implementation. The analytics route is a
page shell with two unused components.

**Absent and load-bearing.** No internal notes — `MessageRole` has no `note`
member, so there is currently no way for an agent to say something on a ticket
that the customer does not receive. No organizations, only contacts. No
business-hours schedule, therefore no SLA. No trigger or automation engine, no
macros, no groups, no ticket search, no CSAT, no public API or webhooks.

## 2. The comparison set

| Product | Shape | What it is known for |
|---|---|---|
| Zendesk Suite | Ticket-first, enterprise | Triggers/automations/macros, SLA, Explore reporting, Guide help centre, multi-brand, side conversations, custom objects, apps marketplace |
| Freshdesk / Freshdesk Omni | Ticket-first, SMB→mid | Parent-child and linked tickets, agent collision detection, scenario automations, canned responses, Freddy AI |
| Intercom | Conversation-first | Fin autonomous AI agent, messenger, outbound, help centre |
| Plain / Pylon | B2B, Slack-native | Slack Connect / Teams / Discord as first-class channels, account health, SLAs over shared channels |
| Chatwoot | Conversation-first, OSS | Multichannel inbox, live chat |
| Zammad | Ticket-first, OSS, mature | Email/web/chat, strong search, granular permissions, text modules |
| FreeScout | Shared inbox, OSS, light | Help Scout clone, runs on LAMP, paid extension catalogue |

Relaydesk sits closest to Zammad structurally (ticket-first, email-first,
self-hostable) but is aiming at the Intercom/Pylon end on AI and at a developer
audience on channels.

## 3. Feature catalogue

Status key: **have** / **partial** / **gap**.

### 3.1 Channels

| Feature | Reference | Relaydesk |
|---|---|---|
| Email ingest + reply, threading, bounces | all | **have** |
| Multiple support addresses per workspace, per-brand sending domain w/ DKIM | Zendesk multi-brand | gap |
| Web chat / async messaging widget | Intercom, Freshdesk Omni | gap |
| Slack Connect shared channels | Pylon, Plain | gap |
| Discord | Pylon | **partial** (enum only) |
| WhatsApp / SMS | Zendesk, Freshdesk | gap |
| Voice, IVR, voicemail→ticket + transcription | Zendesk Talk | gap |
| Social DMs, app-store reviews | Zendesk, Freshdesk | gap |
| GitHub Issues / Linear as a channel | — | gap (differentiator) |
| Public ticket API + client SDKs | all | **partial** (enum only) |
| Business hours / schedules per channel | Zendesk, Freshdesk | gap |

Two channel notes worth carrying into design. WhatsApp imposes a 24-hour reply
window after the customer's last message, after which only pre-approved
template messages may be sent — that is a state machine on the conversation,
not an integration detail. And Zendesk keeps Support business hours and Chat
operating hours as separate, non-interacting schedules; that split is a known
source of user confusion and is worth *not* copying.

### 3.2 Ticketing core

| Feature | Reference | Relaydesk |
|---|---|---|
| Internal notes + @mentions | all | **gap — highest priority** |
| Groups / teams, assign to group | all | gap |
| Organizations (companies), org-shared tickets, org-level SLA | Zendesk, Freshdesk | gap |
| Custom ticket fields + multiple ticket forms | Zendesk, Freshdesk | gap |
| Custom statuses over the base state machine | Zendesk | gap |
| Merge, split, parent-child, linked tickets | Freshdesk | gap |
| Side conversations (email a vendor from inside a ticket) | Zendesk | gap (high value) |
| Agent collision detection / presence | Freshdesk | gap |
| CC / BCC / followers on a ticket | all | gap |
| Snooze with a wake time | all | **partial** (`on_hold`, no timestamp) |
| Full-text ticket search with operators | all | gap |
| Bulk actions, keyboard triage, command palette | all | gap |
| Saved views | all | **have** |
| Labels / tags | all | **have** |
| Activity history | all | **have** |
| Attachments | all | **have** |
| Contact merge, custom attributes, cross-ticket timeline, block list | all | gap |

### 3.3 Automation and routing

| Feature | Reference | Relaydesk |
|---|---|---|
| Trigger engine: event-driven condition→action on create/update | Zendesk triggers, Freshdesk rules | gap |
| Time-based automations (auto-close, nudge, escalate) | Zendesk automations (hourly) | gap |
| SLA policies: first reply, next reply, resolution; business-hours aware; breach views and events | Zendesk, Freshdesk, Pylon | gap |
| Macros / canned responses with placeholders | all | gap |
| One-click multi-action scenarios | Freshdesk scenario automations | gap |
| Round-robin, load-balanced, skills-based, omnichannel routing; agent capacity | Zendesk (skills-based on Professional) | gap |
| Auto-acknowledgement + out-of-hours reply | all | gap |
| Spam filter, blocked senders, suppression list | all | gap |
| Webhook as a trigger action | Zendesk | gap |

The trigger engine is the single highest-leverage item on this whole page.
Almost everything else in this section is a set of conditions and actions on top
of it, and so are auto-assignment, escalation, notification and most of what a
customer will call "workflow".

### 3.4 Self-service and knowledge

| Feature | Reference | Relaydesk |
|---|---|---|
| Article authoring, categories, draft→ready→published | Zendesk Guide | **have** |
| Internal vs external scope | — | **have** (differentiator) |
| Per-workspace public help site with search | Zendesk Guide | **have** |
| Revision history, scheduled publish, reviewer approval | Zendesk Guide | gap |
| Translations / locales | Zendesk Guide | gap |
| Multi-brand help centres | Zendesk (Suite Professional+) | gap |
| Restricted / signed-in-only articles | Zendesk | gap |
| Article feedback, view counts, search-term analytics | Zendesk | gap |
| Content-gap detection from unanswered tickets | Zendesk content cues | gap |
| SEO: sitemap, schema.org FAQ/HowTo, canonicals | Zendesk Guide | gap |
| Portal theming | Zendesk Guide themes | gap |
| Community forum / Q&A | Zendesk Guide | gap (skip) |
| Authenticated customer portal: my tickets, reply, org-shared | Zendesk, Freshdesk | gap |
| "Create article from this ticket" | Zendesk | gap (cheap, high value) |

### 3.5 AI

| Feature | Reference | Relaydesk |
|---|---|---|
| Conversation summary | Zendesk Copilot, Freddy | **partial** (columns exist, unwritten) |
| Suggested reply grounded in KB, with citations | Zendesk Copilot, Freddy Copilot | gap |
| Tone rewrite, expand, shorten, translate | Zendesk Copilot | gap |
| Macro suggestion | Zendesk Copilot | gap |
| Autonomous AI agent answering from KB | Fin, Freddy AI Agent, Answer Bot | gap |
| Agent conversations surfaced as normal tickets | Zendesk (GA 2026) | gap |
| Tool use: agent calls customer systems with approval gates | Fin, Pylon | gap |
| Auto-triage: intent, priority, language, sentiment, auto-label | Zendesk, Freddy | gap |
| AutoQA over 100% of conversations | Zendesk QA (ex-Klaus) | gap (differentiator) |
| BYO model key / self-hosted inference | — | gap (differentiator) |
| PII redaction before inference, retrieval citations, confidence-gated escalation | — | gap |

**On resolution rates, honestly.** Fin's own pages claim 71–76%. Intercom's
published case studies cluster at 42–50%; an independent 500-ticket
small-business test landed at 38%, and B2B deployments run 17–25 points below
vendor benchmarks because B2B tickets are harder. Relaydesk's customers are
likely B2B. The product decision that follows is to instrument deflection
honestly in the analytics layer and make the human handoff excellent, rather
than tuning for a headline number.

**The strongest AI card Relaydesk already holds** is the internal article
scope, described in the README as "procedures for the AI agent, describing how
to handle a kind of request step by step." That is a runbook an AI agent
executes, written and edited by support staff rather than engineers, reviewed
through the same draft→ready→published workflow, and auditable after the fact.
No competitor exposes agent behaviour that legibly. Everything else in the AI
column is a commodity within a year; this is not.

### 3.6 Reporting

| Feature | Reference | Relaydesk |
|---|---|---|
| Volume by channel / label / assignee / time | all | gap (route stub) |
| First reply time, next reply time, full resolution time | Zendesk Explore | gap |
| One-touch rate, reopen rate, backlog, busiest hours | Zendesk Explore | gap |
| SLA attainment and breach reporting | Zendesk | gap |
| CSAT survey + comments, CSAT by agent/label; NPS | all | gap |
| Custom metrics and report builder | Zendesk Explore | gap (expensive) |
| AI deflection, escalation rate, cost per resolution | Fin, Freddy | gap |
| Scheduled report email, CSV export | Zendesk | gap |
| Warehouse export / read-only SQL replica | — | gap (self-host advantage) |
| Live queue dashboard for leads | Zendesk | gap |

### 3.7 Admin, trust and scale

| Feature | Reference | Relaydesk |
|---|---|---|
| SSO (SAML/OIDC), SCIM provisioning, enforced 2FA | Zendesk/Freshdesk Enterprise | gap |
| Custom roles beyond admin/agent; light agents / collaborators | Zendesk | gap |
| Admin audit log, exportable | Zendesk Enterprise | gap |
| Data retention policy, GDPR export/erase by contact | all | gap |
| Message and attachment redaction | Zendesk | gap |
| HIPAA posture / BAA, encryption at rest | Zendesk Enterprise | gap |
| API tokens with scopes, IP allowlist | all | gap |
| Multi-brand | Zendesk | gap |
| Sandbox workspace | Zendesk Enterprise | gap |
| Config as code: triggers, macros, fields exported to git | third-party only (Salto) | gap (differentiator) |
| Per-tenant data residency | Zendesk | gap |

### 3.8 Platform and extensibility

| Feature | Reference | Relaydesk |
|---|---|---|
| Public REST API + OpenAPI + SDKs | Zendesk | gap (FastAPI makes this cheap) |
| Signed webhooks with retry and replay | Zendesk | gap |
| Sidebar app framework in the agent view | Zendesk apps, Freshworks | gap |
| MCP server exposing the desk to AI clients | — | gap (cheap, on-brand) |
| Linear / Jira / GitHub issue link and status sync | all | gap |
| Stripe, Shopify, Segment, Slack, CRM sync | all | gap |
| Import from Zendesk / Freshdesk / Intercom / Help Scout / Front / mbox | Help Desk Migration (76 platforms) | gap (README says planned) |
| CLI, Terraform provider | — | gap |

Import is the switching cost. The known hazards from the migration vendors are
worth designing for up front: two sets of API rate limits to respect, every
attachment must be re-hosted rather than hot-linked, and **outbound
notifications must be suppressed during import** or the migration mails
thousands of customers.

### 3.9 Commercial layer

Billing, metering, plan gating, trials, invoices — none of which belongs in the
AGPL self-hosted path. Worth noting the industry has moved to outcome pricing
for AI: Fin bills $0.99 per resolution ($49/mo for the first 50); Freshworks
bills $29/agent/month for Freddy Copilot and $49 per 100 AI-agent sessions.
Seats plus AI outcomes on cloud, everything free when self-hosted, is the
consistent shape.

## 4. Suggested build order

These are ordered because each phase unblocks the next, not for tidiness.

**Phase 1 — make it a desk someone can work in all day.** Internal notes and
@mentions first; the absence of a note is the one gap that makes the inbox
unusable as a team tool. Then business-hours schedules, because SLA and
auto-responders both depend on them. Then the trigger engine and macros, then
SLA policies on top. Then groups and basic assignment, ticket search, snooze
with a wake time, merge/link, collision detection, organizations, and CSAT.

**Phase 2 — the channels this audience actually uses.** Discord (the enum is
already there and the audience is open-source communities), Slack Connect, then
the public API with signed webhooks, then a web widget.

**Phase 3 — AI, in compounding order.** Summary (columns exist) → auto-triage
and labelling → copilot suggested replies grounded in KB with visible citations
→ the autonomous agent executing internal procedure articles with tool calls
and approval gates → AutoQA and honest deflection reporting.

**Phase 4 — trust.** SSO/SCIM, custom roles, admin audit log, retention and
GDPR erase, redaction, config-as-code.

**Phase 5 — commercial.** Import from the big three, billing and metering,
multi-brand.

## 5. What to skip

Voice and IVR — enormous surface, telco vendor dependency, wrong audience.
Community forums — Discord already serves this audience. A visual workflow
builder before a rules engine exists. A full Explore-style report designer;
ship fixed dashboards plus a SQL replica instead. Social DMs and app-store
reviews. Workforce management and scheduling. An app marketplace before there
is a stable public API.

## 6. The six things that would make Relaydesk not-a-Zendesk-clone

1. **Internal procedure articles as the AI agent's auditable runbook** —
   already modelled, nobody else exposes agent behaviour this legibly.
2. **Config as code.** Triggers, macros, fields and views exported to git and
   applied per environment. Zendesk admins pay third parties for this.
3. **Honest AI measurement.** AutoQA across 100% of conversations and a
   deflection number the customer can audit, against a market whose published
   rates are roughly double what independent tests find.
4. **Bring-your-own model, including self-hosted inference.** The only credible
   answer for teams who cannot send support transcripts to a vendor — and the
   natural pairing with an AGPL, self-hostable desk.
5. **Developer-shaped channels** — Discord, Slack Connect, GitHub Issues —
   instead of voice and social.
6. **A first-class import path.** AGPL plus a real migration tool makes the
   switching cost low in both directions, which is the honest version of the
   open-source pitch.

## Sources

Zendesk: [routing and automation options](https://support.zendesk.com/hc/en-us/articles/4408831658650-Routing-and-automation-options-for-incoming-tickets),
[Agent Workspace](https://support.zendesk.com/hc/en-us/articles/4408821259930-About-the-Zendesk-Agent-Workspace),
[what's new, September 2026](https://support.zendesk.com/hc/en-us/articles/11180657600026-What-s-new-in-Zendesk-September-2026),
[AI agent conversations as tickets](https://support.zendesk.com/hc/en-us/articles/9727051305498-Announcing-the-general-availability-of-AI-agent-conversations-as-tickets-in-Support-and-Agent-Workspace),
[Explore](https://support.zendesk.com/hc/en-us/articles/4408831710618-Getting-started-with-Zendesk-Explore-for-reporting-and-analytics),
[messaging business hours](https://support.zendesk.com/hc/en-us/articles/4500737327258-Configuring-messaging-responses-and-business-hours),
[WhatsApp 24-hour rule](https://support.zendesk.com/hc/en-us/articles/4408829291162-Working-with-WhatsApp-tickets-and-the-24-hour-rule),
[developer platform](https://developer.zendesk.com/documentation/api-basics/getting-started/about-the-zendesk-developer-platform/),
[Klaus acquisition](https://www.zendesk.com/blog/quality-assurance/wem/zendesk-acquisition-klaus/).
Freshdesk: [ticketing system guide](https://www.eesel.ai/blog/freshdesk-ticketing-system),
[parent-child workflows](https://support.freshdesk.com/support/solutions/articles/50000001089-automate-parent-child-ticketing-workflows),
[Omni pricing](https://www.eesel.ai/blog/freshdesk-omni-pricing).
Intercom: [Fin guide](https://www.getmacha.com/blog/intercom-fin-ai-agent-complete-guide),
[independent 500-ticket review](https://builts.ai/blog/intercom-fin-ai-review/),
[resolution-rate comparison](https://superframeworks.com/articles/best-ai-customer-support-tools).
B2B/Slack-native: [Pylon review](https://www.aicxstack.com/blog/pylon-review),
[Plain on Slack-native support](https://www.plain.com/blog/best-slack-native-support-tools-2026).
Open source: [Zammad vs FreeScout](https://openalternative.co/compare/freescout/vs/zammad),
[open-source helpdesk roundup](https://herothemes.com/blog/open-source-helpdesk-ticketing-systems/).
Migration: [Help Desk Migration](https://help-desk-migration.com/zendesk/),
[Zendesk→Intercom technical guide](https://clonepartner.com/blog/zendesk-to-intercom-migration-the-2026-technical-guide).
