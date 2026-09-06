"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { PortalTreeCategory } from "@/components/portal/kb-tree";
import { cn } from "@/lib/utils";

/**
 * The help centre's persistent left-hand tree: every category with its
 * articles nested underneath, and the article on screen highlighted.
 *
 * A client component for one reason -- the collapse chevron is state, and
 * state has to live somewhere that re-renders. The tree's *data* is not
 * state: every caller reads it on the server and hands it down already
 * shaped, so nothing here fetches, and the sidebar is in the first HTML
 * response rather than after a round trip.
 *
 * Deliberately told nothing about where it is mounted. The portal points
 * its rows at `/help/...`; the console preview points them at
 * `/knowledge-base/{id}/preview`. Both get the same tree.
 */
export function PortalKbSidebar({
  categories,
  activeArticleId = null,
  className,
}: {
  categories: PortalTreeCategory[];
  /** The article being read, if the surface is showing one. */
  activeArticleId?: string | null;
  className?: string;
}) {
  // Collapsed rather than expanded ids, so a category that appears later --
  // a newly published one -- starts open like every other.
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(
    () => new Set<string>(),
  );

  if (categories.length === 0) return null;

  function toggle(id: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  return (
    <nav
      // Named for what the surface is called after the rename -- the portal
      // nav tab above it reads "Knowledge Base" too. The console's own tree
      // (components/knowledge-base/sidebar-tree) is "Knowledge base"; the
      // two are never on screen together, and each matches the label its own
      // surface uses.
      aria-label="Knowledge Base"
      className={cn("text-[13px] leading-normal", className)}
    >
      <ul className="space-y-0.5">
        {categories.map((category) => {
          const open = !collapsed.has(category.id);
          const listId = `portal-kb-${category.id}`;

          return (
            <li key={category.id}>
              <div className="flex items-center gap-0.5">
                <button
                  type="button"
                  aria-expanded={open}
                  aria-controls={listId}
                  aria-label={`${open ? "Collapse" : "Expand"} ${category.name}`}
                  onClick={() => toggle(category.id)}
                  className="inline-flex size-5 shrink-0 items-center justify-center rounded text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-900"
                >
                  {open ? (
                    <ChevronDown className="size-3.5" />
                  ) : (
                    <ChevronRight className="size-3.5" />
                  )}
                </button>
                {category.href ? (
                  <Link
                    href={category.href}
                    className="min-w-0 flex-1 truncate rounded-md px-1.5 py-1 font-semibold tracking-tight text-ink-900 transition-colors hover:bg-ink-50"
                  >
                    {category.name}
                  </Link>
                ) : (
                  <span className="min-w-0 flex-1 truncate px-1.5 py-1 font-semibold tracking-tight text-ink-900">
                    {category.name}
                  </span>
                )}
              </div>

              <ul id={listId} hidden={!open} className="ml-2.5 border-l border-ink-200 pl-1.5">
                {category.articles.map((article) => {
                  const active = article.id === activeArticleId;
                  return (
                    <li key={article.id}>
                      <Link
                        href={article.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "block truncate rounded-md px-2 py-1.5 transition-colors",
                          active
                            ? "bg-ink-100 font-medium text-ink-900"
                            : "text-ink-600 hover:bg-ink-50 hover:text-ink-900",
                        )}
                      >
                        {article.title}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
