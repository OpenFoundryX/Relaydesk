import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { searchPublicKb } from "@/lib/api/public";

export const metadata: Metadata = { title: "Search the knowledge base" };

type SearchParams = Promise<{ q?: string }>;

export default async function HelpSearchPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();

  const { q } = await searchParams;
  const query = (q ?? "").trim();

  // The box itself is in the portal's hero now -- present on every portal
  // page, prefilled from this same `?q=`. This page renders results only.
  if (!query) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Search</h1>
        <p className="mt-6 text-[13px] text-ink-500">
          Enter a search term to look through the knowledge base.
        </p>
      </main>
    );
  }

  // Each result carries its own path. It used to be joined against the
  // whole index here to recover one, which a nested knowledge base makes
  // impossible from a slug alone.
  const results = await searchPublicKb(slug, query);

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Search</h1>

      {results.length === 0 ? (
        <p className="mt-6 text-[13px] text-ink-500">
          No articles matched “{query}”.
        </p>
      ) : (
        <p className="mt-1.5 text-[14px] text-ink-500">
          {results.length} {results.length === 1 ? "result" : "results"} for “{query}”
        </p>
      )}

      {results.length > 0 && (
        <ul className="mt-8 grid gap-3">
          {results.map((article) => (
            <li key={article.id}>
              <Link
                href={`/help/${article.path}`}
                className="group block rounded-xl border border-ink-200 p-5 transition-colors hover:border-ink-300 hover:bg-ink-50"
              >
                <span className="block text-[14px] font-medium text-accent-950 group-hover:underline">
                  {article.title}
                </span>
                <span className="mt-1 block text-[13px] leading-relaxed text-ink-500">
                  {article.excerpt}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
