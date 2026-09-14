# Who Relaydesk should sell to first

**Date:** 2026-09-13
**Audience:** Relaydesk founding team
**Scope:** ICP definition, ~30 named accounts, who to contact inside each, and the outreach angle per segment.
**Motions in scope (as requested):** paid self-host + support, managed-cloud waitlist, OSS adoption first.
**Geography:** no hard filter, India-weighted first.

**Method note.** Firmographic and regulatory claims carry a source URL. Technographic claims
("runs Freshdesk") were verified by fetching the prospect's *own* public support page on
2026-09-13 — no platform scraping, no logged-in sources. Where I could not verify, the row
says so. **No contact names or email addresses are invented anywhere in this document**; each
segment instead gets a repeatable route to the right person.

---

## 1. The constraint that decides the ICP

Read from the code, not the pitch. This is what a buyer can actually run today:

| Working | Not there yet |
|---|---|
| Email as a complete channel (IMAP ingest, SMTP reply, threading, bounces, attachments) | **Internal notes** — `MessageRole` is `customer/agent/ai/system`, there is no `note` member |
| Widget with AI answers grounded in published KB articles, with escalation to a ticket | Slack / Teams / Discord (`Channel.discord` is an enum value with no implementation) |
| Per-workspace help portal on its own subdomain, with search | SLA, business hours, macros, triggers/automations, CSAT |
| Public ticket form with honeypot + IP rate limiting | Reporting/analytics beyond the page shell |
| Scoped-key public API at `/v1`, webhooks | One-click import from Zendesk/Freshdesk/Intercom |
| **BYO model key, BYO `base_url`, per-workspace daily token budget** (`ai_config.py`) | Multi-brand sending, WhatsApp, voice |

Two of these lines do more to set the ICP than everything else combined.

**No internal notes caps the buyer at roughly three agents.** A team of ten cannot work a
queue where the only way to say something to a colleague is to say it to the customer. Until
a `note` role ships, every account below is qualified on *small support team*, not on company
size. A 25-agent Zendesk shop is not a hard sell — it is a **Skip**.

