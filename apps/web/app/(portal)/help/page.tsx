import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getPublicKb } from "@/lib/api/public";

export const metadata: Metadata = { title: "Help center" };

/**
 * The hub: every published external category, with its published articles.
 * Categories with no published articles never reach here -- the API omits
 * them from the index -- so there is nothing empty to hide client-side.
 */
export default async function HelpIndexPage() {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();

  const categories = await getPublicKb(slug);

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      {/*
       * The portal nav in the shared layout already reads "Help center" and
       * is highlighted as the active section here, so a second, visible
       * "Help center" heading directly beneath it would just be the same
       * words stacked twice. Kept as an sr-only h1 rather than dropped
       * outright -- the nav link isn't a heading, so screen-reader users
       * still need one page-level heading to land on.
       */}
      <h1 className="sr-only">Help center</h1>

      <form action="/help/search" className="flex gap-2">
        <Input
          type="search"
          name="q"
          placeholder="Search articles…"
          aria-label="Search articles"
        />
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      {categories.length === 0 ? (
        <p className="mt-10 text-[13px] text-ink-500">
          There are no help articles yet.
        </p>
      ) : (
        <div className="mt-10 space-y-8">
          {categories.map((category) => (
            <section key={category.id}>
              <h2 className="text-[15px] font-semibold tracking-tight text-ink-900">
                <Link href={`/help/${category.slug}`} className="hover:underline">
                  {category.name}
                </Link>
              </h2>
              <ul className="mt-3 space-y-3">
                {category.articles.map((article) => (
                  <li key={article.id}>
                    <Link
                      href={`/help/${category.slug}/${article.slug}`}
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
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
