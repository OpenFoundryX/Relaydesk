# Customer-support platform landscape — findings for Relaydesk

**Date:** September 2026
**Audience:** Relaydesk product/eng (AGPL, self-hostable support platform for small startup support teams)
**Method:** Web research against vendor primary sources where possible, third-party analysis where not. Every non-obvious claim carries a URL. Claims I could not verify against a primary source are marked **[unverified]**. Vendor self-description is separated from user-reported experience throughout.

A note on source quality before anything else: **this category's search results are overwhelmingly polluted by competitor-written "pricing teardown" content.** Fin publishes pricing pages about Sierra and Decagon; Unthread publishes pricing teardowns of Thena and Plain; eesel, Macha, Featurebase and Coworker publish SEO pages about everyone. I have preferred vendor primary pages and named press wherever the number mattered, and flagged the rest.

---

## 1. The AI-native entrants

### What they actually claim

| Vendor | Core claim | Pricing model | Source |
|---|---|---|---|
| **Sierra** | Agent SDK; "define the goal and our Agent SDK directs the resources to achieve it across complex, multi-step workflows"; composable skills (triage, respond, confirm); deploy across chat, phone, email, SMS; "your data is never used to train models" | Outcome-based, per resolution, negotiated; no public price | [sierra.ai/platform](https://sierra.ai/platform) |
| **Decagon** | "Agent Operating Procedures" — define agent behaviour in natural language rather than "complex configuration languages that slow iteration, inflate costs, and drain engineering time"; build once, deploy to voice/chat/email; built-in A/B testing and observability | Not disclosed publicly. Decagon's own blog argues resolution is hard to define and reports most customers pick **per-conversation** over per-resolution for predictability | [decagon.ai](https://decagon.ai/), [decagon.ai/blog/pricing-ai-agents](https://decagon.ai/blog/pricing-ai-agents) |
| **Lorikeet** | Not a "deflection" bot — handles complex, high-stakes, regulated work end-to-end: "40-step refund flows", fintech/healthtech, executes SOPs against real systems (Stripe, internal APIs), escalates with context already gathered | Not published | [lorikeetcx.ai](https://www.lorikeetcx.ai/) |
| **Parloa** | "AI Agent Management Platform" — manage *fleets* of voice and chat agents alongside humans in contact centres | Enterprise, not published | [parloa.com](https://www.parloa.com/); $350M Series D at $3B, Jan 2026 ([Sacra](https://sacra.com/c/parloa/)) |
| **Intercom Fin** | Answers grounded in your content; Guidance (plain-language behavioural rules); Procedures (multi-step actions against live systems); Fin Voice 2; an **MCP server exposing Fin as a tool to external agents** | **$0.99 per outcome** (resolution, procedure handoff, disqualification), **$9.99 per qualification**, 50 outcomes/mo minimum. No seat cost when used on non-Intercom helpdesks. Copilot $35/user/mo | [fin.ai/pricing](https://fin.ai/pricing/) |
| **Zendesk AI agents** | "Autonomous Service Workforce"; Resolution Platform trained on ~20B ticket interactions; Resolution Learning Loop; no-code Agent Builder; voice agents in 60+ languages | "Pay only for customer requests that were successfully resolved by the AI agent, without any escalation to a human agent." Seats still $19–$115/agent/mo; Copilot **+$50/agent/mo** | [zendesk.com/pricing](https://www.zendesk.com/pricing/), [Relate 2026 coverage](https://www.cmswire.com/customer-experience/zendesk-unveils-autonomous-ai-workforce-at-relate-2026/) |
| **Forethought** | Solve / Triage; "self-improving" agents that generate their own workflows | ~$0.90/resolved conversation **[unverified — Forethought never published pricing]** | **Acquired by Zendesk**, announced 11 Mar 2026, closed 31 Mar 2026 — Zendesk's largest acquisition ever ([TechCrunch](https://techcrunch.com/2026/03/11/zendesk-acquires-agentic-customer-service-startup-forethought/), [Zendesk newsroom](https://www.zendesk.com/newsroom/articles/forethought-acquisition/)) |
| **Gorgias** | Ecommerce-specific; pre-trained on ecommerce conversations; edits orders, subscriptions, generates discounts | ~$0.90–$1.00 per resolution **and** the conversation still counts as a helpdesk ticket — effectively double-billed **[third-party analysis, not vendor-confirmed]** | [gorgias.com/blog/ai-agent-pricing](https://www.gorgias.com/blog/ai-agent-pricing), [eesel breakdown](https://www.eesel.ai/blog/gorgias-ai-agent-pricing-2025) |
| **Help Scout** | AI Answers, AI Drafts, AI Assist | **$0.75/resolution** for AI Answers, with a customer-settable monthly spend cap. Seats $25/$45/$75 | [helpscout.com/pricing](https://www.helpscout.com/pricing/) |
| **Freshdesk** | Freddy AI Agent + Freddy Copilot | **$49 per 100 AI Agent sessions** (~$0.49/session, *session* not resolution), expiring monthly with no rollover; Copilot $29/agent/mo; base seats $19–$89 (first list-price raise in five years) | [dragapp analysis](https://www.dragapp.com/blog/freshdesk-pricing/) **[third-party]** |

### What this implies about how buyers now judge these products

Three things, and they matter more than the feature lists.

**1. The unit of purchase has moved from the seat to the outcome — but nobody agrees what an outcome is.** Fin bills four *different* outcome types at two different prices. Zendesk bills a "resolution" defined as no human escalation. Freshdesk bills *sessions*, which is usage dressed as outcome. Gorgias bills a resolution *and* a ticket. Help Scout bills resolutions but lets you cap the spend.

This divergence is the important finding, not the convergence. Decagon — an outcome-pricing vendor — says out loud in its own blog that most of its customers choose per-conversation because it is predictable and "avoids arguing over what counts as a resolution" ([decagon.ai](https://decagon.ai/blog/pricing-ai-agents)). Moveworks' CEO publicly declined outcome pricing on the grounds that a resolved IT ticket has no single value **[reported second-hand; I could not find the original interview]**. Critics have made the structural argument well: outcome pricing "gets dangerous when success is subjective, delayed, or easy to dispute" — if a frustrated customer stops responding, is that a resolution? ([The Pricing Conundrum](https://thepricingconundrum.substack.com/p/outcome-based-pricing-as-insurance), [getlago](https://getlago.substack.com/p/outcome-based-pricing-is-not-the)).

**2. Buyers have learned to distinguish deflection from resolution, and they now ask for the denominator.** The 2026 benchmark literature is explicit that "resolution rate is not deflection rate — deflection counts conversations a human did not touch; resolution counts problems actually solved. The two are routinely conflated in marketing." Reported numbers: enterprise median tier-1 deflection ~41%, top quartile ~59%; Lorikeet puts 2026 industry-average *resolution* at 44.8%; deflection-only bots that cannot act land at 10–30% ([Lorikeet benchmarks](https://www.lorikeetcx.ai/articles/resolution-rate-ai-customer-support-benchmarks-2026), [digitalapplied](https://www.digitalapplied.com/blog/ai-support-deflection-resolution-layer-2026-playbook)). One number in there deserves highlighting because it is the quality tell: re-contact rate on AI-resolved conversations **11.3% vs 8.7% human-resolved** **[attributed to Zendesk CX data by a third party; I could not verify against Zendesk directly]**.

**3. Anything sold per-resolution must be auditable, or the buyer will not trust the invoice.** This is why Fin Voice now "shows the knowledge sources, guidance, and instructions it used on each call — making it easy to audit decisions" ([fin.ai/updates](https://fin.ai/updates)), and why Zendesk's whole Relate 2026 narrative is built on "verified resolutions" and a Resolution Learning Loop that records intent, steps taken, whether it resolved, and how long ([diginomica](https://diginomica.com/zendesk-relate-2026-outcome-based-future-verified-resolutions)). Auditability stopped being a compliance nicety and became a **billing** requirement.

---

## 2. The small-team / developer-first tier

| Product | Position | Price | Source |
|---|---|---|---|
| **Pylon** | "The Agentic Support Platform" for B2B. Slack, Teams, email, chat, SMS, WhatsApp, Telegram, Discord, phone. Agent types: Assist, Background, Slack, Support. "Skills" = reusable agent instructions. Pulls Salesforce/HubSpot/Snowflake/BigQuery/Gong/Linear/PostHog | **Not published** — demo-gated | [usepylon.com](https://www.usepylon.com/) |
| **Plain** | API-first, GraphQL, used by Vercel/Cursor/n8n. **BYOA — bring your own agent** on the top tier. AI credits metered | Foundation **$35/seat/mo** (2,000 AI credits), Horizon **$299/mo for 3 seats**, +$99/seat (15,000 credits), Frontier custom (BYOA, SSO/SCIM) | [plain.com/pricing](https://www.plain.com/pricing) |
| **Unthread** | Slack-native internal helpdesk | $50 / $75 per agent/mo, 5-seat minimum **[third-party]** | [Capterra](https://www.capterra.com/p/10023623/Unthread/) |
| **Thena** | Slack/Teams B2B support | $29 Starter (1,000 ticket cap) → $79 Standard → $119 Enterprise (Teams gated to Enterprise) **[third-party, published by competitor Unthread — treat as directional]** | [unthread.io/blog/thena-pricing](https://unthread.io/blog/thena-pricing/) |
| **Chatwoot** | Open-source omnichannel inbox | Cloud $0/$19/$39/$99 per agent/mo. **Captain AI metered in credits: 300/500/800 per month by plan, $20 per additional 1,000** | [chatwoot.com/pricing](https://www.chatwoot.com/pricing) |
| **Zammad** | Open-source ticketing, German, compliance-forward | Community Edition free, unlimited agents | See §4 |
| **FreeScout** | Ultra-light PHP shared inbox, 10MB distribution kit, runs on shared hosting | Core free; official modules **$4–$15 one-time, lifetime licence per instance** | [freescout.net/modules](https://freescout.net/modules/) |
| **Libredesk** | **AGPL-3.0, single Go binary.** Omnichannel inbox, widget, help centre, KB-grounded AI assistant, agent copilot, CSAT, SLA, RBAC, macros. ~2.9k GitHub stars | **Free, every feature, no paid tier, no cloud** | [github.com/abhinavxd/libredesk](https://github.com/abhinavxd/libredesk), [libredesk.io](https://libredesk.io/) |
| **Helpy** | MIT open-core, Rails. Appears dormant — I found no 2025/2026 release activity | — **[maintenance status unverified]** | [github.com/helpyio/helpy](https://github.com/helpyio/helpy) |

### Pylon specifically: what the Slack-first model does that a helpdesk cannot

Pylon's founding observation was that B2B companies were already doing support in Slack, Teams and Discord rather than in email and ticket forms, and that legacy platforms "were built for B2C and treated B2B customer needs as an afterthought" ([Series B announcement](https://www.usepylon.com/blog/announcing-our-31m-series-b)). Three capabilities follow from that which a ticket-shaped helpdesk structurally cannot replicate:

1. **The conversation lives where the customer already is, in a shared channel with their colleagues.** A traditional helpdesk models a thread between one contact and one agent. A Slack Connect channel is a persistent, many-to-many room shared with an *account*. You cannot retrofit this by adding "Slack" as a channel that forwards messages into a ticket — the social object is different.
2. **The account, not the contact, is the primary record.** Pylon surfaces contract value, feature usage, stakeholders and renewal-risk signals, and lets support, CS, solutions engineers and AEs work the same account. This is the capability Relaydesk most conspicuously lacks (only individual contacts).
3. **Cross-functional presence.** Because the channel is in Slack, non-support people participate natively. In a helpdesk, that requires seats.

Pylon's own numbers: 750+ customers at Series B (Aug 2025), 1,500+ B2B companies on the site today, 150+ migrations from Zendesk/Intercom/Salesforce, two consecutive years of 5x+ revenue growth, $79M raised. These are **vendor self-reported**.

**The honest read for Relaydesk:** Pylon is winning a segment Relaydesk is not currently in and probably should not chase. Pylon's buyer is a B2B SaaS company with named enterprise accounts. Relaydesk's stated buyer is a small startup with a small support team — which is more likely to be serving many small customers over email and a widget. Building Slack-as-a-channel to compete with Pylon would be competing on Pylon's home ground with a worse version of its core asset.

---

## 3. The incumbents' recent direction

**Zendesk** is the clearest signal in the whole category. At Relate 2026 (Denver, 19 May) it announced the Autonomous Service Workforce: AI agents GA across messaging, email, voice and backend systems; a no-code Agent Builder; voice agents in 60+ languages; and outcome-based pricing as the default for AI. Then it spent its largest-ever acquisition on Forethought to get self-improving agents, saying it accelerated the roadmap by more than a year, and stated it expects autonomous AI to handle more service interactions than humans **this year** ([CMSWire](https://www.cmswire.com/customer-experience/zendesk-unveils-autonomous-ai-workforce-at-relate-2026/), [diginomica](https://diginomica.com/zendesk-relate-2026-resolution-platform-ai-driven-service-delivery), [TechCrunch](https://techcrunch.com/2026/03/11/zendesk-acquires-agentic-customer-service-startup-forethought/)).

**Front** is the most interesting and the least-discussed. Its recent shipping list includes ([front.com/whats-new](https://front.com/whats-new)):
- **External Agents** — deploy agents built with "Claude, OpenAI, Sierra, or another AI provider" inside Front, with visibility and performance tracking.
- **Autopilot Playbooks** / **Autopilot Resolve** — multi-step workflow automation with guardrails and human handoff.
- **Smart QA** — auto-generated scorecards on every closed ticket.
- **Smart CSAT** — **infers satisfaction without a survey**.
- Slack Connect support with threading and user attribution; Dialpad voice/SMS.

Two of those are strategically loud. *External Agents* is an incumbent conceding that it will not win the model layer and repositioning as the **system of record and control plane** for somebody else's agent. *Smart CSAT* is an incumbent conceding that the survey is dying.

**Help Scout** has kept its "simple" identity and priced AI as a metered add-on with a **spend cap** — $0.75/resolution, cap it yourself ([helpscout.com/pricing](https://www.helpscout.com/pricing/)). AI Drafts uses OpenAI models to draft replies from past conversations and Docs articles, billed at $50 per 100 conversations where a draft is generated on contact-based plans ([docs.helpscout.com](https://docs.helpscout.com/article/1539-ai-drafts-pricing-billing)). The spend cap is a small, unglamorous feature that I think is more commercially significant than most of the agent architecture announcements.

**Freshdesk** raised list prices for the first time in five years and split AI into two separately metered products (Copilot per-agent, AI Agent per-session). **[third-party]**

**Kustomer** shipped AI for Customers 2.0 in March 2026 adding "Procedures" — deterministic logic inside generative flows, "to enforce exact business rules without prompt engineering" ([eesel](https://www.eesel.ai/blog/kustomer-ai)) **[third-party]**. **Gladly** rebranded to gladly.ai in Q2 2026 **[third-party]**.

### What the category's direction actually says

- **Everyone has converged on the same shape:** AI agent answers → takes actions against real systems → hands off to a human with context. Sierra, Decagon, Lorikeet, Fin, Zendesk, Front Autopilot, Pylon, Gorgias. Nobody is arguing about the shape any more.
- **Determinism is being re-added on top of generative flows.** Decagon's AOPs, Kustomer's Procedures, Fin's Procedures, Front's Playbooks, Sierra's skills and guardrails. The industry tried pure LLM autonomy, found it unpredictable, and is bolting structure back on. That is the second-order lesson of 2025–26.
- **Incumbents are becoming hosts.** Front's External Agents and Intercom's MCP server (which lets *external* agents call Fin as a tool, [Intercom docs](https://www.intercom.com/help/en/articles/15481203-fin-agent-api-mcp-server)) both point the same way: the helpdesk expects to be an interoperable substrate, not the sole intelligence.

---

## 4. Open-source competitors specifically

This is the section where the most consequential news for Relaydesk sits.

**Chatwoot** — MIT for the main codebase, with a carve-out: the `enterprise/` directory is licensed separately under `enterprise/LICENSE` ([LICENSE](https://github.com/chatwoot/chatwoot/blob/develop/LICENSE)). 36.7k stars. Monetises three ways: cloud seats ($0/$19/$39/$99), **paid self-hosted plans** ($19 Premium Support / $99 Enterprise per agent/mo — SSO/SAML, SLA policies, Captain AI, voice, roles & permissions, custom branding are all behind these), and metered Captain AI credits ([self-hosted plans](https://www.chatwoot.com/pricing/self-hosted-plans)). So: open core, with the features a growing team needs most — SSO, SLAs, RBAC — gated.

*What users complain about:* performance. A long-running GitHub issue reports the self-hosted instance becoming "very slow with 10~15 users" and ~3,000 tickets with requests over 3 seconds despite adequate CPU and memory ([chatwoot#3425](https://github.com/chatwoot/chatwoot/issues/3425)). A Chatwoot discussion has the team acknowledging they "still need to do more performance testing" and have few metrics to share ([discussion #1358](https://github.com/orgs/chatwoot/discussions/1358)). Chatwoot's own docs note they don't offer one-time installation services due to limited resources ([FAQ](https://developers.chatwoot.com/self-hosted/faq)). Third-party commentary consistently lands on the same theme — the licence is free, the operations are not. Treat the operational-cost framing with suspicion (much of it is written by SaaS competitors), but the GitHub performance reports are first-party user evidence.

**Zammad** — AGPL community edition, unlimited agents. **Zammad 7.0 shipped AI features on 4 March 2026** with an explicit "free choice of large language model" positioning: AI summaries, a writing assistant with custom translation prompts, and AI agents for group assignment and prioritisation, with **local LLM support via Ollama for GDPR-compliant, sovereign data handling** ([Zammad 7.0](https://zammad.com/en/product/zammad-7-0), [press release](https://zammad.com/en/company/press/zammad-introduces-ai-features-with-free-choice-of-large-language-model)). Current stable 7.1.3 as of late August 2026 **[version number third-party]**.

**FreeScout** — AGPL-3.0 modules, core free with unlimited users, revenue from $4–$15 one-time lifetime module licences ([modules](https://freescout.net/modules/), [modules FAQ](https://freescout.net/modules-faq/)). Notable for being genuinely tiny (10MB, runs on shared hosting) — the opposite of the Chatwoot operational profile. It is also now marketing itself as "omnichannel AI-powered" ([GitHub](https://github.com/freescout-help-desk/freescout)).

**Libredesk — read this one carefully.** AGPL-3.0, Go + Vue, **single binary**, ~2.9k stars, and its feature list already includes: omnichannel inbox, embeddable chat widget, knowledge base/help centre, **"an AI assistant grounded in your knowledge base"** with human handoff, **agent copilot for drafting replies**, automation rules, RBAC, **CSAT surveys**, SLAs, macros, custom attributes, activity log. Its FAQ states: *"libredesk is open source and free to self-host. Every feature is included, and there are no paid tiers"* ([libredesk.io](https://libredesk.io/), [GitHub](https://github.com/abhinavxd/libredesk)).

This is the closest thing to a direct Relaydesk competitor I found. It is architecturally simpler to operate than Chatwoot (single binary vs Rails + Sidekiq + Redis), it is AGPL like Relaydesk, it already has KB-grounded AI *and* an agent copilot *and* CSAT — three things on Relaydesk's built/not-built boundary — and it has no monetisation model at all, which is both a competitive threat (free forever) and a sustainability question (no revenue).

**Frappe Helpdesk** — AGPL-3.0, frequently ranked top of open-source helpdesk lists in 2026 **[third-party listicles; I did not verify feature set or activity against the repo]**.

**Tiledesk** — open-source with a no-code chatbot builder **[third-party]**.

### How open source monetises in this category

Four patterns, in descending order of how well they appear to work:
1. **Cloud hosting + open core with SSO/SLA/RBAC gated** (Chatwoot). Works, at the cost of "open source" goodwill.
2. **Paid support/maintenance subscriptions on self-hosted** (Chatwoot Premium Support $19/agent, Zammad).
3. **Metered AI credits on top of seats** (Chatwoot Captain, $20/1,000 credits). New, and the most natural fit for an AGPL product because inference is a genuine marginal cost that customers understand.
4. **Cheap one-time module licences** (FreeScout, $4–$15). Sustains a small project; does not build a company.
5. **Nothing** (Libredesk). Not sustainable, but very hard to compete against on price.

### What open-source users complain about most

Ranked by frequency across GitHub issues, discussions and reviews:
1. **Operational burden and performance at modest scale** — the Chatwoot 10–15 user slowdown is the canonical example.
2. **Upgrade pain and unclear install instructions.**
3. **Bait-and-switch feeling when core-seeming features (SSO, SLA, RBAC, roles) turn out to be enterprise-gated.**
4. **Abandonment risk** (Helpy — no visible recent activity).

**Relaydesk's real open-source opportunity is #1 and #3, not features.** "Installs in one command, runs well on a $20 VPS with 15 agents, and nothing your team needs is behind a licence key" is a positioning nobody in this list credibly owns except Libredesk and FreeScout — and FreeScout is architecturally dated while Libredesk has no company behind it.

---

## 5. Emerging patterns — durable vs fashion

| Pattern | Verdict | Reasoning |
|---|---|---|
| **AI agent → action → human handoff with context** | **Durable. This is the category's permanent shape.** | Universally converged across every vendor tier from Sierra to Libredesk. Relaydesk already has the answer+escalate half. |
| **Grounding + visible citations** | **Durable, and already table stakes.** | Not differentiation any more. Zendesk documents an admin setting to display sources on generative replies; Fin Voice shows sources used per call. Legally reinforced: *Moffatt v. Air Canada* held the airline liable for a chatbot's invented bereavement-fare policy, rejecting the argument that the chatbot was a separate entity ([McCarthy Tétrault](https://www.mccarthy.ca/en/insights/blogs/techlex/moffatt-v-air-canada-misrepresentation-ai-chatbot), [CBC](https://www.cbc.ca/news/canada/british-columbia/air-canada-chatbot-lawsuit-1.7116416)). |
| **Determinism layered on generative flows** (Procedures / AOPs / Playbooks / Skills) | **Durable.** | Four independent vendors reached the same conclusion within ~12 months. That's convergent evolution, not fashion. |
| **Outcome-based pricing** | **Durable as a pricing *option*; the "per-resolution" unit specifically is fragile.** | Every incumbent adopted it in 18 months, but the definition is contested by the vendors themselves (Decagon), sometimes double-counted (Gorgias), and sometimes not an outcome at all (Freshdesk sessions). The lasting change is that **buyers now expect cost to scale with value and to be capped**, not that "resolution" survives as a unit. |
| **Agent copilots / AI draft replies** | **Durable and table stakes, but commoditised.** | Universally shipped, and notably priced as a premium per-seat add-on by everyone: Zendesk Copilot $50/agent/mo, Freshdesk Copilot $29/agent/mo, Fin Copilot $35/user/mo. Even free Libredesk has one. Being *without* one is now conspicuous. |
| **Knowledge-base gap detection** | **Durable, underbuilt, and the most under-priced idea in the category.** | Zendesk has Content Cues; a cottage industry (Fini, eesel, DocsHound) exists purely to bolt gap analysis onto Zendesk and Intercom, which tells you incumbents' versions are weak. It is also the only AI feature whose value *compounds* rather than recurring per-ticket. |
| **MCP / tool-calling so the agent acts** | **Durable as plumbing; overhyped as a product feature.** | Real adoption: Anthropic reported 10,000+ active public MCP servers and 97M monthly SDK downloads by March 2026; 41% of surveyed software orgs in limited or broad production ([Stacklok 2026 report via digitalapplied](https://www.digitalapplied.com/blog/mcp-adoption-statistics-2026-model-context-protocol)) **[survey figures third-party]**. Amazon Connect shipped MCP support ([AWS](https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-connect-mcp-support)). Intercom exposes Fin *as* an MCP server. But "we support MCP" is not a purchase reason; "the agent can cancel my subscription" is. |
| **Voice AI agents** | **Durable for enterprise/contact-centre; 2026 fashion for small startup support teams.** | Parloa raised $350M at $3B for this. Zendesk shipped 60+ language voice agents. Fin Voice 2 claims 24.5% higher resolution and 0.43s faster responses. None of that describes a five-person startup support team whose customers email and use a widget. |
| **Inferred/passive CSAT** (Front Smart CSAT) | **Durable, and it will eat the survey.** | Survey response rates reportedly collapsed to 10–18% for email CSAT with survey requests up 71% since 2020 **[third-party stats; directionally consistent across several sources but I could not verify the underlying study]**. Caveat worth keeping: one source claims AI-inferred sentiment is "40% less reliable" than structured survey scores **[unverified]**. |
| **Auto-QA / scorecards on every ticket** (Front Smart QA) | **Fashion for small teams.** | Automated QA on 100% of tickets is a workforce-management feature. A five-agent team reads its own tickets. |
| **"Agent fleets" / agent management platforms** | **Fashion, for this market.** | Parloa's framing presumes you have dozens of agents to manage. A small team has one. |

---

## 6. What is now table stakes

A buyer in Relaydesk's segment will assume these exist and will reject the product for lacking them.

1. **Internal notes.** This is the single most serious gap. It is not a feature, it is a precondition — every shared inbox since 2011 has had it, and every workflow ("can you check this?", "FYI the customer is angry", handoff context) depends on it. A buyer discovering this is missing will not file it as a gap; they will assume the product is a prototype.
2. **An AI agent that answers from your knowledge base, cites sources, and escalates.** Relaydesk has this. So does free Libredesk. It is no longer a differentiator.
3. **Agent-side AI draft replies.** Priced as a premium add-on by every commercial vendor and included free by Libredesk. Its absence is now conspicuous.
4. **CSAT of some kind.** Even Libredesk ships CSAT surveys. The measurement debate (survey vs inferred) is live, but *having no satisfaction signal at all* is not a defensible position.
5. **Snooze.** Trivially small, universally present, and the absence of it is felt hourly by anyone doing the job.
6. **The ability to take an action, not just answer.** The whole category has converged on this. A KB-only answering agent is now, in the benchmark literature's terms, a "deflection-only bot" — the 10–30% resolution tier.
7. **Cost control on AI spend.** Help Scout's user-settable monthly cap is the pattern. For a self-hosted product, Relaydesk's per-workspace token budgets already cover this — this is a table-stakes item Relaydesk has *already won*.
8. **Explicit AI disclosure in the widget.** As of **2 August 2026**, EU AI Act Article 50 requires that people be informed when they are interacting with an AI system, and the disclosure must be "perceivable in the interaction itself" — not buried in terms ([Article 50 guide](https://artificialintelligenceact.eu/transparency-rules-article-50/), [European Commission FAQ](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act)). This is now a compliance requirement, not a design choice.

## 7. What is genuinely differentiating right now

1. **Self-hostable + AGPL + a *good* AI agent, with no feature behind a licence key.** Chatwoot gates SSO/SLA/RBAC/Captain. Zammad's AI is new and ticket-centric rather than customer-facing. Libredesk has the feature set but no company. **Expected durability: 12–24 months**, and the clock is set by Libredesk's trajectory, not by Chatwoot's.
2. **Bring-your-own-model with a real audit trail and token budgets.** Only Zammad (free LLM choice, Ollama for sovereignty) and Plain (BYOA, but only on custom-priced Frontier) do this credibly. Relaydesk's per-workspace model config + token budget + audit trail is a genuinely strong asset that nobody in the small-team tier matches. **Durability: 18–36 months** — it is architecturally hard for a SaaS vendor to copy because their margin depends on owning inference.
3. **Server-resolved citations.** Most vendors show sources; doing the resolution server-side so the widget cannot be tricked into rendering a fabricated link is a real correctness property, and the audit/billing pressure described in §1 means the market is moving toward it. **Durability: 12–18 months before it is assumed.**
4. **Time-to-first-value measured in minutes.** The most repeated complaint about Zendesk from the small-team segment is multi-week onboarding needing developer involvement to configure automations ([Pylon's own migration research](https://www.usepylon.com/blog/switch-zendesk-best-alternatives-2026) — vendor-authored, treat as directional). **Durability: indefinite**, because it is a discipline, not a feature — which also means it is easy to lose.
5. **Operational lightness at small scale.** Given the Chatwoot performance reports, "15 agents on a small VPS, fast" is a defensible and checkable claim. **Durability: indefinite if maintained.**

## 8. What is overbuilt — deliberately refuse these

1. **Voice.** Parloa raised $560M+ total and Zendesk shipped 60+ languages. This is a contact-centre arms race. A five-person startup support team does not run a phone queue. **Refuse.**
2. **Slack/Teams as a first-class channel.** Pylon has an eight-year head start on the *social object*, not just the integration, and the B2B-account model that makes it valuable. Building a mediocre version costs months and wins nobody. A read-only "notify the team in Slack" webhook is a different and much cheaper thing — do that instead. **Refuse the channel; ship the notification.**
3. **Auto-QA scorecards on every ticket.** Workforce management for teams of 50+. **Refuse.**
4. **Agent fleet management / multi-agent orchestration.** You have one agent. **Refuse.**
5. **A full workflow/automation builder.** Kustomer, Decagon, Sierra, Front and Zendesk are all building visual/DSL workflow builders. This is the single largest sink of engineering effort in the category and it directly contradicts "little or no learning curve." **Refuse the builder; ship a small number of opinionated, named behaviours.**
6. **Conversation merging.** Genuinely fiddly (identity resolution, thread reconciliation, undo semantics, audit) and genuinely rare at small volume. **Defer indefinitely.**
7. **Full companies/accounts CRM.** A *lightweight* company grouping is worth having (see opportunity 5). A hierarchy with contract values, renewal dates, health scores and stakeholder maps is Pylon's product. **Refuse the CRM; ship the grouping.**
8. **Proactive/outbound messaging.** Intercom-style campaigns pull you into marketing automation, deliverability, and consent management. Enormous surface, different buyer. **Refuse.**

---

## 9. Ranked opportunities

### 1. Internal notes + @mentions
**What:** Private notes on a conversation, @mention a teammate, note-triggered notification, notes excluded from every customer-facing surface and from AI agent context by default.
**Why this product:** It is the one missing thing that makes Relaydesk read as unfinished. Every competitor at every price point has it. No amount of AI differentiation survives a demo where an evaluator asks "how do I ask a colleague about this without emailing the customer?" and the answer is "you can't."
**Effort:** Small. Days, not weeks — a message type, a visibility flag, a mention parser, a notification, and disciplined exclusion from the AI context window and email rendering.
**Risk:** Very low. The only real risk is the leak path — a note rendered into an email or fed to the agent as grounding is a serious incident. Test that specifically.

### 2. Knowledge-base gap detection, closing the loop into the editor
**What:** Every escalation and every low-confidence agent answer is clustered by topic. A "Gaps" view ranks missing/ambiguous topics by volume and escalation cost, shows the real customer questions behind each, and offers a one-click draft of a new KB article from the conversations that prove the gap — landing in the editor for a human to approve.
**Why this product:** This is the highest-leverage idea available to Relaydesk specifically, for four reasons. (a) It is the *direct output* of the strict-grounding bet — an agent that refuses to answer outside the KB produces a clean, high-signal gap log as a by-product. A permissive agent papers over gaps and cannot generate this data. **Strict grounding is what makes this feature possible.** (b) It converts the strictness from a limitation into a compounding asset: each gap closed permanently raises the resolution rate. (c) A cottage industry exists solely to bolt gap analysis onto Zendesk and Intercom ([Fini](https://www.usefini.com/guides/ai-knowledge-base-gap-conflict-detection-support), [eesel](https://www.eesel.ai/blog/zendesk-knowledge-gap-analysis), DocsHound), which is strong evidence incumbents' versions are inadequate. (d) Relaydesk already owns both halves — the agent and the knowledge base — in one product, which almost none of those bolt-on tools do.
**Effort:** Medium. Embedding + clustering of escalation reasons, a ranking heuristic, a view, and a generation prompt. Reuses existing model config and token budgets.
**Risk:** Clustering quality at low volume — a five-person team's ticket flow may be too sparse for meaningful clusters in week one. Mitigate by showing raw grouped questions before claiming statistical confidence, and by never auto-publishing an article.

### 3. AI draft replies for agents, grounded in KB + prior resolved conversations, with visible sources
**What:** When an agent opens a conversation, a draft is pre-generated citing the KB articles and prior resolved threads it drew from. Agent edits and sends, or discards. Never auto-sends.
**Why this product:** Table stakes (§6.3) and the single most commonly monetised AI feature in the category — which tells you buyers value it. Relaydesk already has retrieval, citations, model config, token budgeting and an audit trail; the copilot is mostly a new surface over existing machinery. It also fits the positioning: the fastest measurable win for a small team is not deflection, it is the agent finishing a reply in 20 seconds.
**Effort:** Small-to-medium, precisely because the grounding infrastructure exists.
**Risk:** Two. Draft-shaped complacency — agents rubber-stamping wrong drafts. Mitigate by showing the citation inline in the draft so the agent's eye lands on the evidence. And cost — pre-generating on open burns tokens on conversations nobody replies to; make it explicit-trigger or budget-aware.

### 4. Bring-your-own-tools: let the agent *act*, via MCP, with human-approval gates
**What:** A workspace admin registers an MCP server (or a few HTTP endpoints with a schema). The agent may call read-only tools freely and write tools only with an explicit policy: auto-allow, require agent approval, or never. Every call is written to the existing audit trail with arguments and result.
**Why this product:** This is the difference between the 10–30% resolution tier and the 70%+ tier in the benchmark data, and it is the one place where being self-hosted is a *structural advantage* rather than a trade-off: the customer's internal API is on the same network, behind the same firewall, and no data leaves. A SaaS vendor must build a connector marketplace; Relaydesk just needs to let the operator point at localhost. It also extends strict grounding rather than abandoning it — the agent still never invents; it retrieves from a *live* system instead of only a document.
**Effort:** Medium-to-large. MCP client, a tool registry UI, the approval-gate state machine, audit integration, and careful prompt-injection defence on tool results.
**Risk:** Highest of the top five. Tool results entering the context window are an injection vector; a write tool that misfires is a real-world side effect, not a bad sentence. Ship read-only tools first, write tools behind human approval only, and do not offer auto-allow on writes until there is evidence.

### 5. Lightweight company grouping (not a CRM)
**What:** Contacts group under a company, usually by email domain with manual override. A company view shows every conversation across its contacts. That is the whole feature.
**Why this product:** Even a small startup with a handful of B2B customers hits this within a month — two people from the same customer email in and nobody can see they're the same account. It is the 10% of Pylon's account model that delivers most of the everyday value, at 2% of the cost, and it unblocks later work (per-company SLAs, per-company agent context) without committing to building a CRM.
**Effort:** Small. A table, a domain-matching rule, a view, an override.
**Risk:** Scope creep — this is the feature that will generate requests for contract values, health scores and renewal dates. Write down in advance that the answer is no.

### 6. Inferred CSAT from conversation signals, with an optional one-click survey
**What:** After close, classify the conversation's outcome and customer sentiment from the transcript into a satisfaction signal, with the evidence span shown. Optionally append a thumbs up/down to the closing message for a calibration sample.
**Why this product:** CSAT is table stakes (§6.4) and Front has validated the inferred approach (Smart CSAT). For a five-person team, a survey with a 10–18% response rate produces a handful of data points a month — statistically useless. Inferred CSAT covers 100% of conversations from day one. It also reuses the model config and budget machinery, and it fills a gap Libredesk has already filled with plain surveys.
**Effort:** Small-to-medium.
**Risk:** Real. Inferred sentiment is reportedly materially less reliable than survey scores **[unverified]**, and a *wrong* satisfaction number is worse than none because teams act on it. Mitigate by labelling it honestly as an estimate, always showing the evidence, and shipping the thumbs-up sample so users can calibrate. Do not call it "CSAT" without qualification.

### 7. Widget identity verification (JWT)
**What:** Signed JWT identity for widget users, the modern equivalent of Intercom's HMAC user_hash, with an unverified mode that visibly restricts what the agent may disclose.
**Why this product:** Without it, anyone can boot the widget claiming someone else's email and read that person's conversation history. Intercom is explicit that this allows an attacker to "spoof the identity of another user... and gain access to previous conversations and potentially sensitive data" ([Intercom developer docs](https://developers.intercom.com/installing-intercom/web/identity-verification)). This becomes urgent the moment opportunity 4 ships — an agent that can *act* on behalf of an unverified identity is a vulnerability, not a feature. It is also the thing that blocks any security-conscious buyer at evaluation.
**Effort:** Small. JWT verification, a secret per workspace, docs, and a clear unverified-mode policy.
**Risk:** Low technically. The real risk is ordering: if opportunity 4 ships before this one, you have built an authenticated-action system with no authentication.

### 8. One-command install and a published small-scale performance profile
**What:** A single `docker compose up` or single-binary path to a working instance in under five minutes, plus a published, reproducible benchmark: N agents, M conversations/month, this hardware, these latencies.
**Why this product:** The #1 complaint about open-source support platforms is operational burden and degradation at modest scale — the Chatwoot 10–15 user slowdown is documented in their own issue tracker. Nobody in this space publishes an honest small-scale performance profile. Doing so is cheap, checkable, and attacks the incumbent open-source leader exactly where its users are unhappy. It also directly serves the stated positioning (easy onboarding, no learning curve) in the one dimension that positioning is usually tested: the first twenty minutes.
**Effort:** Small, ongoing. Mostly discipline and CI.
**Risk:** Lowest on the list. The only risk is publishing a number you later regress — so put it in CI.

**Deliberately excluded from the list:** snooze and conversation merging. Snooze is table stakes but too small to be an "opportunity" — just build it alongside notes. Merging is in the refuse-for-now pile (§8.6).

---

## 10. Where the evidence contradicts the product's current bets

### The strict-grounding bet: **right, but framed wrong, and mis-valued.**

Take the claim apart. The premise given to me was that Relaydesk "answers strictly from the knowledge base with citations and never invents; several competitors are more permissive." Two separate propositions.

**Is strict grounding the correct behaviour? Yes, unambiguously, and the evidence has hardened since 2024.**

- *Moffatt v. Air Canada*: the BC tribunal held Air Canada liable for a chatbot's fabricated bereavement-fare policy and rejected the argument that the chatbot was a separate entity — the company was responsible for all information on its website, chatbot included ([McCarthy Tétrault](https://www.mccarthy.ca/en/insights/blogs/techlex/moffatt-v-air-canada-misrepresentation-ai-chatbot), [ABA](https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-february/bc-tribunal-confirms-companies-remain-liable-information-provided-ai-chatbot/)). The standard of care is "reasonable care to ensure their representations are accurate."
- *Cursor / "Sam", April 2025*: Anysphere's support bot invented a single-device subscription policy that did not exist. Users cancelled subscriptions before the company could intervene; a co-founder had to state publicly "we have no such policy" ([AI Incident Database #1039](https://incidentdatabase.ai/cite/1039/), [WinBuzzer](https://winbuzzer.com/2025/04/22/cursor-ais-support-bot-hallucinates-policy-sparking-user-backlash-and-company-apology-xcxwbn/)). Note the buyer profile: a startup, selling to developers, destroyed by its own support bot in roughly three hours. That is precisely Relaydesk's customer.
- EU AI Act Article 50 has applied since 2 August 2026, with fines up to €15M or 3% of worldwide turnover, and requires disclosure perceivable in the interaction itself ([artificialintelligenceact.eu](https://artificialintelligenceact.eu/transparency-rules-article-50/)).

For a small startup that cannot absorb a public trust failure, strict grounding is the right default and should stay the default.

**Is it differentiating? No — and this is the part that contradicts the current bet.**

The framing "several competitors are more permissive" does not survive contact with the market. Grounding and citations have become the *default claim* of every serious vendor, not the exception:

- Zendesk documents an admin setting to **display sources** on generative replies.
- Fin Voice 2 now "shows the knowledge sources, guidance, and instructions it used on each call" ([fin.ai/updates](https://fin.ai/updates)).
- Sierra markets guardrails and objectives as core platform primitives ([sierra.ai/platform](https://sierra.ai/platform)).
- **Free, AGPL Libredesk ships "an AI assistant grounded in your knowledge base"** ([libredesk.io](https://libredesk.io/)).

So the bet is correct and worth keeping, but it is **hygiene, not moat**. Building marketing or roadmap around "we don't hallucinate" in late 2026 is building around a claim every competitor also makes, including a free one.

**Where the bet is actively wrong: conflating "never invents" with "only ever quotes documents."**

These are different commitments, and the market has separated them while Relaydesk has not. Look at what the leaders ground *on*:

- Intercom's own Fin AI Engine page — a primary source — describes retrieval across **Content, Data, and Integrations & actions**, not content alone, and describes a "clarify and disambiguate" path when certainty thresholds are not met ([Fin AI Engine](https://www.intercom.com/help/en/articles/9929230-the-fin-ai-engine)). *Third-party summaries that say Fin "answers only from your help centre" are an oversimplification of Intercom's own documentation.*
- Lorikeet's entire pitch is the distinction: FAQ bots "know the articles" but not the answers; real resolution means executing SOPs against live systems ([lorikeetcx.ai](https://www.lorikeetcx.ai/)).
- Decagon's AOPs and Kustomer's Procedures add **deterministic** behaviour that is neither a hallucination nor a document quote.
- The benchmark literature is blunt: an agent that is grounded but "cannot take backend actions" sits in the 10–30% resolution band, while action-taking agents reach far higher ([digitalapplied](https://www.digitalapplied.com/blog/ai-support-deflection-resolution-layer-2026-playbook), [Lorikeet](https://www.lorikeetcx.ai/articles/resolution-rate-ai-customer-support-benchmarks-2026)).

**So the plain verdict: keep "never invents," drop "only answers from articles."** An agent constrained to prose in a knowledge base will be correct and unhelpful — it can tell a customer the refund *policy* but not whether *their* refund was issued. That is not a grounding property; it is a missing capability. Extending grounding to live, authenticated, audited tool results (opportunity 4) *preserves* the safety property — every assertion still traces to a verifiable source — while removing the ceiling. Constrained deterministic procedures do the same. The bet should be re-stated as **"every claim is traceable to a source, and sources include systems, not just documents."**

### Three smaller contradictions

**"AI built in rather than bolted on" is now a crowded claim, and the product's actual differentiator is elsewhere.** Every vendor says this. What Relaydesk has that is genuinely rare in the small-team tier is **per-workspace model config with token budgets and an audit trail** — cost governance and model sovereignty. The nearest comparables are Zammad's free LLM choice with Ollama and Plain's BYOA, the latter gated to custom-priced Frontier. Meanwhile Chatwoot is metering Captain AI at $20/1,000 credits and Help Scout's headline AI-buying feature is a **spend cap**. The market has started buying cost predictability. Relaydesk already ships it and appears not to be leading with it. That is a positioning error, not a product one.

**The "no learning curve" positioning is under-defended against a specific threat, and it isn't Zendesk.** Libredesk is AGPL, self-hosted, a single binary, has KB-grounded AI, an agent copilot, CSAT and SLAs, and charges nothing for anything. Relaydesk's advantages over it are real but narrow: model governance, server-resolved citations, token budgets, and the command palette. That is a 12–24 month lead at best, against a project with no revenue pressure and therefore no reason to stop. It deserves to be tracked as *the* competitor, not Zendesk.

**Refusing Slack is right; refusing *all* Slack is probably wrong.** §8 argues against Slack-as-a-channel and I stand by it. But note that Front — a platform with far more to lose — shipped Slack Connect support with threading and user attribution. The cheap, correct version for Relaydesk is outbound only: notify a Slack channel on escalation, new conversation, or @mention, with a deep link back. Hours of work, removes the most common objection, and commits to nothing.

---

## Appendix: verification status

**Verified against vendor primary sources:** Fin pricing ($0.99/outcome, $9.99/qualification, 50/mo minimum); Zendesk plan prices and outcome-pricing language; Help Scout plan prices and $0.75/resolution AI Answers with spend cap; Chatwoot cloud and self-hosted prices, Captain credit allowances and $20/1,000 overage; Chatwoot LICENSE and the `enterprise/` carve-out; Plain pricing tiers and BYOA placement; Sierra platform claims; Decagon product claims and its own pricing blog; Lorikeet positioning; Pylon channel list and agent types; Front's shipped-feature list; Libredesk licence, features and "no paid tiers" FAQ; Zammad 7.0 AI + BYO-LLM/Ollama; FreeScout module licensing; Intercom Fin AI Engine retrieval scope; Intercom identity-verification spoofing language; Intercom Fin MCP server; EU AI Act Article 50 timing and requirements; Moffatt v. Air Canada; Cursor "Sam" incident; Zendesk/Forethought acquisition and close date.

**Third-party only — treat as directional:** Sierra ~$1.50/resolution and total-contract estimates; Decagon per-resolution figures and Vendr contract medians; Forethought ~$0.90/resolution; Gorgias per-resolution price and the double-billing claim; Freshdesk 2026 price rise and Freddy session pricing; Unthread and Thena prices (the Thena figures are published by its competitor Unthread); Kustomer AI for Customers 2.0; Gladly rebrand; Parloa funding; all deflection/resolution benchmark percentages; the 11.3% vs 8.7% re-contact figure; CSAT response-rate collapse statistics; the "40% less reliable" inferred-sentiment claim; MCP adoption survey percentages; Zammad current version number; Frappe Helpdesk and Tiledesk feature claims.

**Could not verify:** Helpy's current maintenance status; the original Moveworks CEO quote on declining outcome pricing; Pylon's pricing (demo-gated, not published anywhere I could reach).
