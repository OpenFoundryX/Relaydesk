import { useEffect, type ReactNode } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { ArticleGuardProvider, useArticleGuard } from "./article-guard";
import { SidebarTree } from "./sidebar-tree";
import type { ArticleStatus, KbArticleSummary, KbCategory } from "@/lib/types";

// The tree imports the console's server actions -- through its own menu, and
// through the "Add article" dialog it nests under each category. A Server
// Action module is not something jsdom can execute, and none of these
// assertions call one.
vi.mock("@/app/(console)/knowledge-base/actions", () => ({
  createArticleAction: vi.fn(),
  deleteArticleAction: vi.fn(),
  deleteCategoryAction: vi.fn(),
  renameCategoryAction: vi.fn(),
}));

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

beforeAll(() => {
  // Radix's menus drive themselves with pointer capture and scroll the
  // highlighted item into view; jsdom implements neither.
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

beforeEach(() => {
  push.mockClear();
});

function category(overrides: Partial<KbCategory> = {}): KbCategory {
  return {
    id: "cat-1",
    name: "Billing",
    slug: "billing",
    scope: "internal",
    position: 0,
    articleCount: 1,
    ...overrides,
  };
}

function summary(
  id: string,
  title: string,
  status: ArticleStatus,
  categoryId = "cat-1",
): KbArticleSummary {
  return {
    id,
    title,
    slug: title.toLowerCase().replaceAll(" ", "-"),
    excerpt: "",
    status,
    categoryId,
    updatedAt: "2026-09-05T10:00:00Z",
  };
}

const billing = category();
const returns = category({
  id: "cat-2",
  name: "Returns",
  slug: "returns",
  position: 1,
  articleCount: 0,
});

const refunds = summary("art-1", "Handling a refund request", "draft");
const dunning = summary("art-2", "Chasing a failed payment", "published");

function tree(
  props: Partial<Parameters<typeof SidebarTree>[0]> = {},
  children?: ReactNode,
) {
  return render(
    <ArticleGuardProvider>
      {children}
      <SidebarTree
        scope="internal"
        categories={[billing, returns]}
        articles={[refunds, dunning]}
        activeArticleId={null}
        isAdmin
        {...props}
      />
    </ArticleGuardProvider>,
  );
}

/** Opens a Radix menu the way a pointer does. */
function openMenu(name: string) {
  const trigger = screen.getByRole("button", { name });
  fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false, pointerType: "mouse" });
  return trigger;
}

