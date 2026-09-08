"use client";

import {
  useState,
  useTransition,
  type MouseEvent,
  type ReactNode,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MoreHorizontal, Plus } from "lucide-react";

import {
  createCategoryAction,
  deleteArticleAction,
  deleteCategoryAction,
  editCategoryAction,
} from "@/app/(console)/knowledge-base/actions";
import { useArticleGuard } from "@/components/knowledge-base/article-guard";
import {
  CategoryFields,
  EMPTY_FACE,
  type CategoryFace,
} from "@/components/knowledge-base/category-fields";
import { nestCategories } from "@/components/knowledge-base/category-tree";
import { NewArticleDialog } from "@/components/knowledge-base/new-article-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ArticleStatus, KbArticleSummary, KbCategory, KbScope } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * What a not-yet-live article is labelled in the tree.
 *
 * A published article carries no badge -- it is the ordinary case, and a
 * badge on every row would say nothing. The other two are named for what
 * they are rather than lumped together as "Draft": "ready" means written and
 * waiting for someone to publish it, which is a different thing to ask of a
 * reader than "still being written".
 */
const PENDING_LABEL: Partial<Record<ArticleStatus, string>> = {
  draft: "Draft",
  ready: "Ready",
};

const shellStyles =
  "w-64 shrink-0 self-start overflow-hidden rounded-lg border border-ink-200 bg-white";

type Pending =
  | { kind: "edit"; category: KbCategory }
  | { kind: "sub"; parent: KbCategory }
  | { kind: "delete-category"; category: KbCategory }
  | { kind: "delete-article"; article: KbArticleSummary };

/**
 * The deepest a category may sit, matching `MAX_DEPTH` in
 * `relaydesk.services.kb_categories`. A row already at the limit is not
 * offered a control the API would refuse.
 */
const MAX_DEPTH = 2;

/**
 * The persistent left-hand tree: every category in the active scope with its
 * articles nested underneath it, and the article on screen highlighted.
 *
 * The API returns categories and articles as two flat lists -- a category
 * knows how many articles it holds, not which ones -- so the nesting happens
 * here, the way the list page's `CategoryList` did before it.
 */
