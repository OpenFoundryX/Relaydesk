# Targeting just-launched funded startups

**Date:** 2026-09-13
**Supersedes** the segment ranking in
[2026-09-13-initial-customers-and-icp.md](../research/2026-09-13-initial-customers-and-icp.md)
for account selection. The ICP mechanics, disqualifiers and product-constraint findings in that
document still hold.

---

## 1. What this ICP fixes, and what it breaks

**Fixes.** It matches the three-agent cap in the product exactly — founder-led support *is* a
one-to-three person queue. The buying committee is one person. No procurement, no security review,
no DPA, no SOC 2 question, no six-week evaluation. A founder can go from cold to installed in a
single evening, and that is the fastest path to the five production installs you actually need.

**Breaks, and this is the part to design around:**

**There is no competitor in the deal — and no budget line either.** Every recently funded startup
probed on 2026-09-13 was running **no support tooling at all**. That is not a gap you walk into; it
is the absence of a purchase. You are not displacing Zendesk, you are asking someone to stop using
Gmail. Nobody has ever been fired for continuing to use Gmail.

**The AI has nothing to ground on.** Relaydesk answers from *published KB articles*. A startup six
weeks past launch has four docs pages. Your flagship feature degrades to the escalation form
precisely in the cohort you are now targeting — and the escalation form is not a reason to switch
off a shared inbox.

**Self-hosting is a cost to this buyer, not a benefit.** Docker Compose, Postgres, an IMAP
catch-all mailbox, wildcard DNS and a wildcard TLS certificate is a half-day of founder time that
produces nothing a customer can see. The AGPL and sovereignty arguments — the entire wedge in the
previous document — are **negative value** here. This ICP is a managed-cloud motion or it is
nothing.

