import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getPublicKb, searchPublicKb } from "@/lib/api/public";

export const metadata: Metadata = { title: "Search the help center" };

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

  const form = (
    <form action="/help/search" className="mt-6 flex gap-2">
      <Input
        type="search"
        name="q"
        defaultValue={query}
        placeholder="Search articles…"
        aria-label="Search articles"
      />
      <Button type="submit" variant="secondary">
        Search
      </Button>
    </form>
  );

  if (!query) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
          Search
        </h1>
        {form}
        <p className="mt-10 text-[13px] text-ink-500">
          Enter a search term to look through the help center.
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
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
        Search
      </h1>
      {form}

      {results.length === 0 ? (
        <p className="mt-10 text-[13px] text-ink-500">
          No articles matched “{query}”.
        </p>
      ) : (
        <ul className="mt-10 space-y-4">
          {results.map((article) => (
            <li key={article.id}>
              <Link
                href={linkFor.get(article.id) ?? "/help"}
                className="text-[14px] font-medium text-accent-950 hover:underline"
              >
                {article.title}
              </Link>
              <p className="mt-0.5 text-[13px] leading-relaxed text-ink-500">
                {article.excerpt}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
