import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { PortalKbSidebar } from "@/components/portal/kb-sidebar";
import { helpTree } from "@/components/portal/kb-tree";
import { getPublicKb } from "@/lib/api/public";

export const metadata: Metadata = { title: "Knowledge Base" };

/**
 * The hub: every published external category, with its published articles.
 * Categories with no published articles never reach here -- the API omits
 * them from the index -- so there is nothing empty to hide client-side.
 *
 * The search box that used to sit at the top of this page now lives in the
 * portal's shared header, where every portal page gets it.
 */
export default async function HelpIndexPage() {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();

  const categories = await getPublicKb(slug);

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      {/*
       * The portal nav in the shared layout already reads "Knowledge Base"
       * and is highlighted as the active section here, so a second, visible
       * heading directly beneath it would just be the same words stacked
       * twice. Kept as an sr-only h1 rather than dropped outright -- the nav
       * link isn't a heading, so screen-reader users still need one
       * page-level heading to land on.
       */}
      <h1 className="sr-only">Knowledge Base</h1>

      {categories.length === 0 ? (
        <p className="text-[13px] text-ink-500">There are no help articles yet.</p>
      ) : (
        <div className="flex flex-col gap-10 md:flex-row md:gap-12">
          {/* The tree is built on the server from the index this page has
              already read; the sidebar only owns the collapse state. */}
          <PortalKbSidebar
            categories={helpTree(categories)}
            className="w-full shrink-0 md:w-56"
          />

          <div className="min-w-0 flex-1 space-y-8">
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
        </div>
      )}
    </main>
  );
}
