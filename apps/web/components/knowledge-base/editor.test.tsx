import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ArticleEditor } from "./editor";
import type { ArticleStatus, KbArticle, KbCategory } from "@/lib/types";

// The editor imports the console's server actions. A Server Action module is
// not something jsdom can execute, and none of these assertions call one.
vi.mock("@/app/(console)/knowledge-base/actions", () => ({
  saveArticleAction: vi.fn(),
  setArticleStatusAction: vi.fn(),
  uploadArticleImageAction: vi.fn(),
}));

const category: KbCategory = {
  id: "cat-1",
  name: "Billing",
  slug: "billing",
  scope: "internal",
  position: 0,
  articleCount: 1,
};

function article(overrides: Partial<KbArticle> = {}): KbArticle {
  return {
    id: "art-1",
    title: "Handling a refund request",
    slug: "handling-a-refund-request",
    excerpt: "",
    status: "draft",
    categoryId: category.id,
    // What the API stores for a brand new article.
    doc: { type: "doc", content: [] },
    updatedAt: "2026-09-05T10:00:00Z",
    publishedAt: null,
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ArticleEditor", () => {
  it("mounts on a brand new article, whose stored document has no blocks", () => {
    render(<ArticleEditor article={article()} category={category} />);
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveProperty(
      "value",
      "Handling a refund request",
    );
  });

  it("renders a stored image node through the console's image proxy", () => {
    const { container } = render(
      <ArticleEditor
        article={article({
          doc: {
            type: "doc",
            content: [{ type: "image", attrs: { id: "img-7", alt: "A receipt" } }],
          },
        })}
        category={category}
      />,
    );

    const image = container.querySelector("img");
    expect(image?.getAttribute("src")).toBe("/api/kb/images/img-7");
    expect(image?.getAttribute("alt")).toBe("A receipt");
  });

  it("offers every toolbar control the authoring surface promises", () => {
    render(<ArticleEditor article={article()} category={category} />);

    for (const label of [
      "Heading 1",
      "Heading 2",
      "Heading 3",
      "Bold",
      "Italic",
      "Inline code",
      "Bullet list",
      "Numbered list",
      "Quote",
      "Code block",
      "Link",
      "Table",
      "Horizontal rule",
      "Image",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeDefined();
    }
  });

  // The API's own table, in `ALLOWED_TRANSITIONS`. Anything this control
  // offers that the API would refuse is a dead end for whoever clicks it.
  const legalTransitions: Record<ArticleStatus, string[]> = {
    draft: ["Mark ready"],
    ready: ["Publish", "Back to draft"],
    published: ["Unpublish"],
  };
  const everyLabel = ["Mark ready", "Publish", "Back to draft", "Unpublish"];

  for (const [status, offered] of Object.entries(legalTransitions)) {
    it(`offers exactly the legal transitions out of ${status}`, () => {
      render(
        <ArticleEditor
          article={article({ status: status as ArticleStatus })}
          category={category}
        />,
      );

      for (const label of everyLabel) {
        const found = screen.queryByRole("button", { name: label });
        if (offered.includes(label)) {
          expect(found, `${status} should offer ${label}`).not.toBeNull();
        } else {
          expect(found, `${status} must not offer ${label}`).toBeNull();
        }
      }
    });
  }
});