**BYO key + BYO base_url + a hard token budget is the strongest thing you own.** The whole
market has moved to per-outcome billing and buyers hate it: Intercom Fin is **$0.99 per
outcome** ([fin.ai/pricing](https://fin.ai/pricing/)), Zendesk bills roughly **$1.50–$2.00 per
automated resolution** ([eesel breakdown](https://www.eesel.ai/blog/zendesk-plans-and-pricing)),
Chatwoot meters Captain AI in credits at **$20 per additional 1,000**
([chatwoot.com/pricing](https://www.chatwoot.com/pricing)). Relaydesk's answer is not "cheaper
per resolution" — it is **"there is no per-resolution line at all; you pay your own model bill
at cost, you cap it in the console, and you can point it at inference you host."** That
sentence is the wedge. Lead with it everywhere.

### The channel mismatch to respect

I checked 25 candidate companies' public sites for a support-desk widget. The result is worth
internalising: **open-source developer-tool companies overwhelmingly run no helpdesk at all.**
Appsmith, Plane, NocoDB, n8n, Windmill, Twenty, Keploy, Elestio all route support to **Discord**;
SigNoz runs Inkeep on docs; Hoppscotch, Hasura, Typesense, Documenso, Dub, Formbricks, Appwrite,
Coolify, PikaPods and Cloudron showed no desk vendor on their front door.

They are culturally the easiest audience to reach and the hardest to charge, and the channel
they live in is the one channel Relaydesk has not built. Treat OSS dev tools as an **adoption
and contribution** audience, not as the paid-self-host pipeline. Sell revenue to teams whose
customers *email them*.

---

## 2. The competitive fact that reshapes the India plan

**Libredesk is a Zerodha project.** It is listed on
[zerodha.tech/projects](https://zerodha.tech/projects/) as "Self-hosted customer support desk in
a single binary," and it markets itself as a lightweight alternative to Intercom, Zendesk and
Chatwoot — AGPL-3.0, every feature free, no paid tier, ~2.9k stars
([github.com/abhinavxd/libredesk](https://github.com/abhinavxd/libredesk)).

Consequences, plainly:

1. **Zerodha is not a prospect.** Do not spend a cycle there. It is the single most obvious
   Indian FOSS-first support-desk buyer and it already built its own.
2. **"Free and self-hostable" is not a differentiator in India.** Libredesk is free *and* ships
   SLA, macros, CSAT, RBAC and an agent copilot — all things Relaydesk does not have yet. Against
   it, Relaydesk wins on **BYO/self-hosted inference with a spend cap**, **API-first with scoped
   keys**, **per-workspace multi-tenancy** (Libredesk is single-tenant per install), and the
   managed cloud they do not offer. Say those four things, not "open source".
3. **Multi-tenancy is a real, under-used asset.** Libredesk, Zammad and FreeScout are
   one-org-per-install. Relaydesk's workspace model means one deployment serves many customers —
   which is exactly what an agency, an MSP, or a hosting provider needs. See Segment C.

---

## 3. The ICP

> A **1–3 agent support team** at a company whose customers reach them **by email or a website
> widget** (not Discord), that already maintains **public documentation** the AI can ground on,
> and that has a **named reason to keep support transcripts on infrastructure it controls** —
> Indian DPDP/RBI exposure, EU data residency, or a stated anti-US-cloud position — **or** a
> per-resolution AI bill it has already been shocked by. Technical enough to run Docker Compose,
> or buying from you because it does not want to.

### Pass / fail checklist

| # | Criterion | Pass |
|---|---|---|
| 1 | Support headcount | 1–3 agents working the queue |
| 2 | Dominant inbound channel | Email, web form, or on-site widget |
| 3 | Public KB / docs exists | ≥ 20 articles the AI can answer from |
| 4 | Data-control driver | DPDP (India), RBI localisation, GDPR/residency, or explicit sovereignty stance |
| 5 | Cost driver (alternative to 4) | Currently paying per-resolution AI, or on a seat plan they resent |
| 6 | Technical capability | Runs its own infra, **or** is buying managed cloud precisely because it will not |
| 7 | Reachable champion | Founder/CTO/Head of Support identifiable from public sources |

Four of seven, with at least one of (4) or (5), qualifies.

### Disqualifiers — Skip on sight

- **> 5 agents on the queue** (no internal notes; they will churn in week two)
- **Support lives in Discord or Slack Connect** (no channel; Pylon and Plain own this)
- **Contractual SLA commitments to their own customers** (no business hours, no SLA engine)
- **Needs a migration from Zendesk/Freshdesk on day one** (no importer)
- **Voice or WhatsApp is a primary channel**
- **Already runs Libredesk happily** — no story yet, revisit after SLA/macros
- **Any regulated buyer who needs a signed DPA + SOC 2 before a pilot** — you have neither

---

## 4. The three segments, ranked

| Rank | Segment | Motion | Why first | Realistic ACV |
|---|---|---|---|---|
| **1** | Privacy/sovereignty-first email businesses (EU-heavy) | Paid self-host + support | Support *is* email; they are constitutionally unable to buy Zendesk; tiny teams; BYO-inference is a requirement, not a feature | €3–15k/yr support contract |
| **2** | Indian regulated small teams — fintech infra, health, brokerages | Cloud waitlist → paid self-host | DPDP hard deadline **13 May 2027**; RBI already forbids offshore payment data; support tickets are full of PII | ₹3–12L/yr |
| **3** | Agencies, MSPs, Frappe/ERPNext partners, hosting platforms | Paid self-host + reseller | One deployment, many workspaces — the multi-tenant model nobody else in OSS has | ₹2–8L/yr, or per-seat resale |
| — | OSS dev tools | **OSS adoption only** | Stars, issues, contributors, credibility. Do not forecast revenue here | ₹0 |
| — | DPI / govtech | Strategic, 12–18 months | Real fit, glacial procurement. Plant now, harvest later | — |

**Why India is second, not first,** despite the geographic preference: the regulatory clock is
real but the hard deadline is **May 2027**, and the buyers who feel it most are also the ones who
will ask for a DPA, SOC 2 and an SLA you cannot sign yet. Sovereignty-driven EU buyers ask the
same questions but accept "self-hosted, you hold the data, here is the AGPL source" as the answer.
Start the India conversations now on the **cloud waitlist** motion so the pipeline is warm when
notes and SLA ship; close revenue first where the deployment itself is the compliance answer.

---

## 5. Named accounts

Confidence: **High** = two independent sources or the company's own page; **Medium** = one credible
source plus consistent evidence; **Low** = directional, verify before outreach. `Desk today` was
probed on 2026-09-13 against the company's own public support/help URL.

### Segment 1 — Sovereignty / privacy-first, email-shaped support

| Score | Company | Country | Why a prospect | Desk today | Confidence |
|---|---|---|---|---|---|
| **Hot** | **Migadu** | CH | Your own deployment doc already recommends them for inbound catch-all ([docs/deployment/email-channel.md](../deployment/email-channel.md)) — you are their customer, which is a warm door. Mail host, support is 100% email, tiny team, explicitly anti-bigtech | Not detected | Medium |
| **Hot** | **Heinlein Support / mailbox.org** | DE | Sells privacy mail to German SMB and public sector; "Support" is in the company name; cannot put customer mail through a US desk | Not detected | Medium |
| **Hot** | **Tuta (Tutao GmbH)** | DE | Encrypted mail, ~100 staff, support is email + KB, publicly refuses US cloud services. BYO/self-hosted inference is the only AI story they can accept | Not detected | Medium |
| **Hot** | **Nextcloud GmbH** | DE | Sells self-hosted software to public sector; their own support portal being self-hosted is a sales asset. Ideologically identical buyer | Not detected | Medium |
| **Warm** | **Posteo** | DE | Ideologically perfect, email-only support, but deliberately tiny and may have no budget line at all | Not detected | Low |
| **Warm** | **OpenProject GmbH** | DE | openDesk component vendor, public-sector customers, self-host-first ([openproject.org](https://www.openproject.org/blog/sovereign-workplace/)) | Not detected | Medium |
| **Warm** | **Element (Matrix)** | UK | Sovereignty buyers, self-hosted deployments, email support to enterprise customers | Not detected | Low |
| **Warm** | **Penpot / Kaleidos** | ES | Growing OSS design tool with a real non-developer user base — their users email, they do not open GitHub issues | Not detected | Low |
| **Cold** | **Codeberg e.V.** | DE | Perfect values fit, nonprofit, essentially no budget. Adoption story, not revenue | Not detected | Medium |
| **Cold (strategic)** | **ZenDiS / openDesk** | DE | Germany's sovereign workplace suite has **eight modules and no helpdesk** ([opendesk.eu](https://www.opendesk.eu/en/about)); customers include the Bundeswehr and Robert Koch Institute. A 12–18 month play, but the gap is real and AGPL is not a blocker for them | n/a | Medium |

### Segment 2 — Indian regulated small teams

The "why now" is concrete: the DPDP Rules were notified **13 Nov 2025**, soft enforcement ends
around **Nov 2026**, and full compliance is due **13 May 2027**
([india-briefing](https://www.india-briefing.com/news/india-dpdp-compliance-timeline-enforcement-2026-27-44740.html/)).
Separately, RBI already requires the *entire* payment data set to be stored on systems located
only in India, with offshore copies deleted within 24 hours
([Business Standard](https://www.business-standard.com/article/economy-policy/payments-data-must-be-stored-in-systems-located-in-india-says-rbi-119062700043_1.html)).
Support tickets routinely contain names, PAN, account and transaction details — that is payment
data sitting in a US SaaS desk.

| Score | Company | Why a prospect | Desk today | Confidence |
|---|---|---|---|---|
| **Hot** | **Setu** | Fintech infrastructure (AA, UPI, BBPS), RBI-adjacent, small support org | **Freshdesk** — `support.setu.co/support/home` | **High** (verified) |
| **Hot** | **Juspay** | Payments infra under RBI localisation *and* genuinely OSS-native (Hyperswitch). Will read the AGPL source and the `ai_provider.py` docstring and understand exactly what you built | Not detected | Medium |
| **Hot** | **Eka.care** | ABDM-linked health records — PHI in tickets is the sharpest possible data-control argument | Not detected | Medium |
| **Hot** | **E2E Networks** | Indian sovereign cloud, listed company, whose entire pitch is "your data stays in India". Dogfood buyer *and* a natural reseller of a managed Relaydesk on Indian infrastructure | Not detected | Medium |
| **Warm** | **Decentro** | Banking-API startup, small team, RBI-regulated customers | Not detected | Medium |
| **Warm** | **M2P Fintech** | BaaS at scale; publishes on RBI localisation ([m2pfintech.com](https://m2pfintech.com/blog/decrypting-rbi-data-localization-policy-for-payment-companies/)) — they have already written your pitch | Not detected | Medium |
| **Warm** | **Exotel** | CPaaS; telecom + DPDP exposure; runs a desk today | **Freshdesk** — `support.exotel.com` | **High** (verified) |
| **Warm** | **Dhan** | Tech-forward discount broker, SEBI-regulated, small support team relative to peers | No support subdomain | Low |
| **Warm** | **Signzy / Perfios** | KYC and financial-data processing — DPDP "significant data fiduciary" candidates | Not detected | Low |
| **Warm** | **Onsurity / Plum** | Insurtech holding employee health data; small CX teams | Not checked | Low |
| **Warm** | **Sarvam AI** | India-sovereign AI; a support desk that can point at *their own* inference endpoint is a story they will enjoy telling | Not detected | Low |
| **Cold** | **KreditBee / Fibe** | NBFC, strong data pressure, but support teams are far too large for a desk with no internal notes | Not checked | Low |
| **Skip** | **Upstox** | Verified Freshdesk (`upstox.com/help-center/`) but a support org of hundreds. Note it for 2027, not now | **Freshdesk** | **High** (verified) |
| **Skip** | **Zerodha** | Builds and maintains Libredesk | Libredesk | **High** |

### Segment 3 — Agencies, MSPs, hosting platforms (the multi-tenant play)

This is the segment your architecture fits best and the one nobody is pitching. One Relaydesk
deployment, one workspace per client, scoped API keys per workspace, a help portal per subdomain.
Libredesk, Zammad and FreeScout all require one install per customer.

| Score | Target | Why | How to reach | Confidence |
|---|---|---|---|---|
| **Hot** | **Frappe/ERPNext implementation partners (India)** | Hundreds of small firms already self-hosting Frappe for many clients, each needing a support queue per client. They have Docker skills and no US-SaaS budget. Partner directory is public at [frappe.io](https://frappe.io/) | Partner directory → founder/MD directly | Medium |
| **Hot** | **Cloudron** | 200+ app catalog, paying self-hosters, app requests are community-driven ([cloudron.io](https://www.cloudron.io/)) | Cloudron forum app-request thread | **High** |
| **Hot** | **PikaPods** | ~200 managed OSS apps at $2–4/mo; explicitly the "self-host without a VPS" audience; actively solicits new apps ([dev.to/pikapods](https://dev.to/pikapods/kickstart-2026-deploy-your-first-open-source-app-on-pikapods-38cm)) | App suggestion form / their public channels | **High** |
| **Warm** | **Elestio** | 400+ app catalog, fully managed on the customer's chosen cloud — a ready-made "managed Relaydesk" that costs you nothing to operate | App request via their support/Discord | **High** |
| **Warm** | **Coolify** | Large self-host community; a one-click template puts Relaydesk in front of exactly the right people | Template PR to their repo | **High** |
| **Warm** | **Indian WordPress / Shopify agencies** | Run support for 10–50 client brands each; currently juggling shared Gmail inboxes | Founder via LinkedIn / agency directories | Low |
| **Warm** | **Small Indian MSPs and hosting resellers** | Ticketing is their product; per-seat desk pricing destroys their margin | Direct founder outreach | Low |

**Distribution note:** getting listed in Cloudron, PikaPods, Elestio, Coolify and
`awesome-selfhosted` is cheap, permanent, and puts Relaydesk in front of the self-host audience
without any outbound. Do this before, not after, the outreach campaign.

### Segment 4 — OSS dev tools (adoption motion only; zero revenue forecast)

All verified on 2026-09-13 as running **no helpdesk**, with community in Discord: **Appsmith**,
**Plane**, **NocoDB**, **Keploy**, **n8n**, **Windmill**, **Twenty**, **Budibase**. **SigNoz** runs
Inkeep on docs. **Hoppscotch**, **Hasura**, **Typesense**, **Frappe**, **Documenso**, **Dub**,
**Formbricks**, **Appwrite** showed nothing.

What to do with them: ask for a **star, a read, and an issue**, not a purchase. They are your
credibility layer and your contributor pool, and the Indian ones (SigNoz, Plane, Appsmith,
Hoppscotch, Keploy, NocoDB, Frappe) are reachable in the same city and at the same meetups.
One caveat — **Frappe ships Frappe Helpdesk**, so treat them as an ecosystem partner via their
partner network, never as a desk prospect.

### Segment 5 — DPI / govtech (plant now)

**MOSIP**, **eGov Foundation**, **Samagra**, **Bhashini**, **ONDC** network participants. AGPL is an
asset rather than an obstacle here, self-hosting is mandatory, and citizen-facing support desks
are a genuine unmet need. Budget cycles are 12–18 months and procurement will ask for things you
do not have. Contribute, get known, do not forecast.

---

## 6. Who to contact, by segment

The generic answer for a helpdesk purchase — 5–8 stakeholders, procurement involved in ~53% of
cycles ([growthspree](https://www.growthspreeofficial.com/blogs/b2b-saas-buying-committee-size-benchmarks-2026-stakeholders-by-acv-vertical-region-role-composition))
— **does not apply to you yet**, because at a 1–3 agent team the champion, the technical approver
and the budget holder are usually two people or one. Aim small and senior.

| Segment | First contact (champion) | Technical approver | Unblocker | Do **not** start with |
|---|---|---|---|---|
| Sovereignty / privacy | **Founder or CTO** — these are 10–100 person companies where the founder still has an opinion about the support stack | Same person, or Head of Infrastructure | — | Marketing, partnerships |
| India regulated | **Head of Customer Experience / Support Operations** (feels the pain) — or **DPO / Head of Compliance** (owns the deadline) | VP Engineering / Head of Platform | **CISO or DPO** — under DPDP they are the one who can say "this must come in-house" | CEO cold. Procurement — they will demand SOC 2 |
| Agencies / MSPs | **Founder or Managing Director** — one-person buying committee | — | — | Account managers |
| Hosting platforms | **Founder**, or whoever maintains the app catalog | — | — | Sales; there is no sales motion, use the public app-request channel |
| OSS dev tools | **Head of DevRel / Community**, or the top committer on the docs repo | — | — | Anyone, for money |
| DPI / govtech | **Programme or product lead** on the specific initiative | Solution architect | — | Procurement, tenders |

### How to find the actual human (no guessing, no invented addresses)

1. **GitHub first** for anything OSS-adjacent — the org's top committers on the docs or support
   repo, and the address in their commits if they publish one. Highest-signal route you have.
2. **`/security.txt`, `/.well-known/security.txt`, `/imprint`, `/impressum`** — EU companies are
   legally required to publish a named contact in the Impressum. For the German accounts in
   Segment 1 this hands you a real name and address, lawfully.
3. **The company's own published role addresses** — `support@`, `hello@`, `info@`. For a 1–3 agent
   team, `support@` *is* the Head of Support's inbox. This is both the most compliant route and
   often the most effective one.
4. **LinkedIn title search** (manual, no scraping) for "Head of Customer Experience", "Support
   Operations", "Data Protection Officer" at the Indian accounts.
5. **Their own help centre** — the reply address on a ticket you file yourself tells you the tool,
   the team size and the tone. Filing one real support request is legitimate research.

Retain the **source URL and the date** for every contact you add to a list — required for DPDP,
GDPR and CAN-SPAM lineage.

---

## 7. Outreach angles that fit what exists

One angle per segment. Each leads with the thing that is true today, and none of them promise
notes, SLA or migration.

**A. Sovereignty / privacy (highest conversion)**
> Subject: *AI answers without sending your customers' mail to a US model vendor*
>
> Every AI helpdesk on the market answers your tickets by posting them to a model API someone else
> chose. Relaydesk lets you point it at inference you host — `base_url` in the workspace config —
> and caps the daily token spend in the console. AGPL, self-hosted, your Postgres. We are early and
> we know exactly what is missing; here is the list before you ask.

Leading with the missing-features list is not modesty, it is the fastest qualifier you have. This
audience rewards it.

**B. India regulated (cloud waitlist now, revenue later)**
> Subject: *Your support tickets contain PAN and account numbers. Where are they stored?*
>
> RBI already requires payment data to live only on systems in India. DPDP's full compliance date
> is 13 May 2027. A Freshdesk or Zendesk instance holding transaction-level tickets is the part of
> the stack nobody has audited yet. Relaydesk runs inside your VPC, on your Postgres, with the
> model key you choose — or none at all.

Open with the DPO/compliance lead, not the support lead. They have a dated obligation; the support
lead has a preference.

**C. Agencies, MSPs, Frappe partners**
> Subject: *One helpdesk install, one workspace per client*
>
> Libredesk and Zammad want one install per customer. Relaydesk is multi-tenant by design —
> workspaces, scoped API keys per workspace, a branded help portal per subdomain, one deployment
> you operate. Per-seat desk pricing across 30 client brands is what is eating your margin.

**D. Hosting platforms (Cloudron, PikaPods, Elestio, Coolify)**
Not an email — a well-written app request in their public channel, with a working Compose file, a
screenshot and honest scope. These communities reward a maintainer who shows up with the packaging
already done.

**E. OSS dev tools**
Not an email either. Ship something they use, comment usefully in their repos, and let the AGPL
source do the talking. Ask for a read of `ai_provider.py` — the docstring explaining *why* the
provider is a protocol is the single most persuasive artefact in the repository for this audience.

---

## 8. Qualify before you send

A prospect's current desk is the strongest single qualifier — it tells you whether they have the
pain and the budget. The probe script written for this research is at
`/private/tmp/claude-501/-Users-abcom-Desktop-openfoundry-Relaydesk/75f32b61-e376-423c-a0c4-fe2e7f8d6b03/scratchpad/help.sh`
(move it into `scripts/` if you want to keep it). It fetches only the prospect's own
`support.` / `help.` subdomain — no platform scraping — and reports the vendor.

Before any account moves to Hot, confirm all four:

- [ ] Support team is 1–3 people (careers page, LinkedIn headcount, or the reply on a ticket you filed)
- [ ] Inbound is email or web, not Discord or Slack Connect
- [ ] A public KB with enough articles for grounded answers to work on day one
- [ ] A named data-control or cost driver — not an assumed one

---

## 9. What I could not verify

- **Support-team size for every named account.** This is the load-bearing qualifier and none of it
  is public. Verify per account before outreach.
- **Widget detection is homepage-level.** A desk behind an app login would not show up, so
  "not detected" means "no desk on the public front door", not "no desk".
- **Indian D2C and insurtech** were probed only shallowly; several had no `support.`/`help.`
  subdomain, which usually means an in-app desk rather than none.
- **Whether Segment 1's EU accounts are already on Zammad or OTRS.** Several likely are. That
  changes the pitch from "get off US SaaS" to "your desk has no AI story and cannot get one
  without sending transcripts to OpenAI" — a better pitch, but confirm first.
- **Budget reality for Posteo, Codeberg and similar.** Values-aligned and possibly unable to pay
  anything at all.
