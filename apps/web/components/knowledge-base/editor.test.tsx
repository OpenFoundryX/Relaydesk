import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TRANSITIONS } from "./article-status";
import { ArticleEditor } from "./editor";
import { setArticleStatusAction } from "@/app/(console)/knowledge-base/actions";
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

/**
 * Where this workspace's public help site lives. The console always has one
 * -- it comes from the workspace on the session -- so it is a plain required
 * prop rather than something the editor has to cope with the absence of.
 */
const portalOrigin = "http://chronon.localhost:3000";

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
    render(<ArticleEditor article={article()} category={category} portalOrigin={portalOrigin} />);
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveProperty(
      "value",
      "Handling a refund request",
    );
  });

  describe("leaving with unsaved changes", () => {
    it("does not intercept the back link while everything is saved", () => {
      render(<ArticleEditor article={article()} category={category} portalOrigin={portalOrigin} />);
      const back = screen.getByRole("link", { name: "Knowledge base" });

      // `fireEvent` returns false when a handler called preventDefault. A
      // clean article must let the link navigate on its own.
      expect(fireEvent.click(back)).toBe(true);
      expect(screen.queryByText("Leave without saving?")).toBeNull();
    });

    it("stops the back link and asks first when there are unsaved changes", () => {
      render(<ArticleEditor article={article()} category={category} portalOrigin={portalOrigin} />);
      makeDirty();

      expect(
        fireEvent.click(screen.getByRole("link", { name: "Knowledge base" })),
      ).toBe(false);
      expect(screen.getByText("Leave without saving?")).toBeDefined();
      expect(push).not.toHaveBeenCalled();
    });

    it("stays put when you keep editing", () => {
      render(<ArticleEditor article={article()} category={category} portalOrigin={portalOrigin} />);
      makeDirty();
      fireEvent.click(screen.getByRole("link", { name: "Knowledge base" }));

      fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));

      expect(push).not.toHaveBeenCalled();
      expect(screen.getByText("Unsaved changes")).toBeDefined();
    });

    it("leaves for the right scope's tab once you confirm", () => {
      render(<ArticleEditor article={article()} category={category} portalOrigin={portalOrigin} />);
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
          portalOrigin={portalOrigin}
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
        portalOrigin={portalOrigin}
      />,
    );

    const image = container.querySelector("img");
    expect(image?.getAttribute("src")).toBe("/api/kb/images/img-7");
    expect(image?.getAttribute("alt")).toBe("A receipt");
  });

  it("offers every toolbar control the authoring surface promises", () => {
    render(<ArticleEditor article={article()} category={category} portalOrigin={portalOrigin} />);

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

  // The status control is a toggle plus a Publish button. What each state
  // may offer is the API's own table, `ALLOWED_TRANSITIONS`: anything this
  // offers that the API would refuse is a dead end for whoever clicks it.
  describe("the status control", () => {
    it("reads off, with Publish disabled, on a draft", () => {
      render(<ArticleEditor article={article()} category={category} portalOrigin={portalOrigin} />);

      const toggle = screen.getByRole("switch", { name: "Ready to publish" });
      expect(toggle.getAttribute("aria-checked")).toBe("false");
      expect(
        screen.getByRole("button", { name: "Publish" }),
      ).toHaveProperty("disabled", true);
    });

    it("reads on, with Publish enabled, on a ready article", () => {
      render(
        <ArticleEditor article={article({ status: "ready" })} category={category} portalOrigin={portalOrigin} />,
      );

      const toggle = screen.getByRole("switch", { name: "Ready to publish" });
      expect(toggle.getAttribute("aria-checked")).toBe("true");
      expect(
        screen.getByRole("button", { name: "Publish" }),
      ).toHaveProperty("disabled", false);
    });

    it("reads Published and hides Publish once the article is live", () => {
      render(
        <ArticleEditor
          article={article({ status: "published" })}
          category={category}
          portalOrigin={portalOrigin}
        />,
      );

      const toggle = screen.getByRole("switch", { name: "Published" });
      expect(toggle.getAttribute("aria-checked")).toBe("true");
      expect(screen.queryByRole("button", { name: "Publish" })).toBeNull();
      // The one thing the API has no edge for. A "Ready" control here would
      // be a button whose only outcome is a rejection.
      expect(screen.queryByRole("switch", { name: "Ready to publish" })).toBeNull();
    });

    it("unpublishes to draft -- the only edge out of published", async () => {
      vi.mocked(setArticleStatusAction).mockResolvedValue({
        ok: true,
        status: "draft",
      });
      render(
        <ArticleEditor
          article={article({ status: "published" })}
          category={category}
          portalOrigin={portalOrigin}
        />,
      );

      fireEvent.click(screen.getByRole("switch", { name: "Published" }));

      expect(setArticleStatusAction).toHaveBeenCalledWith("art-1", "draft");
      expect(TRANSITIONS.published).not.toContain("ready");
    });

    it("sends a draft to ready, and a ready article back to draft", () => {
      vi.mocked(setArticleStatusAction).mockResolvedValue({
        ok: true,
        status: "ready",
      });
      const { unmount } = render(
        <ArticleEditor article={article()} category={category} portalOrigin={portalOrigin} />,
      );
      fireEvent.click(screen.getByRole("switch", { name: "Ready to publish" }));
      expect(setArticleStatusAction).toHaveBeenLastCalledWith("art-1", "ready");
      unmount();

      render(
        <ArticleEditor article={article({ status: "ready" })} category={category} portalOrigin={portalOrigin} />,
      );
      fireEvent.click(screen.getByRole("switch", { name: "Ready to publish" }));
      expect(setArticleStatusAction).toHaveBeenLastCalledWith("art-1", "draft");
    });

    it("publishes a ready article", () => {
      vi.mocked(setArticleStatusAction).mockResolvedValue({
        ok: true,
        status: "published",
      });
      render(
        <ArticleEditor article={article({ status: "ready" })} category={category} portalOrigin={portalOrigin} />,
      );

      fireEvent.click(screen.getByRole("button", { name: "Publish" }));

      expect(setArticleStatusAction).toHaveBeenLastCalledWith("art-1", "published");
    });
  });

  describe("the public page", () => {
    const external: KbCategory = { ...category, scope: "external", slug: "billing" };

    function previewControl() {
      return (
        screen.queryByRole("link", { name: "Preview live page" }) ??
        screen.getByRole("button", { name: "Preview live page" })
      );
    }

    it("links to it for a published article in an external category", () => {
      render(
        <ArticleEditor
          article={article({ status: "published" })}
          category={external}
          portalOrigin={portalOrigin}
        />,
      );

      expect(previewControl().getAttribute("href")).toBe(
        "http://chronon.localhost:3000/help/billing/handling-a-refund-request",
      );
    });

    // Every one of these would 404 on the help site, so the control says so
    // instead of leading there.
    const noPage: Array<[string, ArticleStatus, KbCategory]> = [
      ["a draft in an external category", "draft", external],
      ["a ready article in an external category", "ready", external],
      ["a published internal article", "published", category],
    ];

    for (const [label, status, own] of noPage) {
      it(`stays disabled for ${label}`, () => {
        render(
          <ArticleEditor
            article={article({ status })}
            category={own}
            portalOrigin={portalOrigin}
          />,
        );

        const control = previewControl();
        expect(control.tagName).toBe("BUTTON");
        expect(control).toHaveProperty("disabled", true);
      });
    }
  });
});
