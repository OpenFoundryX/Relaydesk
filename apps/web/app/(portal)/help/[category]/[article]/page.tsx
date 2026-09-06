import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { ArticleView } from "@/components/portal/article-view";
import { PortalKbSidebar } from "@/components/portal/kb-sidebar";
import { helpTree } from "@/components/portal/kb-tree";
import { getPublicArticle, getPublicKb } from "@/lib/api/public";

type Params = Promise<{ category: string; article: string }>;

/**
 * The image resolver for public pages. Deliberately not the console's
 * `/api/kb/images/{id}` proxy -- that one requires a session -- but the
 * public route, which enforces that the image's own article is published
 * before serving a single byte of it.
 */
function publicImageSrc(slug: string) {
  return (id: string) => `/api/public/${slug}/kb/images/${id}`;
}

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) return {};
  const { category, article: articleSlug } = await params;
  const article = await getPublicArticle(slug, category, articleSlug);
  if (!article) return {};
  return {
    title: article.title,
    openGraph: {
      title: article.title,
      description: article.excerpt,
      type: "article",
    },
  };
}

/**
 * A single published article. `notFound()` covers a draft, a ready-but-
 * unpublished article, one in an internal category, one from another
 * workspace, and a slug that never existed -- all the same response, on
 * purpose: distinguishing them would leak which ones exist.
 */
export default async function HelpArticlePage({ params }: { params: Params }) {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();

  const { category, article: articleSlug } = await params;
  // The index is read for the sidebar. `getPublicKb` is `cache()`-wrapped
  // and request-scoped, and `generateMetadata` above has already paid for
  // `getPublicArticle`, so neither of these is an extra round trip. Both
  // apply the same published/external predicates, so the tree beside an
  // article can only ever list articles that are themselves public.
  const [article, categories] = await Promise.all([
    getPublicArticle(slug, category, articleSlug),
    getPublicKb(slug),
  ]);
  if (!article) notFound();

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="flex flex-col gap-10 md:flex-row md:gap-12">
        <div className="w-full shrink-0 md:w-56">
          <Link
            href={`/help/${category}`}
            className="mb-4 inline-block text-[13px] text-ink-500 hover:text-ink-900"
          >
            ← Back
          </Link>
          <PortalKbSidebar
            categories={helpTree(categories)}
            activeArticleId={article.id}
          />
        </div>

        <div className="min-w-0 flex-1">
          <ArticleView
            title={article.title}
            doc={article.doc}
            imageSrc={publicImageSrc(slug)}
            updatedAt={article.updatedAt}
          />
        </div>
      </div>
    </main>
  );
}