export function SidebarTree({
  scope,
  categories,
  articles,
  activeArticleId,
  isAdmin,
}: {
  scope: KbScope;
  categories: KbCategory[];
  articles: KbArticleSummary[];
  activeArticleId: string | null;
  /**
   * Creating, renaming and deleting a category are admin-only in the API.
   * An agent is not shown a control that would come back 403.
   */
  isAdmin: boolean;
}) {
  const router = useRouter();
  const guard = useArticleGuard();
  const [pending, setPending] = useState<Pending | null>(null);

  const listHref = `/knowledge-base?tab=${scope}`;

  /**
   * The editor next door saves explicitly, so leaving an article with
   * unsaved edits has to be something it gets asked about. It answers for
   * itself -- see `ArticleGuardProvider` -- and a `true` here means it has
   * put its own "leave without saving?" dialog up and this click must not
   * navigate. A modified click opens a new tab and leaves these edits alone.
   */
  function handleNavigate(event: MouseEvent<HTMLAnchorElement>, href: string) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (guard.askBefore(() => router.push(href))) event.preventDefault();
  }

  if (categories.length === 0) {
    // The pane on the right carries the real invitation to start; the tree
    // only says why it is empty.
    const noun = scope === "internal" ? "categories" : "sections";
    return (
      <nav aria-label="Knowledge base" className={shellStyles}>
        <p className="px-3 py-3 text-[13px] text-ink-500">No {noun} yet.</p>
      </nav>
    );
  }

  return (
    <>
      <nav aria-label="Knowledge base" className={shellStyles}>
        <ul className="py-1">
          {nestCategories(categories).map((category) => {
            const entries = articles.filter(
              (article) => article.categoryId === category.id,
            );

            return (
              <li
                key={category.id}
                className="px-1 py-0.5"
                // Indented rather than nested in real <ul>s: the API hands
                // back one flat list per scope, and a section's articles
                // hang off the section itself, so what a reader needs to
                // see here is depth, not containment.
                style={{ paddingLeft: `${0.25 + category.depth * 0.75}rem` }}
              >
                <div className="group flex items-center gap-1 rounded-md px-2 py-1.5">
                  <h2
                    className={cn(
                      "min-w-0 flex-1 truncate text-[13px] tracking-tight text-ink-900",
                      category.depth === 0 ? "font-semibold" : "font-medium",
                    )}
                  >
                    {category.name}
                  </h2>
                  <span className="tabular shrink-0 rounded-full bg-ink-100 px-1.5 text-[11px] leading-5 text-ink-500">
                    {category.articleCount}
                  </span>
                  {isAdmin && (
                    <RowMenu label={`${category.name} actions`}>
                      <DropdownMenuItem
                        onSelect={() => setPending({ kind: "edit", category })}
                      >
                        Edit
                      </DropdownMenuItem>
                      {category.depth < MAX_DEPTH && (
                        <DropdownMenuItem
                          onSelect={() =>
                            setPending({ kind: "sub", parent: category })
                          }
                        >
                          Add section inside
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem
                        destructive
                        // The API refuses this with a 409 while the category
                        // still holds articles, so the tree does not offer it
                        // as something to try.
                        disabled={entries.length > 0}
                        title={
                          entries.length > 0
                            ? "Delete or move its articles first."
                            : undefined
                        }
                        onSelect={() =>
                          setPending({ kind: "delete-category", category })
                        }
                      >
                        Delete category
                      </DropdownMenuItem>
                    </RowMenu>
                  )}
                </div>

                <ul className="ml-2 border-l border-ink-200 pl-1.5">
                  {entries.map((article) => {
                    const href = `/knowledge-base/${article.id}`;
                    const active = article.id === activeArticleId;
                    const badge = PENDING_LABEL[article.status];

                    return (
                      <li key={article.id} className="group flex items-center gap-1">
                        <Link
                          href={href}
                          aria-current={active ? "page" : undefined}
                          onClick={(event) => handleNavigate(event, href)}
                          className={cn(
                            "flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-[13px] transition-colors",
                            active
                              ? "bg-ink-100 font-medium text-ink-900"
                              : "text-ink-600 hover:bg-ink-50 hover:text-ink-900",
                          )}
                        >
                          <span className="min-w-0 flex-1 truncate">
                            {article.title}
                          </span>
                          {badge && (
                            <Badge variant="outline" className="shrink-0">
                              {badge}
                            </Badge>
                          )}
                        </Link>
                        <RowMenu label={`${article.title} actions`}>
                          <DropdownMenuItem
                            destructive
                            onSelect={() =>
                              setPending({ kind: "delete-article", article })
                            }
                          >
                            Delete article
                          </DropdownMenuItem>
                        </RowMenu>
                      </li>
                    );
                  })}

                  {/* Nested under its category rather than sitting beside it,
                      so "add" reads as "add to this one" on both tabs. */}
                  <li>
                    <NewArticleDialog
                      categories={categories}
                      defaultCategoryId={category.id}
                      trigger={
                        <button
                          type="button"
                          className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-ink-500 transition-colors hover:bg-ink-50 hover:text-ink-900"
                        >
                          <Plus className="size-3.5" />
                          Add article
                        </button>
                      }
                    />
                  </li>
                </ul>
              </li>
            );
          })}
        </ul>
      </nav>

      <PendingDialog
        pending={pending}
        onClose={() => setPending(null)}
        onArticleDeleted={(id) => {
          // The pane on the right is showing the article that just stopped
          // existing. Anything else on screen is still valid.
          if (id === activeArticleId) router.push(listHref);
        }}
      />
    </>
  );
}

/**
 * The hover affordance on a row. Kept visible while its own menu is open --
 * otherwise the trigger disappears from under the menu it opened -- and
 * whenever it has keyboard focus, so the menu is reachable without a mouse.
 */
function RowMenu({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={label}
          className={cn(
            "inline-flex size-6 shrink-0 items-center justify-center rounded text-ink-400 transition-colors",
            "opacity-0 focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100",
            "hover:bg-ink-200 hover:text-ink-900",
          )}
        >
          <MoreHorizontal className="size-3.5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">{children}</DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * One dialog for all three destructive-or-renaming paths. They are mutually
 * exclusive -- a menu opens exactly one of them -- and sharing the shell
 * keeps the error line, the pending state and the close handling in a single
 * place instead of three near-copies.
 */
function PendingDialog({
  pending,
  onClose,
  onArticleDeleted,
}: {
  pending: Pending | null;
  onClose: () => void;
  onArticleDeleted: (articleId: string) => void;
}) {
  const [face, setFace] = useState<CategoryFace>(EMPTY_FACE);
  const [error, setError] = useState<string | null>(null);
  const [running, startTransition] = useTransition();

  // `pending` changing means a different menu item was picked; reset the
  // draft and any message left over from the last attempt. Editing starts
  // from what the category already shows, so an author changing an icon
  // does not have to retype its blurb.
  const [seen, setSeen] = useState<Pending | null>(null);
  if (pending !== seen) {
    setSeen(pending);
    setFace(
      pending?.kind === "edit"
        ? {
            name: pending.category.name,
            description: pending.category.description,
            icon: pending.category.icon,
          }
        : EMPTY_FACE,
    );
    setError(null);
  }

  if (!pending) return null;

  function handleOpenChange(next: boolean) {
    if (!next && !running) onClose();
  }

  function run(work: () => Promise<{ ok: true } | { ok: false; message: string }>) {
    setError(null);
    startTransition(async () => {
      const result = await work();
      if (result.ok) {
        onClose();
      } else {
        setError(result.message);
      }
    });
  }

  const edit = pending.kind === "edit" ? pending : null;
  const sub = pending.kind === "sub" ? pending : null;
  const removeCategory =
    pending.kind === "delete-category" ? pending.category : null;
  const removeArticle = pending.kind === "delete-article" ? pending.article : null;

  return (
    <Dialog open onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {edit && "Edit category"}
            {sub && `New section in “${sub.parent.name}”`}
            {removeCategory && "Delete category?"}
            {removeArticle && "Delete article?"}
          </DialogTitle>
          {removeCategory && (
            <DialogDescription>
              “{removeCategory.name}” is removed for everyone in the workspace.
              This cannot be undone.
            </DialogDescription>
          )}
          {removeArticle && (
            <DialogDescription>
              “{removeArticle.title}” is removed for everyone in the workspace.
              This cannot be undone.
            </DialogDescription>
          )}
        </DialogHeader>
        <DialogBody>
          {error && (
            <p
              role="alert"
              className="rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
            >
              {error}
            </p>
          )}
          {(edit || sub) && (
            <CategoryFields
              value={face}
              onChange={setFace}
              idPrefix="category"
              slugNote={Boolean(edit)}
            />
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" disabled={running} onClick={onClose}>
            Cancel
          </Button>
          {edit && (
            <Button
              variant="primary"
              disabled={running || face.name.trim().length === 0}
              onClick={() =>
                run(() =>
                  editCategoryAction(edit.category.id, {
                    name: face.name.trim(),
                    description: face.description.trim(),
                    icon: face.icon,
                  }),
                )
              }
            >
              {running ? "Saving…" : "Save"}
            </Button>
          )}
          {sub && (
            <Button
              variant="primary"
              disabled={running || face.name.trim().length === 0}
              onClick={() =>
                run(() =>
                  createCategoryAction(face.name.trim(), sub.parent.scope, {
                    parentId: sub.parent.id,
                    description: face.description.trim(),
                    icon: face.icon,
                  }),
                )
              }
            >
              {running ? "Creating…" : "Create"}
            </Button>
          )}
          {removeCategory && (
            <Button
              variant="danger"
              disabled={running}
              onClick={() => run(() => deleteCategoryAction(removeCategory.id))}
            >
              {running ? "Deleting…" : "Delete category"}
            </Button>
          )}
          {removeArticle && (
            <Button
              variant="danger"
              disabled={running}
              onClick={() =>
                run(async () => {
                  const result = await deleteArticleAction(removeArticle.id);
                  if (result.ok) onArticleDeleted(removeArticle.id);
                  return result;
                })
              }
            >
              {running ? "Deleting…" : "Delete article"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
