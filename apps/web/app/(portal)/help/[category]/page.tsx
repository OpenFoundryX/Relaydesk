import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { getPublicKb } from "@/lib/api/public";

type Params = Promise<{ category: string }>;

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) return {};
  const { category: categorySlug } = await params;
  const categories = await getPublicKb(slug);
  const category = categories.find((entry) => entry.slug === categorySlug);
  return category ? { title: category.name } : {};
}

/**
 * One published external category and its published articles. A category
 * slug that does not resolve -- wrong workspace, internal-scoped, or never
 * existed -- looks exactly like one that never existed: `notFound()`.
 */
export default async function HelpCategoryPage({ params }: { params: Params }) {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) notFound();

  const { category: categorySlug } = await params;
  const categories = await getPublicKb(slug);
  const category = categories.find((entry) => entry.slug === categorySlug);
  if (!category) notFound();

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <Link href="/help" className="text-[13px] text-ink-500 hover:text-ink-900">
        ← Knowledge Base
      </Link>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink-900">
        {category.name}
      </h1>

      {category.articles.length === 0 ? (
        <p className="mt-8 text-[13px] text-ink-500">
          There are no articles in this section yet.
        </p>
      ) : (
        <ul className="mt-8 space-y-4">
          {category.articles.map((article) => (
            <li key={article.id}>
              <Link
                href={`/help/${category.slug}/${article.slug}`}
                className="text-[14px] font-medium text-accent-950 hover:underline"
              >
                {article.title}
              </Link>
              <p className="mt-0.5 text-[13px] leading-relaxed text-ink-500">
                {article.excerpt}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
