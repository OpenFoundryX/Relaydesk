import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { getPublicKb } from "@/lib/api/public";

export const metadata: Metadata = { title: "Knowledge Base" };

/**
 * The hub: every published external category, with its published articles.
 * Categories with no published articles never reach here -- the API omits
 * them from the index -- so there is nothing empty to hide client-side.
 *
 * No tree on this page. `PortalKbSidebar` lists every category and every
 * article, which is exactly what this page's body already is -- mounting
 * both put each of these links on screen twice, side by side, and pushed
 * the body into the right third of the shell. The tree earns its place on
 * an article page, where the body is prose and navigation has to come from
 * somewhere; here it was the page repeated back to itself.
 *
 * The search box that used to sit at the top of this page now lives in the
 * portal's shared header, where every portal page gets it.
 */
export default async function HelpIndexPage() {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();

  const categories = await getPublicKb(slug);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
        Knowledge Base
      </h1>
      <p className="mt-1.5 text-[14px] text-ink-500">
        Browse answers by topic, or search from the bar above.
      </p>

      {categories.length === 0 ? (
        <p className="mt-10 text-[13px] text-ink-500">
          There are no help articles yet.
        </p>
      ) : (
        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {categories.map((category) => (
            <section
              key={category.id}
              className="rounded-lg border border-ink-200 p-5 transition-colors hover:border-ink-300"
            >
              <h2 className="text-[15px] font-semibold tracking-tight text-ink-900">
                <Link href={`/help/${category.slug}`} className="hover:underline">
                  {category.name}
                </Link>
              </h2>
              <p className="mt-0.5 text-[12px] text-ink-400">
                {category.articles.length}{" "}
                {category.articles.length === 1 ? "article" : "articles"}
              </p>

              <ul className="mt-4 space-y-1 border-t border-ink-200 pt-3">
                {category.articles.map((article) => (
                  <li key={article.id}>
                    {/* The whole row is the target, not just the title -- a
                        one-line link in a list this dense is a small thing
                        to hit. */}
                    <Link
                      href={`/help/${category.slug}/${article.slug}`}
                      className="group -mx-2 block rounded-md px-2 py-1.5 transition-colors hover:bg-ink-50"
                    >
                      <span className="block text-[14px] font-medium text-accent-950 group-hover:underline">
                        {article.title}
                      </span>
                      <span className="mt-0.5 block text-[13px] leading-relaxed text-ink-500">
                        {article.excerpt}
                      </span>
                    </Link>
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
