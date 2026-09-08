import Link from "next/link";

import { CategoryIcon } from "@/components/portal/category-icon";
import type { PublicCollection } from "@/lib/api/public";

export function articleCount(n: number): string {
  return `${n} ${n === 1 ? "article" : "articles"}`;
}

/**
 * One collection on the help site's front page: icon, name, blurb, count.
 *
 * The whole card is the link rather than just the title -- a card this size
 * that only responds to its heading is a target most of which does nothing.
 */
export function CollectionCard({
  collection,
  href,
}: {
  collection: PublicCollection;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="group flex gap-4 rounded-xl border border-ink-200 bg-white p-5 transition-colors hover:border-ink-300 hover:bg-ink-50"
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-ink-100 text-ink-600">
        <CategoryIcon name={collection.icon} className="size-5" />
      </span>
      <span className="min-w-0">
        <span className="block text-[15px] font-semibold tracking-tight text-ink-900 group-hover:underline">
          {collection.name}
        </span>
        {collection.description && (
          <span className="mt-1 block text-[13px] leading-relaxed text-ink-500">
            {collection.description}
          </span>
        )}
        <span className="mt-2 block text-[12px] text-ink-400">
          {articleCount(collection.articleCount)}
        </span>
      </span>
    </Link>
  );
}
