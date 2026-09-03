import { Ellipsis } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ArticleStatus, KbCategory } from "@/lib/mock/types";

const statusTone: Record<ArticleStatus, "neutral" | "accent" | "positive"> = {
  draft: "neutral",
  ready: "accent",
  published: "positive",
};

export function CategoryList({ categories }: { categories: KbCategory[] }) {
  return (
    <div className="space-y-4">
      {categories.map((category) => (
        <section
          key={category.id}
          className="overflow-hidden rounded-lg border border-ink-200 bg-white"
        >
          <header className="flex items-center gap-2 border-b border-ink-200 px-4 py-2.5">
            <h2 className="text-[13px] font-semibold tracking-tight text-ink-900">
              {category.name}
            </h2>
            <span className="tabular rounded-full bg-ink-100 px-2 py-0.5 text-[11px] text-ink-500">
              {category.articles.length}
            </span>
            <div className="flex-1" />
            <button
              type="button"
              aria-label={`Options for ${category.name}`}
              className="rounded p-1 text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-900"
            >
              <Ellipsis className="size-4" />
            </button>
          </header>

          <ul>
            {category.articles.map((article) => (
              <li
                key={article.id}
                className="flex items-start gap-3 border-b border-ink-200 px-4 py-3 last:border-b-0 hover:bg-ink-50"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-ink-900">
                    {article.title}
                  </p>
                  <p className="mt-0.5 line-clamp-1 text-[13px] text-ink-500">
                    {article.excerpt}
                  </p>
                </div>
                <Badge variant={statusTone[article.status]} className="mt-0.5 shrink-0">
                  {article.status}
                </Badge>
                <span className="tabular mt-1 shrink-0 text-[11px] text-ink-400">
                  {article.updatedAt}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
