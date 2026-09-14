# Outbound sequences

**Date:** 2026-09-13
**Companion to:** [2026-09-13-initial-customers-and-icp.md](../research/2026-09-13-initial-customers-and-icp.md)
**Covers:** Segment 1 (sovereignty/privacy, EU-heavy) and Segment 2 (India regulated), plus
first-touch notes for Segment 3 (agencies/MSPs) and the hosting platforms.

---

## The rule that governs every email here

**There is no proof yet, so honesty is the proof.** No customer count, no logos, no "trusted by",
no invented results — one unverifiable claim and this audience is gone permanently, and they talk
to each other. What you have instead is unusually persuasive to these two segments specifically:
public AGPL source, design documents that explain *why* each decision was made, and a candid list
of what is missing. Every sequence below leads with a limitation somewhere in the first three
emails. That is deliberate — it is the fastest qualifier you own, and it is the only credibility
signal available to a pre-1.0 product.

**Claims you may make** (all verifiable in the repo today):
- AGPL-3.0, self-hosted, your Postgres
- The model endpoint is a per-workspace config field — point it at inference you host and no
  transcript leaves your network (`ai_config.py`, `base_url`)
- A per-workspace **daily token budget**, set in the console
- No per-resolution billing of any kind
- Email in and out with RFC-822 threading, retry and bounce capture
- Help centre on the workspace's own subdomain, with search
- Widget that answers from published articles and escalates with the transcript attached
- Scoped-key public API at `/v1`, webhooks
- Multi-tenant: one deployment, many workspaces

**Claims you may not make yet:** anything about uptime, scale, customers, benchmarks, resolution
rates, SOC 2, or a DPA.

---

## Segment 1 — Sovereignty / privacy-first email businesses

**To:** founder or CTO (these are 10–100 person companies; the founder still has an opinion about
the support stack).
**Goal:** a reply, then a production install with hands-on support from you.
**Cadence:** Day 0 / +4 / +10 / +18. Plain text, one link maximum, no tracking pixel — this
audience blocks them and notices that you tried.

### Email 1 — Day 0

> **Subject:** self-hosted inference
>
> Every AI help desk on the market answers a ticket by posting it to a model vendor somebody else
> picked. For most companies that's a procurement question. For you it's a non-starter.
>
> I'm building Relaydesk — an AGPL support desk, email-first, runs on your own Postgres. The AI
> answers from your published help articles, and the model endpoint is a field in the workspace
> config: point it at inference you host and the transcript never leaves your network. There's a
> daily token ceiling in the console so it can't run away from you either.
>
> It's early, and the gaps are real — no internal notes, no SLA, no importer. That rules out a big
> support team. It doesn't obviously rule out yours.
>
> Worth a look at the source?

### Email 2 — Day 4 (angle: the economics)

> **Subject:** per-resolution pricing
>
> Intercom bills $0.99 an outcome. Zendesk is roughly $1.50–$2.00 a resolution. Chatwoot meters AI
> in credits at $20 per additional thousand.
>
> All three make your support cost a function of how many customers you have and how incomplete
> your docs are — and none of them let you audit the invoice against what was actually resolved.
>
> Relaydesk has no per-resolution line at all. You bring your own model key, you watch the token
> spend, you set the daily ceiling. If you host the model yourself, the marginal cost of an
> answered ticket is your own electricity.
>
> Source is AGPL if you want to read the retrieval path before you believe any of that.

### Email 3 — Day 10 (angle: the missing list)

> **Subject:** what's missing
>
> Rather than another list of features, here's what Relaydesk doesn't do yet: no internal notes —
> which caps it at about three agents — no SLA or business hours, no macros, no Slack or Discord,
> no import from Zendesk.
>
> What does work: email in and out with proper threading and bounce handling, a help centre on your
> own subdomain, a widget that answers from your published articles and hands over to a ticket with
> the transcript attached, and a scoped-key API.
>
> If that list is a no, it's a clean no and I'll stop here. If it's a maybe, I'd rather have five
> teams running this in production and telling me what breaks than five hundred stars.

