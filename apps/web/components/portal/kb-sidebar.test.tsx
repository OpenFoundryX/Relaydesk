import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PortalKbSidebar } from "./kb-sidebar";
import { helpTree, type PortalTreeCategory } from "./kb-tree";

const tree: PortalTreeCategory[] = [
  {
    id: "cat-billing",
    name: "Billing",
    href: "/help/billing",
    articles: [
      { id: "art-refunds", title: "Refunds", href: "/help/billing/refunds" },
      { id: "art-invoices", title: "Invoices", href: "/help/billing/invoices" },
    ],
  },
  {
    id: "cat-accounts",
    name: "Accounts",
    href: "/help/accounts",
    articles: [
      { id: "art-signin", title: "Signing in", href: "/help/accounts/signing-in" },
    ],
  },
];

describe("PortalKbSidebar", () => {
  it("nests every category's articles underneath it", () => {
    render(<PortalKbSidebar categories={tree} />);

    const billing = screen.getByRole("link", { name: "Billing" });
    const refunds = screen.getByRole("link", { name: "Refunds" });

    expect(refunds.getAttribute("href")).toBe("/help/billing/refunds");
    // The article is inside the category's own <li>, not a sibling of it.
    expect(billing.closest("li")?.contains(refunds)).toBe(true);
  });

  // The whole point of the tree on an article page. Get this wrong and a
  // reader has no idea where in the help centre they are standing.
  it("marks the article being read, and only that one", () => {
    render(<PortalKbSidebar categories={tree} activeArticleId="art-invoices" />);

    const current = screen
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page");

    expect(current.map((link) => link.textContent)).toEqual(["Invoices"]);
  });

  it("marks nothing when no article is being read", () => {
    render(<PortalKbSidebar categories={tree} />);

    expect(
      screen.getAllByRole("link").some((l) => l.getAttribute("aria-current")),
    ).toBe(false);
  });

  it("collapses a category's articles and expands them again", () => {
    render(<PortalKbSidebar categories={tree} activeArticleId="art-signin" />);

    const chevron = screen.getByRole("button", { name: "Collapse Billing" });
    expect(chevron.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(chevron);

    // Hidden from the accessibility tree, so `getByRole` stops finding it.
    expect(screen.queryByRole("link", { name: "Refunds" })).toBeNull();
    // Only that category. Its neighbour is untouched.
    expect(screen.getByRole("link", { name: "Signing in" })).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Expand Billing" }));

    expect(screen.getByRole("link", { name: "Refunds" })).toBeDefined();
  });

  it("renders a category with no page of its own as a label, not a link", () => {
    render(
      <PortalKbSidebar
        categories={[{ ...tree[0], href: null }]}
        activeArticleId="art-refunds"
      />,
    );

    expect(screen.queryByRole("link", { name: "Billing" })).toBeNull();
    expect(screen.getByText("Billing")).toBeDefined();
  });

  it("renders nothing at all when there are no categories", () => {
    const { container } = render(<PortalKbSidebar categories={[]} />);

    expect(container.innerHTML).toBe("");
  });
});

describe("helpTree", () => {
  it("points every row at its public help URL", () => {
    const shaped = helpTree([
      {
        id: "cat-billing",
        name: "Billing",
        slug: "billing",
        articles: [
          { id: "art-refunds", title: "Refunds", slug: "refunds", excerpt: "" },
        ],
      },
    ]);

    expect(shaped).toEqual([
      {
        id: "cat-billing",
        name: "Billing",
        href: "/help/billing",
        articles: [
          { id: "art-refunds", title: "Refunds", href: "/help/billing/refunds" },
        ],
      },
    ]);
  });
});
