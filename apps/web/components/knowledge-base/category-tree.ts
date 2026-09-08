import type { KbCategory } from "@/lib/types";

/**
 * The console's flat category list, ordered so a collection is followed by
 * what sits under it.
 *
 * The API returns categories as one list ordered by position, which was all
 * the tree needed while categories were flat. With a tree, that list says
 * nothing about shape -- a section can arrive before the collection it
 * belongs to -- so the nesting is rebuilt here and the rows come back
 * depth-first, ready to indent by `depth`.
 *
 * A category whose parent is missing from the list is treated as a root
 * rather than dropped. That happens legitimately: the console fetches one
 * scope at a time, and it is better to show an orphan at the top level than
 * to hide a collection somebody just made.
 */
export function nestCategories(categories: KbCategory[]): KbCategory[] {
  const byParent = new Map<string | null, KbCategory[]>();
  const known = new Set(categories.map((category) => category.id));

  for (const category of categories) {
    const parent =
      category.parentId && known.has(category.parentId) ? category.parentId : null;
    const siblings = byParent.get(parent);
    if (siblings) siblings.push(category);
    else byParent.set(parent, [category]);
  }

  const ordered: KbCategory[] = [];
  const walk = (parent: string | null) => {
    for (const category of byParent.get(parent) ?? []) {
      ordered.push(category);
      walk(category.id);
    }
  };
  walk(null);

  return ordered;
}
