import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { getPublicKb, searchPublicKb } from "@/lib/api/public";

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

  // The box itself is in the portal's shared header now -- present on every
  // portal page, prefilled from this same `?q=`. This page renders results
  // only. The endpoint and the parameter are unchanged.
  if (!query) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-12">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
          Search
        </h1>
        <p className="mt-6 text-[13px] text-ink-500">
          Enter a search term to look through the knowledge base.
        </p>
      </main>
    );
  }

  // The search endpoint returns article summaries without a category, so
  // the index is fetched alongside it purely to recover the category slug
  // each result needs for its `/help/{category}/{article}` link. Both
  // apply the same "published, external" predicates, so every search hit
  // is expected to also appear in the index.
  const [results, categories] = await Promise.all([
    searchPublicKb(slug, query),
    getPublicKb(slug),
  ]);

  const linkFor = new Map<string, string>();
  for (const category of categories) {
    for (const article of category.articles) {
      linkFor.set(article.id, `/help/${category.slug}/${article.slug}`);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
        Search
      </h1>

      {results.length === 0 ? (
        <p className="mt-6 text-[13px] text-ink-500">
          No articles matched “{query}”.
        </p>
      ) : (
        <p className="mt-1.5 text-[14px] text-ink-500">
          {results.length} {results.length === 1 ? "result" : "results"} for “
          {query}”
        </p>
      )}

      {results.length > 0 && (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {results.map((article) => (
            <li key={article.id}>
              <Link
                href={linkFor.get(article.id) ?? "/help"}
                className="group block h-full rounded-lg border border-ink-200 p-5 transition-colors hover:border-ink-300 hover:bg-ink-50"
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