describe("SidebarTree", () => {
  it("nests each category's articles underneath it", () => {
    tree();

    const groups = screen.getAllByRole("listitem");
    const billingGroup = groups.find((item) =>
      item.querySelector("h2")?.textContent === "Billing",
    );
    expect(billingGroup).toBeDefined();

    const links = within(billingGroup!).getAllByRole("link");
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/knowledge-base/art-1",
      "/knowledge-base/art-2",
    ]);
    // Returns holds nothing, so nothing is nested under it.
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });

  it("offers Add article under every category, empty ones included", () => {
    tree();
    expect(screen.getAllByRole("button", { name: "Add article" })).toHaveLength(2);
  });

  it("badges what is not live, and leaves a published article unbadged", () => {
    tree();

    const draftRow = screen.getByRole("link", { name: /Handling a refund request/ });
    expect(draftRow.textContent).toContain("Draft");
    const liveRow = screen.getByRole("link", { name: /Chasing a failed payment/ });
    expect(liveRow.textContent).not.toContain("Draft");
    expect(liveRow.textContent).not.toContain("Ready");
  });

  it("names a ready article Ready rather than calling it a draft", () => {
    tree({ articles: [summary("art-3", "Issuing a credit note", "ready")] });

    expect(
      screen.getByRole("link", { name: /Issuing a credit note/ }).textContent,
    ).toContain("Ready");
  });

  it("marks the open article as the current page", () => {
    tree({ activeArticleId: "art-2" });

    expect(
      screen
        .getByRole("link", { name: /Chasing a failed payment/ })
        .getAttribute("aria-current"),
    ).toBe("page");
    expect(
      screen
        .getByRole("link", { name: /Handling a refund request/ })
        .getAttribute("aria-current"),
    ).toBeNull();
  });

  describe("the row menus", () => {
    it("offers an admin rename and delete on a category", () => {
      tree();
      openMenu("Billing actions");

      expect(screen.getByRole("menuitem", { name: "Rename" })).toBeDefined();
      expect(
        screen.getByRole("menuitem", { name: "Delete category" }),
      ).toBeDefined();
    });

    // Category create, rename and delete are admin-only in the API. An agent
    // is not shown a control that would come back 403.
    it("gives an agent no category menu at all", () => {
      tree({ isAdmin: false });

      expect(screen.queryByRole("button", { name: "Billing actions" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Returns actions" })).toBeNull();
    });

    it("still lets an agent delete an article, which the API allows", () => {
      tree({ isAdmin: false });
      openMenu("Handling a refund request actions");

      expect(
        screen.getByRole("menuitem", { name: "Delete article" }),
      ).toBeDefined();
    });

    // The API answers a delete on a non-empty category with a 409, so the
    // tree does not offer it as something to try.
    it("will not delete a category that still holds articles", () => {
      tree();
      openMenu("Billing actions");

      expect(
        screen
          .getByRole("menuitem", { name: "Delete category" })
          .getAttribute("aria-disabled"),
      ).toBe("true");
    });

    it("will delete an empty one", () => {
      tree();
      openMenu("Returns actions");

      expect(
        screen
          .getByRole("menuitem", { name: "Delete category" })
          .getAttribute("aria-disabled"),
      ).toBeNull();
    });
  });

  describe("leaving an article with unsaved edits", () => {
    /** Stands in for the editor in the pane next door. */
    function Editor({ ask }: { ask: (proceed: () => void) => boolean }) {
      const guard = useArticleGuard();
      useEffect(() => guard.register(ask), [guard, ask]);
      return null;
    }

    /** The editor that has nothing unsaved and never intervenes. */
    const clean = () => vi.fn(() => false);
    /** The editor that stops everything and puts its own dialog up. */
    const unsaved = () => vi.fn(() => true);

    it("lets a click through when the open article is clean", () => {
      const ask = clean();
      tree({ activeArticleId: "art-1" }, <Editor ask={ask} />);

      const other = screen.getByRole("link", { name: /Chasing a failed payment/ });
      // `fireEvent` returns false when a handler called preventDefault.
      expect(fireEvent.click(other)).toBe(true);
      expect(ask).toHaveBeenCalled();
    });

    it("stops the click when the open article says it has unsaved edits", () => {
      tree({ activeArticleId: "art-1" }, <Editor ask={unsaved()} />);

      expect(
        fireEvent.click(screen.getByRole("link", { name: /Chasing a failed payment/ })),
      ).toBe(false);
      expect(push).not.toHaveBeenCalled();
    });

    it("navigates for the editor once it says to go ahead", () => {
      // Whatever the editor decides, the destination is the sidebar's to
      // name -- it hands one over and the editor calls it back.
      const ask = vi.fn((proceed: () => void) => {
        proceed();
        return true;
      });
      tree({ activeArticleId: "art-1" }, <Editor ask={ask} />);

      fireEvent.click(screen.getByRole("link", { name: /Chasing a failed payment/ }));

      expect(push).toHaveBeenCalledWith("/knowledge-base/art-2");
    });

    it("leaves a modified click alone -- it opens a tab, it does not leave", () => {
      const ask = unsaved();
      tree({ activeArticleId: "art-1" }, <Editor ask={ask} />);

      expect(
        fireEvent.click(
          screen.getByRole("link", { name: /Chasing a failed payment/ }),
          { metaKey: true },
        ),
      ).toBe(true);
      expect(ask).not.toHaveBeenCalled();
    });

    // Creating an article redirects into it, so it is one more way out of an
    // unsaved one.
    it("asks before opening Add article too", () => {
      const ask = unsaved();
      tree({ activeArticleId: "art-1" }, <Editor ask={ask} />);

      fireEvent.click(screen.getAllByRole("button", { name: "Add article" })[0]);

      expect(ask).toHaveBeenCalled();
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("opens Add article straight away when nothing is unsaved", () => {
      tree({ activeArticleId: "art-1" }, <Editor ask={clean()} />);

      fireEvent.click(screen.getAllByRole("button", { name: "Add article" })[0]);

      expect(screen.getByRole("dialog")).toBeDefined();
    });
  });
});