### Email 4 — Day 18 (breakup, with something useful attached)

> **Subject:** closing the loop
>
> I'll leave this one alone. If a self-hosted desk with no per-resolution bill ever becomes
> relevant, the source and I are both easy to find.
>
> One thing that may be useful either way: we published a worked production setup for a support
> mail pipeline — inbound catch-all on Migadu, outbound over SES, with the DNS records, the
> verification steps and the failure modes that bite. No signup, and useful even if you never touch
> Relaydesk.

### Personalisation openers — verify each before sending

Replace the first line of Email 1. Each of these is checkable in under two minutes; if you can't
confirm it, don't use it.

| Account | Opening line |
|---|---|
| **Migadu** | "We run Relaydesk's own inbound catch-all on Migadu — you're named in our deployment docs as the recommended setup. So this is a customer writing, which is either a good or a strange way to start." |
| **mailbox.org / Heinlein** | "You sell privacy mail to German SMBs and public authorities, which means every one of your customers eventually asks where *their* data sits. Presumably they ask about your support system too." |
| **Tuta** | "You've been public about not putting customer data through US cloud services. That position has an awkward consequence: every AI help desk on the market is a US model vendor with a UI on top." |
| **Nextcloud** | "Your entire pitch is that the data stays where the customer put it. A hosted support portal is the one place in that story where it doesn't." |
| **OpenProject** | "openDesk has eight modules and no help desk in any of them. I'm not pitching you on that gap — but you're closer to the people who'll feel it than anyone." |
| **Penpot** | "Design tools attract users who email rather than open a GitHub issue. That's a different support load than the rest of your ecosystem has to carry." |

---

## Segment 2 — India regulated (fintech infrastructure, health, brokerages)

**To:** **DPO / Head of Compliance first**, Head of Customer Experience second. The compliance lead
has a dated obligation; the support lead only has a preference.
**Goal:** a reply and a waitlist conversation now, a pilot when notes and SLA ship.
**Cadence:** Day 0 / +5 / +12 / +20.

### Email 1 — Day 0 (to compliance)

> **Subject:** ticket data
>
> A question you may already have had to answer internally: where do your support tickets live?
>
> They tend to be the last unmapped store of personal data in a regulated stack — names, PAN,
> account and transaction detail, pasted in by customers, sitting in a desk hosted somewhere else.
> RBI already requires the entire payment data set on systems located only in India. DPDP's full
> compliance date is 13 May 2027.
>
> Relaydesk is an AGPL support desk that runs inside your own VPC, on your Postgres, with whichever
> model key you choose — or no model at all.
>
> Worth a conversation before an audit forces one?

### Email 2 — Day 5 (angle: the renewal, can be sent to the CX lead instead)

> **Subject:** desk renewal
>
> If your help desk renewal arrives with an AI line priced per resolution, it's worth knowing the
> alternative before signing for another year.
>
> Relaydesk answers from your own published help articles, using your own model key, with a daily
> spend ceiling you set in the console. There's no per-resolution billing, because there's no vendor
> in the middle taking a cut of your deflection rate.
>
> It's self-hosted and AGPL, so the residency conversation is finished before it starts.
>
> Early, and I'd rather say so: it fits a team of about three agents today. Worth a look?

### Email 3 — Day 12 (angle: the thing auditors actually ask)

> **Subject:** data flow mapping
>
> The DPDP question that catches teams out isn't the privacy notice. It's the data flow map — every
> processor that touches personal data, where it's stored, and how it's deleted when a customer asks.
>
> A hosted help desk is a processor holding free-text tickets full of identifiers, indexed for
> search, backed up to a region you didn't choose, and now increasingly piped to a model vendor for
> AI answers. Erasure across that chain is the part nobody has a clean answer for.
>
> Self-hosting the desk collapses that chain to one database you already map.
>
> Our multi-tenancy and data-handling design notes are public if that's useful to you regardless.

### Email 4 — Day 20 (breakup)

