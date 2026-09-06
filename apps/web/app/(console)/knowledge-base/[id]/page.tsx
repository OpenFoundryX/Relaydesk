import { notFound } from "next/navigation";

import { ArticleEditor } from "@/components/knowledge-base/editor";
import { getArticle, getCategories } from "@/lib/api/kb";
import { getPortalOrigin } from "@/lib/api/portal";

export const metadata = { title: "Article" };

/**
 * The right-hand pane of the knowledge base console. The tabs, the header
 * and the category tree come from the layout and stay put while this
 * changes, so all this route renders is the editor -- still server-loaded,
 * so a deep link or a refresh lands on the article rather than on an empty
 * shell waiting for a fetch.
 */
export default async function ArticlePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const article = await getArticle(id);
  if (!article) notFound();

  // The article carries a category id, not a category. Both scopes are read
  // because the id alone does not say which one it belongs to, and the
  // editor needs the name and the scope for its breadcrumb, and the slug to
  // build the public help URL Preview opens.
  const [internal, external, portalOrigin] = await Promise.all([
    getCategories("internal"),
    getCategories("external"),
    getPortalOrigin(),
  ]);
  const category =
    [...internal, ...external].find((entry) => entry.id === article.categoryId) ??
    null;

  return (
    // Keyed by id on purpose. Moving between two articles in the sidebar
    // re-renders this same component in the same place, and React would keep
    // the last one's state -- its title box, its dirty flag, and a TipTap
    // instance whose document was set once when it was created. The key
    // makes it a fresh editor for a fresh article.
    <ArticleEditor
      key={article.id}
      article={article}
      category={category}
      portalOrigin={portalOrigin}
    />
  );
}
