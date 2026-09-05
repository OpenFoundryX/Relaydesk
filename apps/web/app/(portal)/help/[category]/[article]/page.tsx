import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { DocRenderer } from "@/components/knowledge-base/doc-renderer";
import { getPublicArticle } from "@/lib/api/public";
import { cn } from "@/lib/utils";

type Params = Promise<{ category: string; article: string }>;

/**
 * Typography for a rendered article. Written out rather than pulled from a
 * plugin -- the web app carries no typography plugin -- and kept separate
 * from the console editor's own copy of this: that one styles an editable
 * TipTap surface, this one styles read-only output for anonymous visitors,
 * and the two have no reason to change together.
 */
const articleStyles = cn(
  "text-[15px] leading-relaxed text-ink-800",
  "[&_h1]:mb-2.5 [&_h1]:mt-8 [&_h1]:text-[22px] [&_h1]:font-semibold [&_h1]:tracking-tight [&_h1]:text-ink-900",
  "[&_h2]:mb-2 [&_h2]:mt-7 [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-ink-900",
  "[&_h3]:mb-1.5 [&_h3]:mt-5 [&_h3]:text-[16px] [&_h3]:font-semibold [&_h3]:text-ink-900",
  "[&_p]:my-3",
  "[&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5",
  "[&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5",
  "[&_li]:my-1 [&_li>p]:my-0",
  "[&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:border-accent-500 [&_blockquote]:pl-3 [&_blockquote]:text-ink-600",
  "[&_pre]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-ink-900 [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-[13px] [&_pre]:text-ink-50",
  "[&_:not(pre)>code]:rounded [&_:not(pre)>code]:bg-ink-100 [&_:not(pre)>code]:px-1 [&_:not(pre)>code]:py-0.5 [&_:not(pre)>code]:font-mono [&_:not(pre)>code]:text-[13px]",
  "[&_a]:text-accent-950 [&_a]:underline [&_a]:underline-offset-2",
  "[&_hr]:my-6 [&_hr]:border-ink-200",
  "[&_img]:my-4 [&_img]:max-w-full [&_img]:rounded-md [&_img]:border [&_img]:border-ink-200",
  "[&_table]:my-4 [&_table]:w-full [&_table]:table-fixed [&_table]:border-collapse",
  "[&_td]:border [&_td]:border-ink-200 [&_td]:px-2 [&_td]:py-1.5 [&_td]:align-top",
  "[&_th]:border [&_th]:border-ink-200 [&_th]:bg-ink-50 [&_th]:px-2 [&_th]:py-1.5 [&_th]:text-left [&_th]:font-semibold",
);

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
  const article = await getPublicArticle(slug, category, articleSlug);
  if (!article) notFound();

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <Link
        href={`/help/${category}`}
        className="text-[13px] text-ink-500 hover:text-ink-900"
      >
        ← Back
      </Link>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink-900">
        {article.title}
      </h1>
      <div className={cn(articleStyles, "mt-6")}>
        <DocRenderer doc={article.doc} imageSrc={publicImageSrc(slug)} />
      </div>
    </main>
  );
}
