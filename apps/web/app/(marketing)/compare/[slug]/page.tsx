import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, Check } from "lucide-react";

import { BrandIcon } from "@/components/marketing/brand-icons";
import { Button } from "@/components/ui/button";
import { competitors, getCompetitor } from "@/lib/marketing/compare";

type Params = Promise<{ slug: string }>;

export function generateStaticParams() {
  return competitors.map((competitor) => ({ slug: competitor.slug }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const competitor = getCompetitor((await params).slug);
  if (!competitor) return {};
  return {
    title: `Relaydesk vs ${competitor.name}`,
    description: `Why support teams move from ${competitor.name} to Relaydesk, and how to migrate.`,
  };
}

const relaydeskFacts = [
  "Open source under AGPL-3.0, self-hostable with Docker Compose",
  "One inbox for email, Discord, a hosted portal, and an API",
  "AI triage written in plain language, applied on arrival",
  "An agent that calls your webhooks, MCP servers, and databases",
  "Priced on ticket volume, with a free 14-day trial",
  "Import from your existing help desk during setup",
];

export default async function ComparePage({ params }: { params: Params }) {
  const competitor = getCompetitor((await params).slug);
  if (!competitor) notFound();

  return (
    <div className="mx-auto max-w-6xl px-6 py-16 lg:py-24">
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-accent-800">Compare</p>
        <h1 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-ink-950 sm:text-5xl">
          Relaydesk vs {competitor.name}
        </h1>
        <p className="mt-4 text-balance text-[15px] leading-relaxed text-ink-600">
          {competitor.name} is a solid choice for {competitor.audience}. Teams
          that move to Relaydesk usually want one of three things.
        </p>
      </div>

      <div className="mt-14 grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-ink-200 bg-white p-8">
          <h2 className="text-[15px] font-semibold text-ink-900">
            Why teams leave {competitor.name} for Relaydesk
          </h2>
          <ol className="mt-5 space-y-4">
            {competitor.reasons.map((reason, index) => (
              <li key={reason} className="flex gap-3 text-[14px] leading-relaxed text-ink-700">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-ink-900 text-[11px] font-semibold text-accent-500">
                  {index + 1}
                </span>
                {reason}
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded-xl border border-ink-200 bg-ink-50 p-8">
          <h2 className="text-[15px] font-semibold text-ink-900">What you get with Relaydesk</h2>
          <ul className="mt-5 space-y-3">
            {relaydeskFacts.map((fact) => (
              <li key={fact} className="flex items-start gap-2 text-[14px] text-ink-700">
                <Check className="mt-1 size-4 shrink-0 text-accent-700" aria-hidden />
                {fact}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-14 rounded-xl border border-ink-200 bg-white p-8 text-center sm:p-12">
        <h2 className="text-2xl font-semibold tracking-tight text-ink-950">
          Bring your {competitor.name} tickets with you.
        </h2>
        <p className="mx-auto mt-3 max-w-lg text-[15px] text-ink-600">
          We import your existing conversations and articles during setup, so
          your history and your customers&apos; context come along.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button asChild variant="primary" size="lg">
            <Link href="/contact">
              Try for free
              <ArrowRight />
            </Link>
          </Button>
          <Button asChild variant="secondary" size="lg">
            <Link href="https://github.com/openfoundry/relaydesk">
              <BrandIcon brand="github" mono />
              Self-host instead
            </Link>
          </Button>
        </div>
      </div>

      <p className="mt-10 text-center text-[13px] text-ink-500">
        Also compare:{" "}
        {competitors
          .filter((other) => other.slug !== competitor.slug)
          .map((other, index, list) => (
            <span key={other.slug}>
              <Link href={`/compare/${other.slug}`} className="font-medium text-ink-900 underline underline-offset-4">
                {other.name}
              </Link>
              {index < list.length - 1 ? ", " : ""}
            </span>
          ))}
      </p>
    </div>
  );
}
