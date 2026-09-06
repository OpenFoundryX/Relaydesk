import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { ArticleStatus, KbArticleSummary, KbCategory } from "@/lib/types";

const statusTone: Record<ArticleStatus, "neutral" | "accent" | "positive"> = {
  draft: "neutral",
  ready: "accent",
  published: "positive",
};

/** `updatedAt` arrives as an ISO timestamp; the list only wants the day. */
function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * The API returns categories and articles as two lists -- a category knows
 * how many articles it holds, not which ones -- so the grouping happens
 * here rather than being asked for in a shape the API does not serve.
 */
export function CategoryList({
  categories,
  articles,
}: {
  categories: KbCategory[];
  articles: KbArticleSummary[];
}) {
  return (
    <div className="space-y-4">
      {categories.map((category) => {
        const entries = articles.filter(
          (article) => article.categoryId === category.id,
        );

        return (
          <section
            key={category.id}
            className="overflow-hidden rounded-lg border border-ink-200 bg-white"
          >
            <header className="flex items-center gap-2 border-b border-ink-200 px-4 py-2.5">
              <h2 className="text-[13px] font-semibold tracking-tight text-ink-900">
                {category.name}
              </h2>
              <span className="tabular rounded-full bg-ink-100 px-2 py-0.5 text-[11px] text-ink-500">
                {category.articleCount}
              </span>
            </header>

            {entries.length > 0 ? (
              <ul>
                {entries.map((article) => (
                  <li key={article.id} className="border-b border-ink-200 last:border-b-0">
                    <Link
                      href={`/knowledge-base/${article.id}`}
                      className="flex items-start gap-3 px-4 py-3 hover:bg-ink-50"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-medium text-ink-900">
                          {article.title}
                        </p>
                        <p className="mt-0.5 line-clamp-1 text-[13px] text-ink-500">
                          {article.excerpt || "No excerpt yet."}
                        </p>
                      </div>
                      <Badge
                        variant={statusTone[article.status]}
                        className="mt-0.5 shrink-0"
                      >
                        {article.status}
                      </Badge>
                      <span className="tabular mt-1 shrink-0 text-[11px] text-ink-400">
                        {formatDay(article.updatedAt)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-4 py-3 text-[13px] text-ink-500">
                No articles in this category yet.
              </p>
            )}
          </section>
        );
      })}
    </div>
  );
}
