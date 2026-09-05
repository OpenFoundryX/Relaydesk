import Link from "next/link";
import { BookMarked, BookOpen } from "lucide-react";

import { EmptyState } from "@/components/console/empty-state";
import { PageHeader } from "@/components/console/page-header";
import { PageShell } from "@/components/console/page-shell";
import { TrialStrip } from "@/components/console/trial-strip";
import { CategoryList } from "@/components/knowledge-base/category-list";
import { NewArticleDialog } from "@/components/knowledge-base/new-article-dialog";
import { NewCategoryDialog } from "@/components/knowledge-base/new-category-dialog";
import { SourceDialog } from "@/components/knowledge-base/source-dialog";
import { getCategories, getArticles } from "@/lib/api/kb";
import { getMe } from "@/lib/api/workspace";
import { cn } from "@/lib/utils";

export const metadata = { title: "Knowledge base" };

const tabs = [
  { id: "internal", label: "Internal" },
  { id: "external", label: "External" },
] as const;

const internalSuggestions = ["Billing", "Returns", "Technical Support"];

const externalSuggestions = [
  "Getting Started",
  "Account & Billing",
  "FAQs",
  "Shipping & Returns",
  "Troubleshooting",
];

export default async function KnowledgeBasePage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const { tab } = await searchParams;
  const scope = tab === "external" ? "external" : "internal";
  const [categories, articles, me] = await Promise.all([
    getCategories(scope),
    getArticles({ scope }),
    getMe(),
  ]);

  const isInternal = scope === "internal";
  // Creating a category is admin-only in the API, so an agent is not shown
  // a control that would come back 403. Writing articles is not restricted.
  const isAdmin = me.membership.role === "admin";
  const categoryLabel = isInternal ? "category" : "section";

  return (
    <PageShell>
      <TrialStrip
        daysLeft={me.workspace.trialDaysLeft}
        plan={me.workspace.plan}
      />

      <PageHeader
        title="Knowledge base"
        description={
          isInternal
            ? "Internal articles are procedures for your AI agent. Describe how to handle each kind of request, step by step."
            : "Your external knowledge base is customer-facing. Write these articles as if you were speaking directly to a customer."
        }
        actions={
          <>
            <SourceDialog />
            {categories.length > 0 && <NewArticleDialog categories={categories} />}
          </>
        }
      />

      <nav className="mb-5 flex items-center gap-1 border-b border-ink-200">
        {tabs.map((entry) => {
          const active = entry.id === scope;
          return (
            <Link
              key={entry.id}
              href={`/knowledge-base?tab=${entry.id}`}
              aria-current={active ? "page" : undefined}
              className={cn(
                "-mb-px border-b-2 px-3 pb-2.5 pt-1 text-[13px] transition-colors",
                active
                  ? "border-accent-600 font-medium text-ink-900"
                  : "border-transparent text-ink-500 hover:text-ink-900",
              )}
            >
              {entry.label}
            </Link>
          );
        })}
      </nav>

      {categories.length > 0 ? (
        <>
          {isAdmin && (
            <div className="mb-3 flex justify-end">
              <NewCategoryDialog
                scope={scope}
                triggerLabel={isInternal ? "New category" : "New section"}
                variant="secondary"
              />
            </div>
          )}
          <CategoryList categories={categories} articles={articles} />
        </>
      ) : (
        <EmptyState
          icon={isInternal ? BookMarked : BookOpen}
          title={
            isInternal
              ? "Write the procedures your agent follows"
              : "Create your user guide"
          }
          description={
            isInternal
              ? "Each article tells the AI agent how to handle one kind of request. Start with the requests you answer most often."
              : "Explain how your product works, answer the questions you get most, and let customers help themselves."
          }
          suggestions={isInternal ? internalSuggestions : externalSuggestions}
          actions={
            isAdmin ? (
              <NewCategoryDialog
                scope={scope}
                triggerLabel={isInternal ? "New category" : "New section"}
              />
            ) : (
              <p className="text-[13px] text-ink-500">
                An admin has to create the first {categoryLabel} before you can
                write an article.
              </p>
            )
          }
        />
      )}
    </PageShell>
  );
}
