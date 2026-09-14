import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

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
  "Answers grounded in your published articles, with citations",
  "AI triage written in plain language, applied on arrival",
  "An agent that calls your webhooks, MCP servers, and databases",
  "Priced on ticket volume, never per seat — free to start",
  "Import from your existing help desk during setup",
];

export default async function ComparePage({ params }: { params: Params }) {
  const competitor = getCompetitor((await params).slug);
  if (!competitor) notFound();

  return (
    <div className="mx-auto max-w-[1200px] px-6 pb-20 pt-28 lg:px-10 lg:pb-24 lg:pt-36">
      <div className="max-w-4xl">
        <p className="text-[14px] font-normal text-ash-gray">Compare</p>
        <h1 className="mt-5 font-display text-[40px] font-normal leading-[1.2] tracking-[-0.8px] text-ink-black sm:text-heading-lg">
          Relaydesk vs {competitor.name}
        </h1>
        <p className="mt-7 max-w-xl text-body text-slate-gray">
          {competitor.name} is a solid choice for {competitor.audience}. Teams
          that move to Relaydesk usually want one of three things.
        </p>
      </div>

      <div className="mt-16 grid gap-5 lg:grid-cols-2">
        <div className="rounded-card bg-mist-gray p-8">
          <h2 className="text-[14px] font-normal text-ash-gray">
            Why teams leave {competitor.name} for Relaydesk
          </h2>
          <ol className="mt-5 space-y-4">
            {competitor.reasons.map((reason, index) => (
              <li key={reason} className="flex gap-3 text-[16px] leading-[1.5] text-ink-black">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-ink-black text-[12px] font-w450 text-paper-white">
                  {index + 1}
                </span>
                {reason}
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded-card bg-mist-gray p-8">
          <h2 className="text-[14px] font-normal text-ash-gray">What you get with Relaydesk</h2>
          <ul className="mt-5">
            {relaydeskFacts.map((fact) => (
              <li key={fact} className="border-t border-[#e3e3e5] py-3 text-[16px] leading-[1.5] text-ink-black">
                
                {fact}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-16 rounded-card bg-blush-peach p-8 text-sienna-brown sm:p-12">
        <h2 className="max-w-[18ch] font-display text-[30px] font-normal leading-[1.2] tracking-[-0.5px] text-sienna-brown sm:text-heading">
          Bring your {competitor.name} tickets with you.
        </h2>
        <p className="mt-6 max-w-lg text-[18px] font-w430 leading-[1.5] text-sienna-brown">
          We import your existing conversations and articles during setup, so
          your history and your customers&apos; context come along.
        </p>
        <div className="mt-9 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/contact"
            className="inline-flex h-11 items-center justify-center rounded-full border border-sienna-brown bg-sienna-brown px-5 text-[16px] font-normal text-blush-peach"
          >
            Try for free
          </Link>
          <Link
            href="https://github.com/openfoundry/relaydesk"
            className="inline-flex h-11 items-center justify-center rounded-full border border-sienna-brown px-5 text-[16px] font-normal text-sienna-brown"
          >
            Self-host instead
          </Link>
        </div>
      </div>

      <p className="mt-10 text-caption text-slate-gray">
        Also compare:{" "}
        {competitors
          .filter((other) => other.slug !== competitor.slug)
          .map((other, index, list) => (
            <span key={other.slug}>
              <Link href={`/compare/${other.slug}`} className="text-ink-black underline-offset-4 hover:underline">
                {other.name}
              </Link>
              {index < list.length - 1 ? ", " : ""}
            </span>
          ))}
      </p>
    </div>
  );
}
