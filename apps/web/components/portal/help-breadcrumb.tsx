import Link from "next/link";
import { ChevronRight } from "lucide-react";

import type { PublicCrumb } from "@/lib/api/public";

/**
 * The trail above a collection or an article: All Collections › … › here.
 *
 * The ancestors come from the API with the page, which is also what makes
 * each href buildable -- a crumb's link is every slug up to and including
 * it, and nothing here has to know the shape of the tree to work that out.
 *
 * The last entry is the current page and is rendered as text, not a link:
 * a link to the page you are on is a dead control that still takes a tab
 * stop.
 */
export function HelpBreadcrumb({
  ancestors,
  current,
}: {
  ancestors: PublicCrumb[];
  /** The page itself. Printed last, unlinked. */
  current: string;
}) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[13px] text-ink-500">
        <li className="flex items-center gap-1.5">
          <Link href="/help" className="hover:text-ink-900 hover:underline">
            All Collections
          </Link>
          <ChevronRight className="size-3.5 text-ink-300" aria-hidden />
        </li>
        {ancestors.map((crumb, i) => (
          <li key={crumb.slug} className="flex items-center gap-1.5">
            <Link
              href={`/help/${ancestors
                .slice(0, i + 1)
                .map((step) => step.slug)
                .join("/")}`}
              className="hover:text-ink-900 hover:underline"
            >
              {crumb.name}
            </Link>
            <ChevronRight className="size-3.5 text-ink-300" aria-hidden />
          </li>
        ))}
        <li aria-current="page" className="text-ink-400">
          {current}
        </li>
      </ol>
    </nav>
  );
}
