import type { Metadata } from "next";

import {
  ChannelTable,
  CodeArtifact,
  RingCard,
  StatCard,
} from "@/components/marketing/artifacts";
import { AnswerSequence } from "@/components/marketing/answer-sequence";
import { InboxPreview } from "@/components/marketing/inbox-preview";
import { Marquee, type MarqueeItem } from "@/components/marketing/marquee";
import { PillLink } from "@/components/marketing/pill";
import { Pricing } from "@/components/marketing/pricing";
import { WidgetPreview } from "@/components/marketing/widget-preview";
import { getPlans, triageDefaults } from "@/lib/mock/settings";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: {
    absolute: "Relaydesk · Support that answers from your own help articles",
  },
  description:
    "Gmail quits at about forty tickets a week. Relaydesk answers the repeat questions out of your published articles, cites the one it used, and turns everything else into a ticket with the conversation attached. Forward one address, paste one script tag.",
};

/* -------------------------------------------------------------------------- */
/*  Content                                                                    */
/* -------------------------------------------------------------------------- */

const theFour = [
  "How much is it, and what happens to my bill if I add two people?",
  "I got charged twice.",
  "Your thing stopped talking to my other thing.",
  "How do I do the one feature nobody can find?",
];

/**
 * Each step owns a tint and the ink that belongs with it. Paired here rather
 * than derived from the index so a reordering cannot separate the two.
 */
const setupSteps = [
  {
    tint: "bg-blush-peach",
    ink: "text-sienna-brown",
    action: "Forward support@yourdomain to the address we give you.",
    detail:
      "No DNS records and no IMAP password. Relaydesk stores no mailbox credentials at all, which is also why a stolen copy of the database gets an attacker nowhere near your mail.",
  },
  {
    tint: "bg-mist-blue",
    ink: "text-navy-ink",
    action: "Paste one script tag above </body>.",
    detail:
      "That is the widget. It reads your published articles and nothing else. Restrict it to your own domains from the settings page.",
  },
  {
    tint: "bg-sage-green",
    ink: "text-forest-ink",
    action: "Write four articles.",
    detail:
      "Yes, those four. This is the part everyone skips and it is the only part that matters, because the answers come out of these and nowhere else.",
  },
  {
    tint: "bg-lilac-haze",
    ink: "text-plum-ink",
    action: "Connect Discord, the API, or neither.",
    detail:
      "Discord threads and POSTs to the tickets API land in the same queue as the email. Most people turn this on in month two.",
  },
];

const connectors: MarqueeItem[] = [
  { label: "Stripe", brand: "stripe" },
  { label: "Supabase", brand: "supabase" },
  { label: "Postgres", brand: "postgresql" },
  { label: "MongoDB", brand: "mongodb" },
  { label: "RevenueCat", brand: "revenuecat" },
  { label: "Paddle", brand: "paddle" },
  { label: "Shopify", brand: "shopify" },
  { label: "Slack", brand: "slack" },
  { label: "GitHub", brand: "github" },
  { label: "Linear", brand: "linear" },
  { label: "Jira", brand: "jira" },
  { label: "Convex", brand: "convex" },
];

/** Facts about self-hosting, set big enough to read as a graphic. */
const selfHostStats = [
  {
    value: "AGPL-3.0",
    label: "Licence, top to bottom",
    tint: "bg-sage-green",
    ink: "text-forest-ink",
  },
  {
    value: "1",
    label: "Compose file to stand it up",
    tint: "bg-mist-blue",
    ink: "text-navy-ink",
  },
  {
    value: "0",
    label: "Mailbox credentials in the database",
    tint: "bg-lilac-haze",
    ink: "text-plum-ink",
  },
];

/** The tool registry, as the agent section's artifact. */
const registeredTools = [
  { name: "lookup_subscription", kind: "webhook" },
  { name: "refund_order", kind: "webhook" },
  { name: "search_orders", kind: "mcp" },
  { name: "cancel_plan", kind: "webhook" },
];

