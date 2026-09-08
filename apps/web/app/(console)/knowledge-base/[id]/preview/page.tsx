import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ArticleView } from "@/components/portal/article-view";
import { Badge } from "@/components/ui/badge";
import { getArticle, getCategories } from "@/lib/api/kb";
import type { ArticleStatus } from "@/lib/types";

export const metadata = { title: "Preview" };

const STATUS_LABEL: Record<ArticleStatus, string> = {
  draft: "Draft",
  ready: "Ready",
  published: "Published",
};

/**
 * Where a draft's images come from.
 *
 * The console's own proxy, which attaches the session -- not the public
 * `/api/public/{slug}/kb/images/{id}` route the help site uses, which
 * refuses an image whose article is not published. Same reason the editor
 * resolves images through this proxy: it is the one path that works before
 * an article is live.
 */
function consoleImageSrc(id: string): string {
  return `/api/kb/images/${id}`;
}

/**
 * How an article will look on the help site, seen from inside the console.
 *
 * This is the complement to the editor's "Preview live page", which opens
 * the real public URL and is deliberately dead until the article is
 * published and external -- there is no public URL to open before then, and
 * inventing one would mean a public route that serves drafts. This route
 * covers exactly that gap: it is reached through the session (middleware
 * protects `/knowledge-base`), it reads through the console's authenticated
 * API, and so it may show a draft. Nothing here is reachable anonymously,
 * and nothing here changes what `/help` serves.
 *
 * It renders the portal's own `ArticleView` rather than a copy of it. A
 * forked preview would drift from the page it claims to be previewing,
 * which would make it worse than no preview at all.
 */
export default async function ArticlePreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const article = await getArticle(id);
  if (!article) notFound();

  // The article carries a category id, not a category, and the id alone
  // does not say which scope it is in -- so both are read, exactly as the
  // editor route next door does. All four calls are `cache()`-wrapped and
  // the layout above has already made them this request.
  const [internal, external] = await Promise.all([
    getCategories("internal"),
    getCategories("external"),
  ]);
  const category =
    [...internal, ...external].find((entry) => entry.id === article.categoryId) ??
    null;
  const scope = category?.scope ?? "internal";

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2">
        <Link
          href={`/knowledge-base/${article.id}`}
          className="flex items-center gap-1.5 text-[13px] text-ink-500 transition-colors hover:text-ink-900"
        >
          <ArrowLeft aria-hidden className="size-4" />
          Back to editing
        </Link>
        <Badge variant={article.status === "published" ? "positive" : "outline"}>
          {STATUS_LABEL[article.status]}
        </Badge>
        <p className="text-[13px] text-ink-500">
          {article.status === "published" && scope === "external"
            ? "How this article looks on your help centre."
            : "How this article will look on your help centre once it is published."}
        </p>
      </div>

      {scope === "internal" && (
        <p className="mb-4 rounded-md border border-ink-200 bg-ink-50 px-3 py-2 text-[13px] text-ink-600">
          This is an internal article. It is a procedure for your AI agent and
          will not appear on your help centre — this is only what it would look
          like there.
        </p>
      )}

      {/* The frame stands in for the browser window the help site fills, so
          the reading width and the contents list beside the body land where
          they will in the real thing. The portal's own hero, nav and search
          are not reproduced: they would be controls that go nowhere from
          inside the console. */}
      <div className="overflow-hidden rounded-lg border border-ink-200 bg-white">
        <div className="px-6 py-10">
          <ArticleView
            title={article.title}
            excerpt={article.excerpt}
            doc={article.doc}
            imageSrc={consoleImageSrc}
            updatedAt={article.updatedAt}
            publishedAt={article.publishedAt}
            author={article.author}
          />
        </div>
      </div>
    </div>
  );
}
