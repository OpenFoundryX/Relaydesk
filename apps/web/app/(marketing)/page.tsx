import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Braces,
  ChartLine,
  ChevronRight,
  Forward,
  Globe,
  Inbox,
  Lock,
  Plug,
  Server,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { BrandIcon, type BrandSlug } from "@/components/marketing/brand-icons";
import { InboxPreview } from "@/components/marketing/inbox-preview";
import { Pricing } from "@/components/marketing/pricing";
import { Button } from "@/components/ui/button";
import { getPlans, triageDefaults } from "@/lib/mock/settings";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: { absolute: "Relaydesk · Open-source AI-native customer support" },
  description:
    "One inbox for email, Discord, your portal and your API. AI triage written in plain language, an agent that resolves tickets with your own tools, and a codebase you can self-host.",
};

type Connector =
  | { label: string; brand: BrandSlug }
  | { label: string; icon: LucideIcon };

const connectors: Connector[] = [
  { label: "Gmail", brand: "gmail" },
  { label: "Email forwarding", icon: Forward },
  { label: "Discord", brand: "discord" },
  { label: "Tickets API", icon: Braces },
  { label: "Stripe", brand: "stripe" },
  { label: "RevenueCat", brand: "revenuecat" },
  { label: "Supabase", brand: "supabase" },
  { label: "PostgreSQL", brand: "postgresql" },
  { label: "MongoDB", brand: "mongodb" },
  { label: "Slack", brand: "slack" },
  { label: "GitHub", brand: "github" },
  { label: "Linear", brand: "linear" },
];

const pillars: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: Inbox,
    title: "One inbox, every channel",
    body: "Email, Discord, your user portal and a tickets API land in the same queue with the same statuses, labels, and saved views.",
  },
  {
    icon: Sparkles,
    title: "Triage you can read",
    body: "Priority and routing rules are written in plain language and applied to every message the moment it lands.",
  },
  {
    icon: Wrench,
    title: "An agent with real tools",
    body: "Give the AI your webhooks, MCP servers and databases. It looks up the order, issues the refund, and closes the thread.",
  },
  {
    icon: Lock,
    title: "Yours to run",
    body: "AGPL-licensed and self-hostable with Docker Compose. Or skip the ops and use the managed cloud.",
  },
];

const portalFeatures = [
  "Branded ticket form on your own subdomain",
  "Public knowledge base with drafts, review and publishing",
  "Internal articles the AI cites when it replies",
  "Templates with customer and ticket variables",
];

const analyticsMetrics = [
  { label: "Resolved without an agent", value: "38%", delta: "+9 pts" },
  { label: "Avg first response time", value: "4m 20s", delta: "−61%" },
  { label: "Open backlog", value: "23", delta: "−44%" },
];

