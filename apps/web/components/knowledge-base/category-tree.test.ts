import { describe, expect, it } from "vitest";

import { nestCategories } from "./category-tree";
import type { KbCategory } from "@/lib/types";

function category(
  id: string,
  name: string,
  parentId: string | null,
  depth: number,
): KbCategory {
  return {
    id,
    name,
    slug: name.toLowerCase().replace(/\s+/g, "-"),
    scope: "external",
    position: 0,
    articleCount: 0,
    parentId,
    depth,
    description: "",
    icon: "",
  };
}

describe("nestCategories", () => {
  it("puts a section directly after the collection it belongs to", () => {
    // The API orders by position, which says nothing about shape -- a
    // section can arrive before its own collection.
    const rows = nestCategories([
      category("b", "Expenses", "a", 1),
      category("c", "For admins", null, 0),
      category("a", "For spenders", null, 0),
    ]);

    expect(rows.map((r) => r.name)).toEqual([
      "For admins",
      "For spenders",
      "Expenses",
    ]);
  });

  it("keeps a whole branch together, deepest last", () => {
    const rows = nestCategories([
      category("a", "For spenders", null, 0),
      category("c", "Creating expenses", "b", 2),
      category("b", "Expenses", "a", 1),
      category("d", "For admins", null, 0),
    ]);

    expect(rows.map((r) => r.name)).toEqual([
      "For spenders",
      "Expenses",
      "Creating expenses",
      "For admins",
    ]);
  });

  it("shows a category whose parent is absent rather than hiding it", () => {
    // The console reads one scope at a time, so a parent can legitimately
    // be missing from the list. Dropping the child would make a collection
    // somebody just created look like it failed to save.
    const rows = nestCategories([category("b", "Orphan", "missing", 1)]);

    expect(rows.map((r) => r.name)).toEqual(["Orphan"]);
  });

  it("returns nothing for nothing", () => {
    expect(nestCategories([])).toEqual([]);
  });
});
