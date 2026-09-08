import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound, permanentRedirect } from "next/navigation";

import { ArticleView } from "@/components/portal/article-view";
import { CategoryIcon } from "@/components/portal/category-icon";
import { articleCount } from "@/components/portal/collection-card";
import { HelpBreadcrumb } from "@/components/portal/help-breadcrumb";
import { SectionCard } from "@/components/portal/section-card";
import { getPublicNode, type PublicNode } from "@/lib/api/public";

type Params = Promise<{ path: string[] }>;

/**
 * The image resolver for public pages. Deliberately not the console's
 * `/api/kb/images/{id}` proxy -- that one requires a session -- but the
 * public route, which enforces that the image's own article is published
 * before serving a single byte of it.
 */
function publicImageSrc(slug: string) {
  return (id: string) => `/api/public/${slug}/kb/images/${id}`;
}

/** Where the node the API returned actually lives, as a help-site path. */
function canonicalPath(node: PublicNode): string {
  const ancestors = node.ancestors.map((crumb) => crumb.slug);
  return node.kind === "article"
    ? node.article.path
    : [...ancestors, node.category.slug].join("/");
}

async function load(path: string[]) {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();
  const node = await getPublicNode(slug, path);
  if (!node) notFound();
  return { slug, node };
}

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) return {};
  const { path } = await params;
  const node = await getPublicNode(slug, path);
  if (!node) return {};

  if (node.kind === "category") {
    return { title: node.category.name, description: node.category.description };
  }
  return {
    title: node.article.title,
    description: node.article.excerpt,
    openGraph: {
      title: node.article.title,
      description: node.article.excerpt,
      type: "article",
    },
  };
}

/**
 * Every help-site page below the front page: a collection, a section, or an
 * article. One route because a URL does not say which of the three it names
 * until the API has walked it -- see `read_kb_path` on the API side, which
 * makes the same argument for the same reason.
 *
 * A path that resolves to a page living somewhere else is an old link to an
 * article that has since been moved into a section. It redirects rather
 * than rendering, so the article is not served at two addresses and the one
 * a reader copies is the real one.
 */
export default async function HelpPathPage({ params }: { params: Params }) {
  const { path } = await params;
  const { slug, node } = await load(path);

  const canonical = canonicalPath(node);
  if (canonical !== path.join("/")) permanentRedirect(`/help/${canonical}`);

  if (node.kind === "article") {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <HelpBreadcrumb ancestors={node.ancestors} current={node.article.title} />
        <div className="mt-6">
          <ArticleView
            title={node.article.title}
            excerpt={node.article.excerpt}
            doc={node.article.doc}
            imageSrc={publicImageSrc(slug)}
            updatedAt={node.article.updatedAt}
            publishedAt={node.article.publishedAt}
            author={node.article.author}
          />
        </div>
      </main>
    );
  }

  const base = `/help/${canonical}`;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <HelpBreadcrumb ancestors={node.ancestors} current={node.category.name} />

      <div className="mt-6">
        <CategoryIcon name={node.category.icon} className="size-7 text-ink-500" />
        <h1 className="mt-4 text-[28px] font-semibold leading-tight tracking-tight text-ink-900">
          {node.category.name}
        </h1>
        {node.category.description && (
          <p className="mt-2 text-[15px] leading-relaxed text-ink-500">
            {node.category.description}
          </p>
        )}
        <p className="mt-3 text-[13px] text-ink-400">
          {articleCount(node.category.articleCount)}
        </p>
      </div>

      <div className="mt-8 grid gap-4">
        {/* The loose articles first, unlabelled: they belong to this
            collection itself rather than to any of its sections, and a
            heading over them would have to invent a name for "the rest". */}
        {node.articles.length > 0 && (
          <SectionCard
            title={node.category.name}
            href={null}
            collections={[]}
            articles={node.articles}
            basePath={base}
          />
        )}
        {node.sections.map((section) => (
          <SectionCard
            key={section.collection.id}
            title={section.collection.name}
            href={`${base}/${section.collection.slug}`}
            collections={section.collections}
            articles={section.articles}
            basePath={`${base}/${section.collection.slug}`}
          />
        ))}
      </div>
    </main>
  );
}
