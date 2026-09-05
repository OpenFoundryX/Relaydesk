import { notFound } from "next/navigation";

import { PageShell } from "@/components/console/page-shell";
import { ArticleEditor } from "@/components/knowledge-base/editor";
import { getArticle, getCategories } from "@/lib/api/kb";

export const metadata = { title: "Article" };

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
  // editor needs the name and the scope to label itself and to send the
  // reader back to the tab they came from.
  const [internal, external] = await Promise.all([
    getCategories("internal"),
    getCategories("external"),
  ]);
  const category =
    [...internal, ...external].find((entry) => entry.id === article.categoryId) ??
    null;

  return (
    <PageShell width="narrow">
      <ArticleEditor article={article} category={category} />
    </PageShell>
  );
}
