import { BookMarked, BookOpen } from "lucide-react";

import { EmptyState } from "@/components/console/empty-state";
import { NewCategoryDialog } from "@/components/knowledge-base/new-category-dialog";
import { getCategories } from "@/lib/api/kb";
import { getMe } from "@/lib/api/workspace";

const internalSuggestions = ["Billing", "Returns", "Technical Support"];

const externalSuggestions = [
  "Getting Started",
  "Account & Billing",
  "FAQs",
  "Shipping & Returns",
  "Troubleshooting",
];

/**
 * The right-hand pane with nothing open in it.
 *
 * The tabs, the header and the tree all live in the layout now, so this page
 * is only ever the empty half of a master-detail view: the onboarding
 * prompt while the scope has no categories at all, and otherwise a line
 * telling you the tree beside it is where to start.
 */
export default async function KnowledgeBasePage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const { tab } = await searchParams;
  const scope = tab === "external" ? "external" : "internal";
  const [categories, me] = await Promise.all([getCategories(scope), getMe()]);

  const isInternal = scope === "internal";
  // Creating a category is admin-only in the API, so an agent is not shown
  // a control that would come back 403. Writing articles is not restricted.
  const isAdmin = me.membership.role === "admin";
  const categoryLabel = isInternal ? "category" : "section";

  if (categories.length > 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-300 bg-white px-6 py-10 text-center">
        <p className="text-[13px] text-ink-500">
          Pick an article on the left to start editing, or add a new one under a{" "}
          {categoryLabel}.
        </p>
      </div>
    );
  }

  return (
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
            An admin has to create the first {categoryLabel} before you can write
            an article.
          </p>
        )
      }
    />
  );
}
