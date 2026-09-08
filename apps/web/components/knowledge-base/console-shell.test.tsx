import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { KnowledgeBaseConsole, type ScopeData } from "./console-shell";
import type { ArticleStatus, KbArticleSummary, KbCategory } from "@/lib/types";

// The console's dialogs reach for the server actions. A Server Action module
// is not something jsdom can execute, and none of these assertions call one.
vi.mock("@/app/(console)/knowledge-base/actions", () => ({
  createArticleAction: vi.fn(),
  createCategoryAction: vi.fn(),
  deleteArticleAction: vi.fn(),
  deleteCategoryAction: vi.fn(),
  editCategoryAction: vi.fn(),
}));

// There is no App Router mounted here. `params` and `?tab=` are exactly what
// the shell reads to work out which scope is showing, so the stubs are the
// whole point of this file rather than incidental scaffolding.
const { params, search, path } = vi.hoisted(() => ({
  params: { current: {} as { id?: string } },
  search: { current: new URLSearchParams() },
  path: { current: "/knowledge-base" },
}));
vi.mock("next/navigation", () => ({
  useParams: () => params.current,
  useSearchParams: () => search.current,
  usePathname: () => path.current,
  useRouter: () => ({ push: vi.fn() }),
}));

function category(id: string, name: string, scope: "internal" | "external"): KbCategory {
  return {
    id,
    name,
    slug: name.toLowerCase().replaceAll(" ", "-"),
    scope,
    position: 0,
    articleCount: 1,
  };
}

function summary(id: string, title: string, categoryId: string): KbArticleSummary {
  return {
    id,
    title,
    slug: title.toLowerCase().replaceAll(" ", "-"),
    excerpt: "",
    status: "draft" as ArticleStatus,
    categoryId,
    updatedAt: "2026-09-05T10:00:00Z",
  };
}

const internal: ScopeData = {
  categories: [category("cat-int", "Refund procedure", "internal")],
  articles: [summary("art-int", "Handling a refund request", "cat-int")],
};

const external: ScopeData = {
  categories: [category("cat-ext", "Accounts and Billing", "external")],
  articles: [summary("art-ext", "How to cancel a subscription", "cat-ext")],
};

function shell() {
  return render(
    <KnowledgeBaseConsole internal={internal} external={external} isAdmin>
      <p>the article pane</p>
    </KnowledgeBaseConsole>,
  );
}

/** Which tab the console is telling a screen reader it is on. */
function currentTab(): string | null {
  const tabs = screen.getAllByRole("link", { name: /^(Internal|External)$/ });
  return tabs.find((tab) => tab.getAttribute("aria-current") === "page")?.textContent ?? null;
}

beforeEach(() => {
  params.current = {};
  search.current = new URLSearchParams();
  path.current = "/knowledge-base";
});

describe("KnowledgeBaseConsole", () => {
  describe("on the list route, the tab decides the scope", () => {
    it("shows Internal by default", () => {
      shell();

      expect(currentTab()).toBe("Internal");
      expect(screen.getByText("Refund procedure")).toBeDefined();
      expect(screen.queryByText("Accounts and Billing")).toBeNull();
    });

    it("shows External when ?tab= says so", () => {
      search.current = new URLSearchParams("tab=external");
      shell();

      expect(currentTab()).toBe("External");
      expect(screen.getByText("Accounts and Billing")).toBeDefined();
    });
  });

  // A layout is never told the URL, and an article route carries no `?tab=`
  // at all -- so the scope has to come from the article's own category. Get
  // this wrong and opening an external article lands you, silently, on the
  // Internal tab beside a tree that does not contain it.
  describe("on an article route, the article's category decides the scope", () => {
    it("lands on External for an external article, with no ?tab= present", () => {
      params.current = { id: "art-ext" };
      shell();

      expect(currentTab()).toBe("External");
      expect(screen.getByText("Accounts and Billing")).toBeDefined();
      expect(
        screen
          .getByRole("link", { name: /How to cancel a subscription/ })
          .getAttribute("aria-current"),
      ).toBe("page");
    });

    it("lands on Internal for an internal article", () => {
      params.current = { id: "art-int" };
      shell();

      expect(currentTab()).toBe("Internal");
      expect(screen.getByText("Refund procedure")).toBeDefined();
    });

    it("describes the scope it landed on, not the other one", () => {
      params.current = { id: "art-ext" };
      shell();

      expect(
        screen.getByText(/Your external knowledge base is customer-facing/),
      ).toBeDefined();
      expect(screen.queryByText(/procedures for your AI agent/)).toBeNull();
    });

    // A deleted or unknown id belongs to no category. Internal is the same
    // thing the list route shows with no tab, which is the least surprising
    // place to be while the pane beside it renders a 404.
    it("falls back to Internal for an id in neither scope", () => {
      params.current = { id: "art-gone" };
      shell();

      expect(currentTab()).toBe("Internal");
    });
  });

  it("renders the route below it into the right-hand pane", () => {
    shell();
    expect(screen.getByText("the article pane")).toBeDefined();
  });

  // The preview route renders the help site's own layout, tree included.
  // Wrapped in this shell it would show two category trees at once, one
  // console and one portal, which is the picture the preview exists to
  // avoid.
  describe("on the preview route", () => {
    it("steps out of the way and renders only the route below it", () => {
      params.current = { id: "art-ext" };
      path.current = "/knowledge-base/art-ext/preview";
      shell();

      expect(screen.getByText("the article pane")).toBeDefined();
      expect(screen.queryByRole("navigation", { name: "Knowledge base" })).toBeNull();
      expect(screen.queryByRole("link", { name: "External" })).toBeNull();
    });

    it("still renders its own chrome on the editor route", () => {
      params.current = { id: "art-ext" };
      path.current = "/knowledge-base/art-ext";
      shell();

      expect(screen.getByRole("navigation", { name: "Knowledge base" })).toBeDefined();
    });
  });
});