export default async function MarketingPage() {
  const plans = await getPlans();

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[520px] bg-[radial-gradient(60%_60%_at_50%_0%,#F1F9C5_0%,rgba(255,255,255,0)_70%)]"
          aria-hidden
        />
        <div className="mx-auto max-w-6xl px-6 pb-8 pt-20 text-center sm:pt-28">
          <Link
            href="#open-source"
            className="inline-flex items-center gap-2 rounded-full border border-ink-200 bg-white px-3 py-1 text-[12px] font-medium text-ink-600 transition-colors hover:border-ink-300 hover:text-ink-900"
          >
            <span className="size-1.5 rounded-full bg-accent-500" aria-hidden />
            Open source under AGPL-3.0
            <ArrowRight className="size-3" />
          </Link>
          <h1 className="mx-auto mt-6 max-w-3xl text-balance text-4xl font-semibold tracking-tight text-ink-950 sm:text-6xl">
            Customer support that answers before you get there.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-balance text-[17px] leading-relaxed text-ink-600">
            Relaydesk puts every channel in one inbox, triages each message with
            rules you write in plain English, and lets an AI agent resolve the
            routine ones using your own tools. Self-host it, or let us run it.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild variant="primary" size="lg">
              <Link href="/contact">
                Get started
                <ArrowRight />
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="https://github.com/openfoundry/relaydesk">
                <BrandIcon brand="github" mono />
                Self-host on GitHub
              </Link>
            </Button>
          </div>
          <p className="mt-3 text-[12px] text-ink-400">
            We set up your workspace with you. 14 days free, no credit card.
          </p>
        </div>
        <div className="mx-auto max-w-5xl px-6 pb-20">
          <InboxPreview />
        </div>
      </section>

      {/* Works with */}
      <section className="border-y border-ink-200 bg-ink-50">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <p className="text-center text-[12px] font-semibold uppercase tracking-wide text-ink-400">
            Connects to the tools you already run
          </p>
          <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-8 gap-y-4">
            {connectors.map((item) => (
              <li key={item.label} className="flex items-center gap-2 text-[13px] text-ink-600">
                <span className="flex size-7 items-center justify-center rounded-md border border-ink-200 bg-white">
                  {"brand" in item ? (
                    <BrandIcon brand={item.brand} />
                  ) : (
                    <item.icon className="size-4 text-ink-700" aria-hidden />
                  )}
                </span>
                {item.label}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Pillars */}
      <section id="product" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-24">
        <SectionHeading
          eyebrow="Product"
          title="Built for the team that reads every ticket, and the one that would rather not."
          body="Relaydesk is a help desk first and an AI product second. Every automation sits on top of an inbox your agents would happily use on its own."
        />
        <div className="mt-14 grid gap-px overflow-hidden rounded-xl border border-ink-200 bg-ink-200 sm:grid-cols-2 lg:grid-cols-4">
          {pillars.map((pillar) => (
            <div key={pillar.title} className="bg-white p-6">
              <span className="inline-flex size-9 items-center justify-center rounded-lg bg-ink-900 text-accent-500">
                <pillar.icon className="size-4" aria-hidden />
              </span>
              <h3 className="mt-4 text-[15px] font-semibold text-ink-900">{pillar.title}</h3>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-600">{pillar.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Triage */}
      <section id="triage" className="scroll-mt-24 border-t border-ink-200 bg-ink-50">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 lg:grid-cols-2">
          <div>
            <Eyebrow icon={Sparkles}>AI triage</Eyebrow>
            <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-ink-950">
              Routing rules your whole team can read.
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-600">
              No decision trees, no regex. Describe who should get what, in the
              words you would use in a stand-up. Relaydesk applies it to every
              incoming message before anyone opens the inbox, and shows its
              reasoning on the thread.
            </p>
            <ul className="mt-6 space-y-2 text-[13px] text-ink-700">
              <FeatureLine>Sets priority, assignee and labels on arrival</FeatureLine>
              <FeatureLine>Understands your customers: plan, spend, account age</FeatureLine>
              <FeatureLine>Edit the rules and re-run on the open queue</FeatureLine>
            </ul>
          </div>
          <div className="rounded-xl border border-ink-200 bg-white shadow-overlay">
            <div className="flex h-10 items-center border-b border-ink-200 px-4 text-[12px] font-medium text-ink-500">
              Settings · AI triage
            </div>
            <RuleBlock label="Priority" rules={triageDefaults.priority} />
            <RuleBlock label="Assignee" rules={triageDefaults.assignee} last />
          </div>
        </div>
      </section>

      {/* Agent */}
      <section id="agent" className="scroll-mt-24 border-t border-ink-200">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 lg:grid-cols-2">
          <div className="order-2 lg:order-1">
            <div className="rounded-xl border border-ink-200 bg-white shadow-overlay">
              <div className="flex h-10 items-center border-b border-ink-200 px-4 text-[12px] font-medium text-ink-500">
                Refund for duplicate charge · Marcus L.
              </div>
              <div className="space-y-4 p-5 text-[13px]">
                <Bubble who="Marcus L." ago="12m">
                  I was charged twice for order #48213 yesterday. Can you sort it out?
                </Bubble>
                <ToolCall name="lookup_subscription" result="Growth · renews 14 Sep · 2 charges on 3 Sep" />
                <ToolCall name="refund_order" args='{ order_id: "48213", amount: 4900 }' result="Refund re_3Q9x issued" />
                <Bubble who="Relaydesk AI" ago="11m" ai>
                  Sorry about that, Marcus. I can see the duplicate charge on order
                  #48213 and have refunded $49.00 to your card. It should show up in
                  3–5 business days.
                </Bubble>
                <p className="flex items-center gap-2 text-[12px] text-ink-500">
                  <span className="size-1.5 rounded-full bg-positive-600" aria-hidden />
                  Resolved without an agent. Sara was notified in Slack.
                </p>
              </div>
            </div>
          </div>
          <div className="order-1 lg:order-2">
            <Eyebrow icon={Wrench}>AI agent</Eyebrow>
            <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-ink-950">
              An agent that does the work, not just the wording.
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-600">
              Most AI support tools stop at drafting a reply. Relaydesk connects
              the agent to your systems, so it can look up the account, take the
              action, and tell the customer what it did.
            </p>
            <ul className="mt-6 space-y-2 text-[13px] text-ink-700">
              <FeatureLine>Custom webhooks with typed parameters</FeatureLine>
              <FeatureLine>MCP servers, so tools you already built just work</FeatureLine>
              <FeatureLine>Read access to Stripe, Supabase, Postgres, MongoDB and more</FeatureLine>
              <FeatureLine>Every action is logged on the thread for a human to review</FeatureLine>
            </ul>
          </div>
        </div>
      </section>

      {/* Portal + Analytics */}
      <section id="portal" className="scroll-mt-24 border-t border-ink-200 bg-ink-50">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-24 lg:grid-cols-2">
          <Card>
            <Eyebrow icon={Globe}>User portal and knowledge base</Eyebrow>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-ink-950">
              Let customers help themselves first.
            </h2>
            <p className="mt-3 text-[14px] leading-relaxed text-ink-600">
              Deploy a support portal on your own subdomain in a couple of clicks.
              Articles you publish there are the same ones the AI reads before it
              replies.
            </p>
            <ul className="mt-5 space-y-2 text-[13px] text-ink-700">
              {portalFeatures.map((item) => (
                <FeatureLine key={item}>{item}</FeatureLine>
              ))}
            </ul>
            <div className="mt-6 flex items-center gap-2 rounded-md border border-ink-200 bg-ink-50 px-3 py-2 font-mono text-[12px] text-ink-600">
              <BookOpen className="size-3.5 text-ink-400" aria-hidden />
              chronon.relaydesk.app
              <span className="ml-auto rounded-full bg-positive-50 px-2 py-0.5 text-[11px] font-medium text-positive-600">
                Deployed
              </span>
            </div>
          </Card>
          <Card id="analytics">
            <Eyebrow icon={ChartLine}>Analytics</Eyebrow>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-ink-950">
              Know what the AI is handling, and what it is not.
            </h2>
            <p className="mt-3 text-[14px] leading-relaxed text-ink-600">
              Tickets created, responded and resolved, first response time, and
              the share closed without a human on the thread. Filter by assignee
              and period.
            </p>
            <dl className="mt-6 grid gap-3 sm:grid-cols-3">
              {analyticsMetrics.map((metric) => (
                <div key={metric.label} className="rounded-md border border-ink-200 bg-white px-3 py-2.5">
                  <dt className="text-[12px] text-ink-500">{metric.label}</dt>
                  <dd className="tabular mt-0.5 flex items-baseline gap-1.5">
                    <span className="text-lg font-semibold tracking-tight text-ink-900">
                      {metric.value}
                    </span>
                    <span className="text-[11px] font-medium text-accent-800">{metric.delta}</span>
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-[11px] text-ink-400">Illustrative numbers from a demo workspace.</p>
          </Card>
        </div>
      </section>

      {/* Open source */}
      <section id="open-source" className="scroll-mt-24 border-t border-ink-200 bg-ink-950 text-white">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 lg:grid-cols-2">
          <div>
            <Eyebrow icon={Server} dark>Open source</Eyebrow>
            <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-white">
              Your customers&apos; conversations, on your infrastructure.
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-400">
              Relaydesk is licensed under the AGPL-3.0. The whole stack, a Next.js
              console, a FastAPI backend and PostgreSQL, runs from a single Docker
              Compose file. Bring your own model keys and nothing leaves your
              network.
            </p>
            <ul className="mt-6 space-y-2 text-[13px] text-ink-300">
              <FeatureLine dark>Same codebase powers the managed cloud</FeatureLine>
              <FeatureLine dark>Import from your old help desk</FeatureLine>
              <FeatureLine dark>Public roadmap, governance and security policy</FeatureLine>
            </ul>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild variant="accent" size="lg">
                <Link href="https://github.com/openfoundry/relaydesk">
                  <BrandIcon brand="github" mono />
                  Star on GitHub
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                className="border-ink-700 bg-transparent text-white hover:border-ink-600 hover:bg-ink-900"
              >
                <Link href="https://github.com/openfoundry/relaydesk/blob/main/CONTRIBUTING.md">
                  Contributing guide
                </Link>
              </Button>
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-ink-800 bg-ink-900">
            <div className="flex h-10 items-center gap-2 border-b border-ink-800 px-4 text-[12px] text-ink-400">
              <Plug className="size-3.5" aria-hidden />
              Terminal
            </div>
            <pre className="overflow-x-auto p-5 font-mono text-[13px] leading-relaxed text-ink-200">
              <code>{`git clone https://github.com/openfoundry/relaydesk
cd relaydesk
cp .env.example .env
docker compose up --build

# Web    http://localhost:3000
# API    http://localhost:8000`}</code>
            </pre>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="scroll-mt-24 border-t border-ink-200">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <SectionHeading
            eyebrow="Pricing"
            title="Priced on tickets, not on seats you have to ration."
            body="Every plan includes the AI agent, triage and the portal. Self-hosting is free forever."
          />
          <div className="mt-14">
            <Pricing plans={plans} />
          </div>
          <p className="mt-6 text-center text-[13px] text-ink-500">
            Need more volume, or want to run it yourself?{" "}
            <Link href="/contact" className="font-medium text-ink-900 underline underline-offset-4">
              Talk to us
            </Link>
            .
          </p>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-ink-200 bg-ink-50">
        <div className="mx-auto max-w-3xl px-6 py-24 text-center">
          <h2 className="text-balance text-3xl font-semibold tracking-tight text-ink-950 sm:text-4xl">
            Ready to make customer support easier?
          </h2>
          <p className="mt-4 text-[15px] text-ink-600">
            Set up your help desk in 15 minutes. Or book a demo to see it in action.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild variant="primary" size="lg">
              <Link href="/contact">
                Try for free
                <ChevronRight />
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/contact">Book a demo</Link>
            </Button>
          </div>
        </div>
      </section>
    </>
  );
}

function SectionHeading({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-[12px] font-semibold uppercase tracking-wide text-accent-800">{eyebrow}</p>
      <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-ink-950">{title}</h2>
      <p className="mt-4 text-[15px] leading-relaxed text-ink-600">{body}</p>
    </div>
  );
}

function Eyebrow({ icon: Icon, dark, children }: { icon: LucideIcon; dark?: boolean; children: React.ReactNode }) {
  return (
    <p
      className={cn(
        "inline-flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide",
        dark ? "text-accent-400" : "text-accent-800",
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {children}
    </p>
  );
}

function FeatureLine({ dark, children }: { dark?: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span
        className={cn("mt-2 size-1.5 shrink-0 rounded-full", dark ? "bg-accent-400" : "bg-accent-500")}
        aria-hidden
      />
      <span>{children}</span>
    </li>
  );
}

function Card({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <div id={id} className="scroll-mt-24 rounded-xl border border-ink-200 bg-white p-8">
      {children}
    </div>
  );
}

function RuleBlock({ label, rules, last }: { label: string; rules: string; last?: boolean }) {
  return (
    <div className={cn("p-4", !last && "border-b border-ink-200")}>
      <p className="text-[12px] font-medium text-ink-500">{label}</p>
      <pre className="mt-2 whitespace-pre-wrap font-mono text-[12.5px] leading-relaxed text-ink-800">
        {rules.split(/(@[A-Za-z]+)/g).map((part, index) =>
          part.startsWith("@") ? (
            <span key={index} className="rounded bg-accent-100 px-1 text-accent-950">
              {part}
            </span>
          ) : (
            <span key={index}>{part}</span>
          ),
        )}
      </pre>
    </div>
  );
}

function Bubble({ who, ago, ai, children }: { who: string; ago: string; ai?: boolean; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
          ai ? "bg-ink-900 text-accent-500" : "bg-ink-100 text-ink-700",
        )}
      >
        {ai ? <Sparkles className="size-3.5" aria-hidden /> : who.slice(0, 2).toUpperCase()}
      </span>
      <div className="min-w-0">
        <p className="text-[12px] text-ink-500">
          <span className="font-medium text-ink-900">{who}</span> · {ago}
        </p>
        <p className="mt-1 leading-relaxed text-ink-800">{children}</p>
      </div>
    </div>
  );
}

function ToolCall({ name, args, result }: { name: string; args?: string; result: string }) {
  return (
    <div className="ml-10 rounded-md border border-ink-200 bg-ink-50 px-3 py-2 font-mono text-[12px]">
      <p className="text-ink-700">
        <span className="text-accent-800">▸</span> {name}
        {args && <span className="text-ink-500">({args})</span>}
      </p>
      <p className="mt-0.5 text-ink-500">↳ {result}</p>
    </div>
  );
}
