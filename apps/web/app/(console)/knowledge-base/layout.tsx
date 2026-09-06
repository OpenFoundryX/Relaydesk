import { Suspense, type ReactNode } from "react";

import { PageShell } from "@/components/console/page-shell";
import { ArticleGuardProvider } from "@/components/knowledge-base/article-guard";
import { KnowledgeBaseConsole } from "@/components/knowledge-base/console-shell";
import { getArticles, getCategories } from "@/lib/api/kb";
import { getMe } from "@/lib/api/workspace";

export const metadata = { title: "Knowledge base" };

/**
 * The knowledge base is a master-detail console: the tree on the left stays
 * put while articles open and close beside it. That only works if the tree
 * is owned by the layout rather than by a page, so this is where the
 * categories and articles are read -- once, on the server, for both routes
 * underneath it.
 *
 * Both scopes are loaded, not just the active one. A layout is never told
 * the URL, so which tab is active is decided a level down in
 * `KnowledgeBaseConsole`; and on an article route the active scope is the
 * one that article's category belongs to, which nothing here knows either.
 * Four reads instead of two, all cached per request, in exchange for a
 * sidebar that never has to guess.
 */
export default async function KnowledgeBaseLayout({
  children,
}: {
  children: ReactNode;
}) {
  const [
    internalCategories,
    externalCategories,
    internalArticles,
    externalArticles,
    me,
  ] = await Promise.all([
    getCategories("internal"),
    getCategories("external"),
    getArticles({ scope: "internal" }),
    getArticles({ scope: "external" }),
    getMe(),
  ]);

  return (
    <PageShell>
      <ArticleGuardProvider>
        {/* `KnowledgeBaseConsole` reads `?tab=`, which is a dynamic read the
            way `components/console/sidebar` does it one layout up. */}
        <Suspense fallback={null}>
          <KnowledgeBaseConsole
            internal={{
              categories: internalCategories,
              articles: internalArticles,
            }}
            external={{
              categories: externalCategories,
              articles: externalArticles,
            }}
            isAdmin={me.membership.role === "admin"}
          >
            {children}
          </KnowledgeBaseConsole>
        </Suspense>
      </ArticleGuardProvider>
    </PageShell>
  );
}