> **Subject:** closing the loop
>
> I'll stop here. Two honest gaps, in case they're the reason: there's no DPA and no SOC 2 report
> yet, and no SLA engine in the product. Both are on the way; neither is today.
>
> If it's useful, the deadline sequence is worth having on a slide somewhere: soft enforcement ends
> around November 2026, hard compliance is 13 May 2027, and the support stack is usually the last
> thing anyone maps.

### Personalisation openers

| Account | Opening line |
|---|---|
| **Setu** | "You run support on Freshdesk at support.setu.co. For an AA and UPI business, that's a processor holding financial identifiers outside your own boundary." |
| **Juspay** | "You open-sourced your payments stack, so I'll skip the part where I explain why AGPL matters. The relevant bit: the model endpoint is a config field, so inference can stay inside your infrastructure too." |
| **Eka.care** | "ABDM-linked records make your support queue a PHI store, not a ticket queue. That's a different conversation from every other desk vendor's." |
| **E2E Networks** | "Your pitch is that Indian workloads stay on Indian infrastructure. A self-hosted support desk is both something you'd run and something you could offer the customers already buying that argument from you." |
| **M2P Fintech** | "You've published on RBI localisation, so you've effectively already written the argument I'd be making. The unasked question is whether the support desk was in scope." |
| **Exotel** | "You run Freshdesk at support.exotel.com. Telecom metadata plus DPDP scope makes that a heavier processor relationship than it looks." |
| **Decentro** | "Banking APIs mean your customers' compliance posture becomes yours. Support tickets are usually where that leaks first." |

---

## Segment 3 and the hosting platforms — first touch is not email

**Agencies, MSPs, Frappe/ERPNext partners.** LinkedIn or a direct founder email, one message, no
sequence:

> Libredesk and Zammad want one install per customer. Relaydesk is multi-tenant by design —
> a workspace per client, scoped API keys per workspace, a branded help centre on each client's own
> subdomain, one deployment you operate. If per-seat desk pricing across 30 client brands is eating
> your margin, this is worth twenty minutes. AGPL, self-hosted.

**Cloudron, PikaPods, Elestio, Coolify.** Do not email. Post a proper app request in their public
channel — working Compose file, screenshot, resource requirements, honest scope including the
missing features. These communities reward a maintainer who arrives with the packaging already
done, and a listing is permanent inbound you never have to send again.

---

## Sending rules

- **Plain text. No HTML, no images, no tracking pixels, one link maximum.** Segment 1 will notice
  a pixel and it will cost you the reply.
- **Separate sending domain** from the product domain, warmed over two to three weeks. Do not risk
  the domain your outbound help-desk mail will eventually go out on.
- **20–30 sends a day maximum** at this list size. These are 30 accounts, not 3,000 — every one is
  worth researching by hand.
- **Reply to your own thread** for follow-ups; don't start new threads.
- **Send Tue–Thu.** For India, mid-morning IST; for EU accounts, before 10:00 CET.

## Compliance

- **EU recipients:** B2B cold email under GDPR runs on legitimate interest, which requires relevance
  to the recipient's professional role, a clear identity, and a working opt-out in every message.
  Germany is stricter than most of the EU on unsolicited commercial mail — keep these genuinely
  individual, never bulk, and honour an opt-out instantly and permanently.
- **India:** DPDP obligations sit on the recipient's data, not on your outreach, but hold yourself
  to the same standard you're selling.
- **Both:** record the **source URL and the date** for every contact before the first send, and keep
  a suppression list. A one-line plain-text unsubscribe at the foot of each message is enough.

## What to measure

At 30 accounts the only numbers that mean anything are **replies** and **installs**. Ignore open
rates — you aren't tracking opens. A 10–15% reply rate on a list this well-qualified is the bar; a
positive-reply rate below 5% means the list is wrong, not the copy. Anyone who replies with a
specific objection ("no notes is a blocker", "we need an SLA") is worth more than the install:
that's your roadmap being written by the people who'd pay for it.
