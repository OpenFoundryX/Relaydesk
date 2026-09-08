import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { articleCount } from "@/components/portal/collection-card";
import type { PublicArticleSummary, PublicCollection } from "@/lib/api/public";

function Row({
  href,
  label,
  meta,
}: {
  href: string;
  label: string;
  /** The "7 articles" line under a sub-collection. Articles have none. */
  meta?: string;
}) {
  return (
    <li>
      <Link
        href={href}
        className="group flex items-center gap-3 border-t border-ink-100 px-5 py-3.5 first:border-t-0 hover:bg-ink-50"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-[14px] text-ink-800 group-hover:underline">
            {label}
          </span>
          {meta && <span className="mt-0.5 block text-[12px] text-ink-400">{meta}</span>}
        </span>
        <ChevronRight className="size-4 shrink-0 text-ink-300" aria-hidden />
      </Link>
    </li>
  );
}

/**
 * One card on a collection page: a section heading, then its rows.
 *
 * A row is either an article or a sub-collection, and the two are told
 * apart only by the article count under the second -- which is what the
 * three container levels look like once drawn. Sub-collections come first
 * so a reader meets the broader grouping before the loose articles beside
 * it.
 */
export function SectionCard({
  title,
  href,
  collections,
  articles,
  basePath,
}: {
  title: string;
  /** The section's own page, or null for the unlabelled card of loose articles. */
  href: string | null;
  collections: PublicCollection[];
  articles: PublicArticleSummary[];
  /** Path of the section, for building its sub-collections' hrefs. */
  basePath: string;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-ink-200 bg-white">
      <h2 className="px-5 pb-3.5 pt-4 text-[15px] font-semibold tracking-tight text-ink-900">
        {href ? (
          <Link href={href} className="hover:underline">
            {title}
          </Link>
        ) : (
          title
        )}
      </h2>
      <ul className="border-t border-ink-200">
        {collections.map((collection) => (
          <Row
            key={collection.id}
            href={`${basePath}/${collection.slug}`}
            label={collection.name}
            meta={articleCount(collection.articleCount)}
          />
        ))}
        {articles.map((article) => (
          <Row key={article.id} href={`/help/${article.path}`} label={article.title} />
        ))}
      </ul>
    </section>
  );
}
