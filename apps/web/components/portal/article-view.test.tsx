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

function view(props: Partial<Parameters<typeof ArticleView>[0]> = {}) {
  return render(
    <ArticleView
      title="Refunds"
      excerpt="How to get your money back."
      doc={doc}
      imageSrc={(id) => `/images/${id}`}
      updatedAt="2026-09-04T10:00:00Z"
      publishedAt="2026-09-04T10:00:00Z"
      author={{ name: "Nilesh Pant", monogram: "NP" }}
      {...props}
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

  it("prints the excerpt under the title as the article's subtitle", () => {
    view();

    const subtitle = screen.getByText("How to get your money back.");
    const heading = screen.getByRole("heading", { level: 1 });

    expect(heading.compareDocumentPosition(subtitle) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });

  it("omits the subtitle rather than leaving a gap when there is no excerpt", () => {
    const { container } = view({ excerpt: "" });

    expect(container.querySelector("[data-testid='article-excerpt']")).toBeNull();
  });

  it("says who wrote it and when it was published", () => {
    view();

    expect(screen.getByText("Written by Nilesh Pant")).toBeDefined();
    expect(screen.getByText("4 September 2026")).toBeDefined();
  });

  it("still prints the date when the author's account is gone", () => {
    // `author_user_id` is SET NULL when a user is deleted and the article
    // outlives them; the byline loses a name, not the whole block.
    view({ author: null });

    expect(screen.queryByText(/Written by/)).toBeNull();
    expect(screen.getByText("4 September 2026")).toBeDefined();
  });

  it("falls back to the updated date for an article with no published date", () => {
    view({ publishedAt: null, updatedAt: "2026-09-06T10:00:00Z" });

    expect(screen.getByText("6 September 2026")).toBeDefined();
  });

  it("says when it was last updated only once that is a different day", () => {
    // Otherwise the page prints the same date twice, once as "published"
    // and once as "updated", which tells the reader nothing either time.
    view({ updatedAt: "2026-09-09T10:00:00Z" });

    expect(screen.getByText(/Last updated/).textContent).toBe(
      "Last updated 9 September 2026",
    );
  });

  it("does not repeat the date it has already printed in the byline", () => {
    view();

    expect(screen.queryByText(/Last updated/)).toBeNull();
  });

  // The date is pinned to UTC so the same article never reads as two
  // different days depending on which machine rendered it. 23:30Z on the
  // 4th is the 5th in Sydney, and would drift if this used a local clock.
  it("prints dates in UTC, not in the renderer's time zone", () => {
    view({ publishedAt: "2026-09-04T23:30:00Z" });

    expect(screen.getByText("4 September 2026")).toBeDefined();
  });

  it("gives its headings the ids a contents list links to", () => {
    view({
      doc: {
        type: "doc",
        content: [
          {
            type: "heading",
            attrs: { level: 2 },
            content: [{ type: "text", text: "Getting a refund" }],
          },
        ],
      },
    });

    expect(screen.getByRole("heading", { level: 2 }).id).toBe("getting-a-refund");
  });

  /**
   * The article carries the date and the byline and nothing else. A "was
   * this helpful?" control was considered and deliberately rejected: it is
   * a second anonymous write surface with no backend, and rendering the
   * buttons without one is the dead control this branch has already had to
   * remove twice. Asserting on the absence of *any* control, rather than on
   * that particular wording, is what makes this fail if one is added back
   * under a different label.
   */
  it("offers the reader no controls at all", () => {
    view();

    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryByText(/helpful/i)).toBeNull();
  });

  it("prints no date at all rather than an unparseable one", () => {
    view({ publishedAt: "not-a-date", updatedAt: "not-a-date" });

    expect(screen.queryByText(/Last updated/)).toBeNull();
    expect(screen.getByText("Written by Nilesh Pant")).toBeDefined();
  });
});
