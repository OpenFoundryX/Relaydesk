import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ArticleEditor } from "./editor";
import type { ArticleStatus, KbArticle, KbCategory } from "@/lib/types";

// The editor imports the console's server actions. A Server Action module is
// not something jsdom can execute, and none of these assertions call one.
vi.mock("@/app/(console)/knowledge-base/actions", () => ({
  saveArticleAction: vi.fn(),
  setArticleStatusAction: vi.fn(),
  uploadArticleImageAction: vi.fn(),
}));

// There is no App Router mounted here, so the editor's own `useRouter` has
// to be stood in for. It doubles as the assertion that leaving is something
// the editor decides to do, not something that merely happens.
const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

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

beforeEach(() => {
  push.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** Anything that flips the editor's `dirty` flag will do; typing is the plainest. */
function makeDirty() {
  fireEvent.change(screen.getByRole("textbox", { name: "Title" }), {
    target: { value: "Handling a refund request, revised" },
  });
  expect(screen.getByText("Unsaved changes")).toBeDefined();
}

describe("ArticleEditor", () => {
  it("mounts on a brand new article, whose stored document has no blocks", () => {
    render(<ArticleEditor article={article()} category={category} />);
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveProperty(
      "value",
      "Handling a refund request",
    );
  });

  describe("leaving with unsaved changes", () => {
    it("does not intercept the back link while everything is saved", () => {
      render(<ArticleEditor article={article()} category={category} />);
      const back = screen.getByRole("link", { name: "Knowledge base" });

      // `fireEvent` returns false when a handler called preventDefault. A
      // clean article must let the link navigate on its own.
      expect(fireEvent.click(back)).toBe(true);
      expect(screen.queryByText("Leave without saving?")).toBeNull();
    });

    it("stops the back link and asks first when there are unsaved changes", () => {
      render(<ArticleEditor article={article()} category={category} />);
      makeDirty();

      expect(
        fireEvent.click(screen.getByRole("link", { name: "Knowledge base" })),
      ).toBe(false);
      expect(screen.getByText("Leave without saving?")).toBeDefined();
      expect(push).not.toHaveBeenCalled();
    });

    it("stays put when you keep editing", () => {
      render(<ArticleEditor article={article()} category={category} />);
      makeDirty();
      fireEvent.click(screen.getByRole("link", { name: "Knowledge base" }));

      fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));

      expect(push).not.toHaveBeenCalled();
      expect(screen.getByText("Unsaved changes")).toBeDefined();
    });

    it("leaves for the right scope's tab once you confirm", () => {
      render(<ArticleEditor article={article()} category={category} />);
      makeDirty();
      fireEvent.click(screen.getByRole("link", { name: "Knowledge base" }));

      fireEvent.click(screen.getByRole("button", { name: "Discard and leave" }));

      expect(push).toHaveBeenCalledWith("/knowledge-base?tab=internal");
    });

    it("does not follow a link inside the preview", () => {
      render(
        <ArticleEditor
          article={article({
            doc: {
              type: "doc",
              content: [
                {
                  type: "paragraph",
                  content: [
                    {
                      type: "text",
                      marks: [
                        { type: "link", attrs: { href: "https://example.com/policy" } },
                      ],
                      text: "the refund policy",
                    },
                  ],
                },
              ],
            },
          })}
          category={category}
        />,
      );

      fireEvent.click(screen.getByRole("button", { name: "Preview" }));

      expect(
        fireEvent.click(screen.getByRole("link", { name: "the refund policy" })),
      ).toBe(false);
    });
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