const outcomes = [
  {
    name: "answered",
    note: "cited an article and finished",
    dot: "bg-forest-ink",
  },
  {
    name: "escalated",
    note: "became a ticket, transcript attached",
    dot: "bg-navy-ink",
  },
  {
    name: "refused",
    note: "nothing matched, so it did not guess",
    dot: "bg-sienna-brown",
  },
  {
    name: "degraded",
    note: "provider failed, visitor saw the form",
    dot: "bg-plum-ink",
  },
];

/* -------------------------------------------------------------------------- */
/*  Page                                                                       */
/* -------------------------------------------------------------------------- */

export default async function MarketingPage() {
  const plans = await getPlans();

  return (
    <>
      {/* ================================================================ */}
      {/* HERO — centred display, artifacts floating around it              */}
      {/* ================================================================ */}
      <div className="relative isolate overflow-hidden bg-paper-white">
        {/* The wash spans the hero and the strip beneath it, then stops. */}
        <div
          className="aurora pointer-events-none absolute inset-x-0 top-0 -z-10 h-[1240px]"
          aria-hidden
        />
        <section className="mx-auto max-w-[1200px] px-6 pb-0 pt-24 lg:px-10 lg:pt-28">
          {/* Above the fold, so this runs on load rather than on scroll. The
            delays walk down the block in the order it reads. */}
          <div className="mx-auto max-w-4xl text-center">
            <Display className="animate-fade-in-y">
              Gmail <em className="italic">quits</em> at forty tickets a week
            </Display>
            <p
              className="mx-auto mt-7 max-w-2xl animate-fade-in-y text-body text-slate-gray"
              style={{ animationDelay: "120ms" }}
            >
              You know the week it happens. Two people reply to the same
              customer. A three-day-old email turns up under a thread about
              lunch.
            </p>
            <div
              className="mt-9 flex animate-fade-in-y flex-col items-center justify-center gap-3 sm:flex-row"
              style={{ animationDelay: "220ms" }}
            >
              <PillLink href="/contact" variant="filled">
                Get started
              </PillLink>
              <PillLink href="/contact" variant="ghost">
                Book a demo
              </PillLink>
            </div>
            <p
              className="mt-6 animate-fade-in-y text-caption text-smoke-gray"
              style={{ animationDelay: "300ms" }}
            >
              Forward one address. Paste one script tag. About ten minutes.
            </p>
          </div>

          {/* The collage: three cropped product fragments at varied offsets. */}
          <div className="mt-12 grid items-start gap-6 lg:mt-14 lg:grid-cols-12 lg:gap-5">
            <div className="hero-piece hero-piece-l lg:col-span-3 lg:-ml-[150px] lg:mt-16 xl:-ml-[190px]">
              <div
                className="animate-fade-in-y space-y-5"
                style={{ animationDelay: "520ms" }}
              >
                <ChannelTable />
                <RingCard
                  label="Answered without you"
                  value="38%"
                  percent={38}
                  className="hidden lg:flex"
                />
              </div>
            </div>
            <div className="hero-piece hero-piece-c lg:col-span-5 lg:-mt-4">
              <WidgetPreview
                className="animate-fade-in-y"
                style={{ animationDelay: "400ms" }}
              />
            </div>
            <div className="hero-piece hero-piece-r lg:col-span-4 lg:-mr-[150px] lg:mt-10 xl:-mr-[190px]">
              <div
                className="animate-fade-in-y space-y-5"
                style={{ animationDelay: "620ms" }}
              >
                <StatCard
                  label="Median first response"
                  value="4m 20s"
                  delta="Down from 11m 05s"
                  trend="down"
                />
                <StatCard
                  label="Open backlog"
                  value="23"
                  delta="Down from 41 last month"
                  trend="down"
                  className="hidden lg:block"
                />
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================== */}
        {/* MARQUEE — the trust strip, scrolling                            */}
        {/* ============================================================== */}
        <section className="mx-auto max-w-[1200px] px-6 pb-14 pt-8 lg:px-10">
          <p className="text-center text-[15px] text-slate-gray">
            The agent reaches into the systems you already run
          </p>
          <Marquee items={connectors} className="mt-6" />
        </section>
      </div>

      {/* ================================================================ */}
      {/* THE PROBLEM                                                       */}
      {/* ================================================================ */}
      <Section tone="fog">
        <div className="grid gap-12 lg:grid-cols-12 lg:gap-10">
          <div className="lg:col-span-5">
            <Tag>The problem</Tag>
            <Heading className="mt-5">It is the same four questions</Heading>
            <p className="mt-6 max-w-md text-body text-slate-gray">
              Not a figure of speech. Open your sent folder and read the last
              fifty replies. It will be some version of these four, and you have
              already answered all of them this month.
            </p>
          </div>

          <ol className="q-list lg:col-start-7 lg:col-end-13">
            {theFour.map((question, index) => (
              <li
                key={question}
                className={cn(
                  "q-item flex gap-6 rounded-input px-5 py-5",
                  `q-item-${index + 1}`,
                )}
              >
                <span className="tabular pt-0.5 text-caption text-ash-gray">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="text-body-lg font-w430 text-ink-black">
                  {question}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </Section>

      {/* ================================================================ */}
      {/* THE ONE PEACH CARD — the editorial callout                        */}
      {/* ================================================================ */}
      <Section tone="paper">
        <div className="rounded-card bg-blush-peach px-8 py-12 text-sienna-brown sm:px-12 lg:px-16 lg:py-16">
          <div className="grid gap-10 lg:grid-cols-12 lg:gap-12">
            <h2 className="font-display text-[34px] font-normal leading-[1.2] tracking-[-0.5px] text-sienna-brown lg:col-span-6 lg:text-heading">
              Every AI support tool will offer to fix this
            </h2>
            <div className="space-y-5 lg:col-start-8 lg:col-end-13">
              <p className="text-[18px] font-w430 leading-[1.5] text-sienna-brown">
                Most of them answer out of a model&rsquo;s memory of the
                internet. That is how you end up with a bot cheerfully inventing
                a 30-day refund window you have never offered, to a customer who
                now has it in writing.
              </p>
              <p className="text-[18px] font-w480 leading-[1.5] text-sienna-brown">
                The demo is always great. The first real week is the tell.
              </p>
            </div>
          </div>
        </div>
      </Section>

      {/* ================================================================ */}
      {/* SCROLL-LINKED SEQUENCE — how one answer happens                  */}
      {/* ================================================================ */}
      <Section tone="fog" id="answers">
        <div className="max-w-2xl">
          <Tag>What we did instead</Tag>
          <Heading className="mt-5">
            It can only read what you published
          </Heading>
          <p className="mt-6 text-body text-slate-gray">
            Retrieval runs before the model does, and that order is the whole
            product. Scroll through one answer.
          </p>
        </div>

        <div className="mt-12 xl:-mx-12">
          <AnswerSequence />
        </div>

        <p className="mt-12 max-w-2xl text-body text-slate-gray">
          Two more, neither of which you have to switch on. Addresses and card
          numbers a customer pastes in a panic are stripped before the message
          reaches a provider. And every workspace has a daily token ceiling,
          with an hourly one per embed key, because the widget is an anonymous
          endpoint and anyone who views source on your site is holding the key
          that reaches it.
        </p>
      </Section>

      {/* THE AGENT                                                         */}
      {/* ================================================================ */}
      <Section tone="paper" id="agent">
        <div className="grid gap-14 lg:grid-cols-12 lg:gap-12">
          <Transcript className="lg:col-span-6" />
          <div className="lg:col-start-8 lg:col-end-13">
            <Tag>When an answer is not enough</Tag>
            <Heading size="sm" className="mt-5">
              Some tickets need something done
            </Heading>
            <p className="mt-6 text-body text-slate-gray">
              An article cannot refund anybody. Give Relaydesk a webhook with
              typed parameters, or point it at an MCP server you already run,
              and it looks up the subscription, issues the refund, and says so
              on the thread. Every call it makes is written to the conversation
              where a human can read it and disagree.
            </p>

            <div className="mt-8 rounded-card bg-mist-gray p-6">
              <p className="text-[14px] text-ash-gray">Settings · Tools</p>
              <ul className="mt-3">
                {registeredTools.map((tool) => (
                  <li
                    key={tool.name}
                    className="flex items-center gap-3 border-t border-[#e3e3e5] py-2.5"
                  >
                    <span className="flex-1 truncate font-mono text-[13px] text-ink-black">
                      {tool.name}
                    </span>
                    <span className="shrink-0 rounded-full bg-paper-white px-2.5 py-0.5 text-[12px] text-slate-gray">
                      {tool.kind}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </Section>

      {/* ================================================================ */}
      {/* SETUP                                                             */}
      {/* ================================================================ */}
      <Section tone="fog">
        <div className="max-w-2xl">
          <Tag>Setup</Tag>
          <Heading className="mt-5">
            In the order you will actually do it
          </Heading>
        </div>

        <ol className="mt-10 grid gap-5 md:grid-cols-2">
          {setupSteps.map((step, index) => (
            <li
              key={step.action}
              className={cn(
                "flex flex-col rounded-card p-8",
                step.tint,
                step.ink,
              )}
            >
              <span className="tabular font-display text-[64px] font-normal leading-[0.9] opacity-40">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3 className="mt-6 text-subheading font-w450 leading-[1.3]">
                {step.action}
              </h3>
              <p className="mt-3 text-caption opacity-80">{step.detail}</p>
            </li>
          ))}
        </ol>
      </Section>

      {/* ================================================================ */}
      {/* THE INBOX                                                         */}
      {/* ================================================================ */}
      <Section tone="paper" id="inbox">
        <div className="grid gap-10 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <Tag>The part that is not AI</Tag>
            <Heading className="mt-5">Everything lands in one queue</Heading>
          </div>
          <p className="text-body text-slate-gray lg:col-start-7 lg:col-end-12">
            A Discord thread, a forwarded email, a widget escalation and a POST
            to the tickets API all produce the same object: same statuses, same
            priorities, same labels, same assignment, same saved views. Turn
            every automation off and what is left is still a help desk you would
            use. Triage rules are written in plain language, not a builder with
            eleven dropdowns, and you can edit one and re-run it across the open
            queue.
          </p>
        </div>

        <InboxPreview className="mt-10" />

        <div className="mt-6 rounded-card bg-mist-gray px-6 py-5">
          <p className="text-[14px] text-ash-gray">
            Settings · Triage · priority
          </p>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap font-mono text-[13.5px] leading-relaxed text-ink-black">
            {triageDefaults.priority
              .split(/(@[A-Za-z]+)/g)
              .map((part, index) =>
                part.startsWith("@") ? (
                  <span key={index} className="font-w480">
                    {part}
                  </span>
                ) : (
                  <span key={index}>{part}</span>
                ),
              )}
          </pre>
        </div>
      </Section>

      {/* ================================================================ */}
      {/* MEASUREMENT                                                       */}
      {/* ================================================================ */}
      <Section tone="fog" id="analytics">
        <div className="grid gap-14 lg:grid-cols-12 lg:gap-12">
          <div className="lg:col-span-6">
            <Tag>Check our homework</Tag>
            <Heading className="mt-5">One row per answer attempt</Heading>
            <div className="mt-8 max-w-xl space-y-5 text-body text-slate-gray">
              <p>
                Not one row per successful answer. Per attempt, including the
                ones that refused, the ones that fell back to the ticket form
                when a provider timed out, and the ones that ended because the
                visitor closed the tab mid-sentence. Those get written before
                the model is called, so a visitor hanging up cannot quietly
                delete the evidence.
              </p>
              <p>
                Everyone publishes a resolution rate. Almost nobody hands you
                the table it came out of.
              </p>
            </div>

            <dl className="mt-10">
              {outcomes.map((outcome) => (
                <div
                  key={outcome.name}
                  className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-hairline py-3 first:border-t"
                >
                  <dt className="flex w-28 shrink-0 items-center gap-2.5 font-mono text-[13.5px] text-ink-black">
                    <span
                      className={cn(
                        "size-2 shrink-0 rounded-full",
                        outcome.dot,
                      )}
                      aria-hidden
                    />
                    {outcome.name}
                  </dt>
                  <dd className="text-caption text-slate-gray">
                    {outcome.note}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="space-y-5 lg:col-start-8 lg:col-end-13 lg:mt-8">
            <StatCard
              label="Answered without a human on the thread"
              value="38%"
              delta="Up 9 points since the articles went live"
              trend="up"
            />
            <RingCard label="Open backlog" value="23 of 41" percent={56} />
            <StatCard
              label="Median first response"
              value="4m 20s"
              delta="Down from 11m 05s"
              trend="down"
            />
            <p className="text-[13px] text-smoke-gray">
              Figures from one demo workspace, not an average.
            </p>
          </div>
        </div>
      </Section>

      {/* ================================================================ */}
      {/* SELF-HOSTING                                                      */}
      {/* ================================================================ */}
      <Section tone="paper" id="open-source">
        <div className="grid gap-14 lg:grid-cols-12 lg:gap-12">
          <div className="lg:col-span-5">
            <Tag>Or do not pay us at all</Tag>
            <Heading className="mt-5">Run the whole thing yourself</Heading>
            <p className="mt-7 text-body text-slate-gray">
              AGPL-3.0, top to bottom. A Next.js console, a FastAPI backend and
              Postgres come up from one Compose file. Bring your own model keys
              and nothing leaves your network. The hosted version runs this same
              code, so moving between them is a database dump, not a migration
              project.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <PillLink
                href="https://github.com/openfoundry/relaydesk"
                variant="filled"
              >
                Star on GitHub
              </PillLink>
              <PillLink
                href="https://github.com/openfoundry/relaydesk/blob/main/CONTRIBUTING.md"
                variant="ghost"
              >
                Contributing guide
              </PillLink>
            </div>
          </div>

          <CodeArtifact className="self-start lg:col-start-7 lg:col-end-13 lg:mt-6" />
        </div>

        <dl className="mt-12 grid gap-5 sm:grid-cols-3">
          {selfHostStats.map((stat) => (
            <div
              key={stat.label}
              className={cn("rounded-card p-8", stat.tint, stat.ink)}
            >
              <dt className="font-display text-[44px] font-normal leading-none tracking-[-0.66px]">
                {stat.value}
              </dt>
              <dd className="mt-4 text-caption opacity-80">{stat.label}</dd>
            </div>
          ))}
        </dl>
      </Section>

      {/* ================================================================ */}
      {/* PRICING                                                           */}
      {/* ================================================================ */}
      <Section tone="fog" id="pricing">
        <div className="grid gap-8 lg:grid-cols-12">
          <Heading className="lg:col-span-6">
            Priced on tickets, not seats
          </Heading>
          <p className="text-body text-slate-gray lg:col-start-8 lg:col-end-13">
            Adding the person you just hired to the queue is not a budget
            conversation. Every plan includes the widget, the help centre and
            the AI. Running it yourself costs nothing, forever, and we would
            rather you did that than bounced off a paywall.
          </p>
        </div>

        <div className="mt-10">
          <Pricing plans={plans} />
        </div>
      </Section>

      {/* ================================================================ */}
      {/* CTA                                                               */}
      {/* ================================================================ */}
      <Section tone="paper">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="font-display text-[40px] font-normal leading-[1.25] tracking-[-0.8px] text-ink-black sm:text-heading-lg">
            Go write the <em className="italic">four</em> articles
          </h2>
          <p className="mx-auto mt-7 max-w-xl text-body text-slate-gray">
            Forward your support address, paste the script tag, and write up the
            questions you are tired of answering. If it is not pulling its
            weight in a fortnight, export everything and walk away.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <PillLink href="/contact" variant="filled">
              Get started
            </PillLink>
            <PillLink href="/contact" variant="ghost">
              Book a demo
            </PillLink>
          </div>
        </div>
      </Section>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/*  Primitives                                                                 */
/* -------------------------------------------------------------------------- */

/**
 * Sections alternate paper and fog, which in this system is a ~1% step rather
 * than a light/dark band. 80px is the section gap, doubled on wide screens.
 */
function Section({
  id,
  tone,
  className,
  children,
}: {
  id?: string;
  tone: "paper" | "fog";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className={cn(
        // A hairline on every section: at a 1% tone step between paper and
        // fog, the band change alone is not enough to read as an edge.
        "scroll-mt-20 border-t border-hairline",
        tone === "fog" ? "bg-fog-white" : "bg-paper-white",
      )}
    >
      <div
        className={cn(
          "mx-auto max-w-[1200px] px-6 py-12 lg:px-10 lg:py-16",
          className,
        )}
      >
        {children}
      </div>
    </section>
  );
}

/** 90px at the top of the scale, dropping to something a phone can hold. */
function Display({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <h1
      className={cn(
        "font-display text-[44px] font-normal leading-[1.15] tracking-[-1px] text-ink-black sm:text-heading-lg md:text-display md:leading-[1.15]",
        className,
      )}
    >
      {children}
    </h1>
  );
}

function Heading({
  size = "lg",
  className,
  children,
}: {
  size?: "lg" | "sm";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <h2
      className={cn(
        "font-display font-normal text-ink-black",
        size === "lg"
          ? "text-[34px] leading-[1.2] tracking-[-0.5px] sm:text-heading"
          : "text-[28px] leading-[1.2] tracking-[-0.4px] sm:text-[36px]",
        className,
      )}
    >
      {children}
    </h2>
  );
}

/** Typographic category marker. Deliberately ghost-like: no badge, no fill. */
function Tag({ children }: { children: React.ReactNode }) {
  return <p className="text-[14px] font-normal text-ash-gray">{children}</p>;
}

/** The agent transcript, as a flat mist card rather than a floating artifact. */
function Transcript({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-card bg-mist-gray px-6 py-6", className)}>
      <p className="text-[14px] text-ash-gray">
        Refund for duplicate charge · Marcus L.
      </p>

      <p className="mt-5 text-caption text-slate-gray">Marcus L. · 12m</p>
      <p className="mt-1 text-body text-ink-black">
        I was charged twice for order #48213 yesterday. Can you sort it out?
      </p>

      <div className="mt-5 rounded-input bg-paper-white px-4 py-3 font-mono text-[13px] leading-relaxed">
        <p className="text-ink-black">lookup_subscription()</p>
        <p className="text-slate-gray">
          → Growth · renews 14 Sep · 2 charges on 3 Sep
        </p>
        <p className="mt-2 text-ink-black">
          refund_order(order_id: &quot;48213&quot;, amount: 4900)
        </p>
        <p className="text-slate-gray">→ refund re_3Q9x issued</p>
      </div>

      <p className="mt-5 text-caption text-slate-gray">Relaydesk · 11m</p>
      <p className="mt-1 text-body text-ink-black">
        Sorry about that, Marcus. I can see the duplicate charge on order #48213
        and have refunded $49.00 to your card. It should land in 3 to 5 business
        days.
      </p>

      <p className="mt-5 border-t border-[#e3e3e5] pt-4 text-caption text-slate-gray">
        Closed without a human. Sara was notified in Slack.
      </p>
    </div>
  );
}
