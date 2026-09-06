import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ArticleView } from "./article-view";

const doc = {
  type: "doc",
  content: [
    {
      type: "paragraph",
      content: [{ type: "text", text: "Within thirty days of purchase." }],
    },
  ],
};

function view(updatedAt = "2026-09-04T10:00:00Z") {
  return render(
    <ArticleView
      title="Refunds"
      doc={doc}
      imageSrc={(id) => `/images/${id}`}
      updatedAt={updatedAt}
    />,
  );
}

describe("ArticleView", () => {
  it("renders the title as the page heading, above the body", () => {
    view();

    const heading = screen.getByRole("heading", { level: 1, name: "Refunds" });
    const body = screen.getByText("Within thirty days of purchase.");

    expect(heading.compareDocumentPosition(body) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });

  it("separates the title from the body with a rule", () => {
    const { container } = view();

    const rule = container.querySelector("hr");
    if (!rule) throw new Error("the article rendered no rule under its title");
    const heading = screen.getByRole("heading", { level: 1 });
    const body = screen.getByText("Within thirty days of purchase.");

    expect(heading.compareDocumentPosition(rule) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
    expect(rule.compareDocumentPosition(body) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });

  it("says when the article was last updated, in a machine-readable time", () => {
    const { container } = view();

    expect(screen.getByText(/Last updated/).textContent).toBe(
      "Last updated 4 September 2026",
    );
    expect(container.querySelector("time")?.getAttribute("datetime")).toBe(
      "2026-09-04T10:00:00Z",
    );
  });

  // The date is pinned to UTC so the same article never reads as two
  // different days depending on which machine rendered it. 23:30Z on the
  // 4th is the 5th in Sydney, and would drift if this used a local clock.
  it("prints the date in UTC, not in the renderer's time zone", () => {
    view("2026-09-04T23:30:00Z");

    expect(screen.getByText(/Last updated/).textContent).toBe(
      "Last updated 4 September 2026",
    );
  });

  /**
   * The footer carries the date and nothing else. A "was this helpful?"
   * control was considered for it and deliberately rejected: it is a second
   * anonymous write surface with no backend, and rendering the buttons
   * without one is the dead control this branch has already had to remove
   * twice. Asserting on the absence of *any* control, rather than on the
   * absence of that particular wording, is what makes this fail if one is
   * added back under a different label.
   */
  it("offers the reader no controls at all", () => {
    view();

    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryByText(/helpful/i)).toBeNull();
  });

  it("omits the footer rather than printing an unparseable date", () => {
    view("not-a-date");

    expect(screen.queryByText(/Last updated/)).toBeNull();
  });
});
