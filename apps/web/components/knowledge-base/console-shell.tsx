"use client";

import { Suspense, type MouseEvent, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/console/page-header";
import { useArticleGuard } from "@/components/knowledge-base/article-guard";
import { NewArticleDialog } from "@/components/knowledge-base/new-article-dialog";
import { NewCategoryDialog } from "@/components/knowledge-base/new-category-dialog";
import { SidebarTree } from "@/components/knowledge-base/sidebar-tree";
import { SourceDialog } from "@/components/knowledge-base/source-dialog";
import type { KbArticleSummary, KbCategory, KbScope } from "@/lib/types";
import { cn } from "@/lib/utils";

const tabs = [
  { id: "internal", label: "Internal" },
  { id: "external", label: "External" },
] as const;

const descriptions: Record<KbScope, string> = {
  internal:
    "Internal articles are procedures for your AI agent. Describe how to handle each kind of request, step by step.",
  external:
    "Your external knowledge base is customer-facing. Write these articles as if you were speaking directly to a customer.",
};

export interface ScopeData {
  categories: KbCategory[];
  articles: KbArticleSummary[];
}

/**
 * The persistent half of the knowledge base: tabs, the header action bar,
 * and the category tree, with whichever route is open rendered into the pane
 * on the right.
 *
 * This is a client component for one reason -- which scope is active depends
 * on the URL, and a layout is the one place in the App Router that is never
 * told what the URL is. It is handed both scopes already loaded and picks
 * between them here: `?tab=` on the list route, and on an article route the
 * scope of the category that article belongs to, so opening an external
 * article lands you on the External tab rather than silently on Internal.
 */
export function KnowledgeBaseConsole({
  internal,
  external,
  isAdmin,
  children,
}: {
  internal: ScopeData;
  external: ScopeData;
  /** Category create, rename and delete are admin-only in the API. */
  isAdmin: boolean;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const guard = useArticleGuard();

  // ["", "knowledge-base"] on the list route, plus the id on an article.
  const segments = pathname.split("/");
  const activeArticleId = segments[2] || null;

  const scope: KbScope = activeArticleId
    ? external.articles.some((article) => article.id === activeArticleId)
      ? "external"
      : "internal"
    : searchParams.get("tab") === "external"
      ? "external"
      : "internal";

  const { categories, articles } = scope === "external" ? external : internal;
  const isInternal = scope === "internal";

  /**
   * Every way out of the pane on the right has to give an article with
   * unsaved edits the chance to ask first -- the tabs above as much as the
   * article rows in the tree. See `ArticleGuardProvider`.
   */
  function handleNavigate(event: MouseEvent<HTMLAnchorElement>, href: string) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (guard.askBefore(() => router.push(href))) event.preventDefault();
  }

  return (
    <>
      <PageHeader
        title="Knowledge base"
        description={descriptions[scope]}
        actions={
          <>
            <SourceDialog />
            {isAdmin && (
              <NewCategoryDialog
                scope={scope}
                triggerLabel={isInternal ? "New category" : "New section"}
                variant="secondary"
              />
            )}
            {categories.length > 0 && <NewArticleDialog categories={categories} />}
          </>
        }
      />

      <nav className="mb-5 flex items-center gap-1 border-b border-ink-200">
        {tabs.map((entry) => {
          const active = entry.id === scope;
          const href = `/knowledge-base?tab=${entry.id}`;
          return (
            <Link
              key={entry.id}
              href={href}
              aria-current={active ? "page" : undefined}
              onClick={(event) => handleNavigate(event, href)}
              className={cn(
                "-mb-px border-b-2 px-3 pb-2.5 pt-1 text-[13px] transition-colors",
                active
                  ? "border-accent-600 font-medium text-ink-900"
                  : "border-transparent text-ink-500 hover:text-ink-900",
              )}
            >
              {entry.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex items-start gap-5">
        <SidebarTree
          scope={scope}
          categories={categories}
          articles={articles}
          activeArticleId={activeArticleId}
          isAdmin={isAdmin}
        />
        <div className="min-w-0 flex-1">
          {/* The pane is the only thing here that waits on a fetch of its
              own. Its own boundary keeps the tree beside it on screen while
              an article loads, instead of blanking the whole console. */}
          <Suspense
            fallback={
              <div className="h-64 rounded-lg border border-dashed border-ink-200" />
            }
          >
            {children}
          </Suspense>
        </div>
      </div>
    </>
  );
}