**Funding is not the qualifier.** YC's Summer 2026 batch is 235 companies, **52% B2B and roughly
5% consumer** ([neweconomies](https://www.neweconomies.co/p/y-combinator-summer-26-batch)). A B2B
startup with twelve design partners does not have a support queue — it has a shared Slack channel,
which is Pylon's product, not yours. Most of a funded cohort is structurally disqualified.

---

## 2. The actual qualifier: self-serve user volume

Inside "just-launched and funded", the thing that separates a prospect from a non-prospect is
**how many low-value users they have**, not how much they raised.

| Qualifies | Does not |
|---|---|
| Consumer app with a free tier | B2B SaaS with < 30 logos |
| D2C ecommerce (order, delivery, returns questions) | Deep infra / devtools sold top-down |
| Prosumer SaaS, self-serve signup | Anything with an AE-led sales motion |
| Marketplace (two-sided = double the tickets) | Services and agencies |
| Fintech or neobank app (KYC, refunds, failed payments) | Hardware pre-revenue |
| Edtech with student users | Design-partner-stage anything |

**Pass/fail, all four required:**

1. Funded within the last **6 months** (fresh money, first stack being chosen)
2. Publicly launched and **self-serve** — anyone can sign up without talking to sales
3. Founder or first hire visibly answering support (see §4 for how to check in two minutes)
4. **A `support@`, `help@` or in-app contact route that currently goes to a shared inbox**

Realistic pool: Indian seed activity ran at **$121M across 60 deals** in the recent window
([Inc42](https://inc42.com/lists/top-20-funded-d2c-startups-in-india-2026/)). Apply the ~20–25%
self-serve filter and that is **roughly 12–15 genuinely qualified Indian companies per quarter.**
Plan around that number. It is too small to support an outbound campaign as the primary channel,
which is the single most important consequence in this document.

---

## 3. The buying trigger — they do not buy at launch

A founder answering fifteen emails a week is *enjoying it*. Founder-led support is a thing people
brag about on LinkedIn. The purchase happens at a specific, observable break point, and arriving
before it wastes the contact.

**The four triggers, in order of how strongly they predict a purchase:**

| Trigger | How you see it | Why it converts |
|---|---|---|
| **First support hire** | A "Customer Support" or "Community" role on their careers page or LinkedIn | Two people cannot share a Gmail inbox. This is the single strongest signal in this entire document |
| **Second founder pulled into the queue** | Two different names replying from the same support address | The pain has become visible internally |
| **Public complaint about response time** | App store reviews, X/Twitter replies, Reddit | Support is now a growth problem, not a chore |
| **They start writing docs** | A `/help`, `/docs` or `/faq` route appears that did not exist | They are trying to deflect — and they have just built the corpus your AI needs |

That last one is the one to instrument. **A startup publishing its first help centre is telling you
it has repeat questions**, which is both the pain and the missing ingredient for your AI answers.
That is the moment to arrive, and it is checkable with a weekly HEAD request.

---

## 4. Sourcing — the list regenerates weekly

Thirty names is the wrong deliverable for this ICP. A just-launched startup is a **timing target**;
any static list is stale in thirty days. What follows is a ritual, run every Monday, about forty
minutes.

**Funding sources (dated, which is the point):**
- [Inc42](https://inc42.com/) and Entrackr weekly India funding roundups
- [fundup.ai/recently-funded-startups/country/india](https://fundup.ai/recently-funded-startups/country/india)
- Tracxn / Crunchbase "last 30 days, seed, India" saved search
- YC's own directory filtered by current batch — [ycombinator.com/companies](https://www.ycombinator.com/companies)
- Product Hunt weekly leaderboards, cross-referenced against funding news

**Then filter in this order** — cheapest check first:

1. Is signup self-serve? (30 seconds on their site) → kills ~half
2. Does a `support@`/`help@`/contact route exist? → kills most of the rest
3. Run the probe script on the survivors — a startup already running Intercom or Gorgias has
   **budget and pain but also a switching cost**; one running nothing is your actual target but may
   be too early
4. Check careers page for a support or community role → this moves an account to Hot
5. `HEAD https://<domain>/help` weekly on everything in the pipeline → the docs trigger

**Keep a watchlist, not a lead list.** Most accounts are not ready when you find them; they become
ready three to five months later. The value compounds only if you keep checking.

### Named accounts from the current window

These are from dated August–September 2026 India funding announcements
([Newskart roundup](https://www.newskart.com/india-startup-funding-update-from-august-10-to-september-4-2026-big-cheques-ai-bets-and-founders-to-watch/)),
filtered to sectors with a plausible self-serve support queue. **All are unqualified against §2
criteria 2–4** — I could not confirm launch state, support routing or team shape for any of them,
and several domains did not resolve on a guessed spelling.

| Company | Round | Sector | Queue likely? | Status |
|---|---|---|---|---|
| Scrubsy | $3M seed | D2C ecommerce | Yes — orders, returns | Site resolves, **no support tooling detected** |
| Be Clinical | $2.2M seed | D2C ecommerce | Yes | Domain not confirmed |
| CHINI KUM | $174K | D2C ecommerce | Yes | Domain not confirmed |
| Scooby's Club | $250K pre-seed | Pet care services | Yes — bookings | Domain not confirmed |
| SpeakX | undisclosed | Edtech, consumer | Yes — student users | Site resolves, **nothing detected** |
| Wippi | $1.2M seed | AI, consumer-facing | Maybe | Site resolves, **nothing detected** |
| Rezolv | $12.5M Series A | Fintech SaaS | Maybe — likely sales-led | Domain not confirmed |
| Leanwatts | $2M seed | EV charging | Maybe — field support | Not checked |

Every one of these needs criteria 2–4 checked by hand before it is worth an email. **Treat this
table as a worked example of the ritual, not as a list to send to.** By the time you read it in a
month, the right eight names will be different ones.

---

## 5. The channel that actually works: sell to the investor, not the startup

Twelve to fifteen qualified companies a quarter cannot carry an outbound motion. But they arrive
**in batches, through a small number of doors**, and those doors already run vendor programmes.

Antler alone offers **$4 million in total partner perks** to its portfolio
([Antler India](https://www.startupgrantsindia.com/providers/antler-india)); 100X.VC has backed
**199 companies since 2019** and is India's most active first-check pre-seed investor
([100X.VC](https://www.peony.ink/blog/accelerators-india)). One relationship with a platform team
puts Relaydesk in front of every subsequent batch, automatically, with the investor's
trust attached — which is worth more than any cold email you will ever write to a founder.

**This is the real answer to "who to contact in the company": the company to contact is the fund.**

| Target | Why | Who to contact |
|---|---|---|
| **Antler India** | Explicit $4M partner-perks programme, 80+ India portfolio companies, new cohorts continuously | **Platform / Portfolio Services lead**, or the Partner running the India programme |
| **100X.VC** | India's most active first-check investor; 199 companies; every one is exactly this ICP | Platform or Community lead |
| **Accel Atoms** | Early-stage programme with explicit GTM support | Platform team |
| **Blume Ventures** | Large early portfolio, active founder-services function | Platform / Founder Success |
| **PedalStart, NSRCEL, T-Hub, IIMA Ventures** | High-volume, low-gatekeeping, will say yes faster than a tier-1 fund | Programme manager |
| **YC deals page** | Highest-volume door in the world for this ICP | Requires a YC company or a listed-vendor route — check the current process |

**What you offer them:** a genuinely free hosted tier for portfolio companies, set up in ten
minutes, with you personally on hand for the first month. Not a discount on a paid plan — portfolio
perks that are discounts get ignored. The pitch to the platform lead is *"your founders are
answering support out of Gmail and losing threads; here is a free thing that fixes it, and I will
onboard each one myself."* That is a low-risk yes for them and a batch of design partners for you.

Start with the smaller programmes. PedalStart or NSRCEL will answer this month; Accel will take a
quarter.

---

## 6. Who to contact at the startup

At two to five people there is no title structure worth mapping. The question is only **which
founder is the one holding the support inbox**, and there is a two-minute method that answers it
and qualifies the account at the same time:

1. **File a real support request.** Ask something a genuine early user would ask.
2. **Read the reply.** The name on it *is* your buyer. The response time tells you whether the pain
   exists yet. Whether it came from a shared inbox or a desk tells you the switching cost. The tone
   tells you whether they are enjoying it or drowning.
3. If no reply comes in 48 hours, that is also an answer — and it is the opening line of your email.

Fallbacks, in order: whoever posted the Product Hunt or LinkedIn launch; whoever is listed as the
author on the changelog or docs; in a technical team, the founder who is *not* the one merging PRs
all day. Default to the CEO if the team is two people.

---

## 7. The sequence — different register entirely

Two emails, not four. A seed founder reading a cold email about help-desk software is one swipe
from archiving; length is the enemy. Everything about data residency, AGPL and per-resolution
pricing comes out — none of it is a founder's problem at this stage.

### Email 1 — the trigger email (send only after a trigger from §3 fires)

> **Subject:** support inbox
>
> I emailed your support address on Tuesday and got a reply from you personally, which is the right
> answer at your stage and stops being the right answer at about forty tickets a week.
>
> I'm building Relaydesk. The short version: your support mail becomes a real queue instead of a
> Gmail thread, your help articles answer the repeat questions automatically, and anything the
> answer doesn't cover comes to you with the whole conversation attached.
>
> It's free, and I'll set it up with you in ten minutes on a call if that's faster than reading docs.
>
> Worth it?

### Email 2 — Day 6, the only follow-up

> **Subject:** the four questions
>
> Every founder doing their own support ends up answering the same four questions forever. Pricing,
> refunds, one broken integration, and "how do I do the thing".
>
> Write those four up once and Relaydesk answers them for you from then on — the reply cites the
> article, and if the customer isn't satisfied it becomes a ticket with the transcript attached, so
> you never start from a cold "hi, what's the issue".
>
> Free, hosted, ten minutes. If it's not useful yet, it will be around forty tickets a week — happy
> to just check back then.

That closing line is deliberate: it converts a "no" into a dated follow-up and keeps the account on
the watchlist without another cold open.

**Do not send a breakup email to this ICP.** They are not evaluating and there is nothing to break
up from. Move them to the watchlist and re-approach on the next trigger.

---

## 8. What has to change in the product for this to convert

This ICP is reachable today but will not *convert* today. Four things, in order of impact:

1. **Hosted, self-serve signup.** Non-negotiable. A founder will not run Compose, an IMAP catch-all
   and wildcard DNS to try a help desk. Everything else on this list is worthless without it.
2. **Seed the knowledge base automatically.** Point Relaydesk at their existing site or docs and
   generate draft articles from it. This kills the cold-start problem *and* delivers the first
   visible win inside ten minutes — which is the entire onboarding argument.
3. **Gmail forwarding as the first-run path, not a DNS exercise.** "Forward your support address
   here" is one setting. Anything more loses them.
4. **Internal notes**, the moment a second person joins the queue — which is exactly the trigger
   that made them buy. Without it you will acquire at the support-hire moment and churn eight weeks
   later, which is the worst possible outcome.

Items 1 and 2 are the gate. Until both ship, treat this ICP as **pipeline to warm, not revenue to
close**: run the Monday ritual, build the watchlist, and open the accelerator conversations now so
the channel exists when the product is ready for it.

---

## 9. What to expect

- **Outbound to founders: low single-digit reply rate at best**, because there is no pain to name
  until a trigger fires. Send only on a trigger and this becomes respectable.
- **The accelerator channel is the whole game.** One yes from a platform team is worth a quarter of
  cold email.
- **Watchlist conversion is the number to track**, not reply rate: of the accounts you logged, how
  many fired a trigger within six months, and how many of those replied when you arrived on it.
- **Retention will be your problem, not acquisition.** These companies die, pivot, or outgrow a
  notes-less desk. Assume heavy churn and judge the motion on production installs and the feedback
  they generate, not on ARR.
