import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Article } from "@/components/widget/article";

/** A heading node, the shape `articleHeadings` (components/portal/headings.ts)
 * walks looking for. */
function heading(level: 2 | 3, text: string) {
  return {
    type: "heading",
    attrs: { level },
    content: [{ type: "text", text }],
  };
}

function paragraph(text: string) {
  return { type: "paragraph", content: [{ type: "text", text }] };
}

const ONE_HEADING_DOC = {
  type: "doc",
  content: [paragraph("Intro."), heading(2, "Only section"), paragraph("Body.")],
};

const TWO_HEADING_DOC = {
  type: "doc",
  content: [
    paragraph("Intro."),
    heading(2, "First step"),
    paragraph("Do this."),
    heading(2, "Second step"),
    paragraph("Then this."),
  ],
};

const ARTICLE = {
  id: "a1",
  title: "Refund timing",
  slug: "refund-timing",
  excerpt: "How long a refund takes to land.",
  path: "billing/refund-timing",
  doc: TWO_HEADING_DOC,
  publishedAt: "2026-03-04T00:00:00Z",
  updatedAt: "2026-03-10T00:00:00Z",
  author: { name: "Priya Shah", monogram: "PS" },
};

/** Routes a stubbed `fetch` by pathname and, for `kb/collections`, by
 * whether a `path` is present -- the same two doors `Article` itself
 * calls. */
function routedFetch({
  article,
  ancestors = [],
  related = [],
}: {
  article: unknown;
  ancestors?: unknown[];
  related?: unknown[];
}) {
  return vi.fn(async (input: string) => {
    const url = new URL(input, "http://panel.test");
    if (url.pathname === "/widget/kb/article") {
      return new Response(JSON.stringify({ article, ancestors }), { status: 200 });
    }
    if (url.pathname === "/widget/kb/collections" && url.searchParams.get("path")) {
      return new Response(
        JSON.stringify({ collection: { id: "c", name: "Billing" }, articles: related }),
        { status: 200 },
      );
    }
    return new Response(JSON.stringify(null), { status: 404 });
  });
}

describe("Article, the header", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the title, the excerpt as a subtitle, and the author with a human-readable date", async () => {
    vi.stubGlobal("fetch", routedFetch({ article: ARTICLE, ancestors: [{ name: "Billing", slug: "billing" }] }));

    render(<Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={() => {}} />);

    expect(await screen.findByRole("heading", { name: "Refund timing" })).toBeTruthy();
    expect(screen.getByText("How long a refund takes to land.")).toBeTruthy();
    expect(screen.getByText("Priya Shah")).toBeTruthy();
    // The avatar -- the author's monogram, standing in for a picture we
    // never fetch one of.
    expect(screen.getByText("PS")).toBeTruthy();
    // Written out the way a person would, not the ISO string the API sent.
    expect(screen.getByText("4 March 2026")).toBeTruthy();
    expect(screen.queryByText(/2026-03-04/)).toBeNull();
  });

  it("shows neither an avatar nor a byline when the article has no author", async () => {
    vi.stubGlobal("fetch", routedFetch({ article: { ...ARTICLE, author: null } }));

    render(<Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={() => {}} />);

    await screen.findByRole("heading", { name: "Refund timing" });
    expect(screen.queryByText("Priya Shah")).toBeNull();
    // The date still shows on its own.
    expect(screen.getByText("4 March 2026")).toBeTruthy();
  });

  it("tells the visitor plainly when the article cannot be found", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(null), { status: 404 })));

    render(<Article widgetKey="rdw_test" path="missing" onCompose={() => {}} onOpen={() => {}} />);

    expect(await screen.findByText(/could not be found/i)).toBeTruthy();
  });
});

describe("Article, the table of contents", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders no table of contents at all for an article with fewer than two headings", async () => {
    // One entry is furniture, not navigation.
    vi.stubGlobal("fetch", routedFetch({ article: { ...ARTICLE, doc: ONE_HEADING_DOC } }));

    render(<Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={() => {}} />);

    await screen.findByRole("heading", { name: "Refund timing" });
    expect(screen.queryByText("Contents")).toBeNull();
    expect(screen.queryByRole("navigation", { name: "On this page" })).toBeNull();
  });

  it("collapses a two-or-more-heading article's contents behind a native disclosure, each entry jumping to its heading", async () => {
    vi.stubGlobal("fetch", routedFetch({ article: ARTICLE }));

    const { container } = render(
      <Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={() => {}} />,
    );

    await screen.findByRole("heading", { name: "Refund timing" });
    const details = container.querySelector("details");
    expect(details).toBeTruthy();
    // Collapsed by default -- a native <details> starts closed unless told
    // otherwise, and nothing here opens it.
    expect(details?.hasAttribute("open")).toBe(false);

    // "First step"/"Second step" each appear twice -- once as a ToC entry,
    // once as the heading itself in the body -- so scope to the
    // navigation to get the entry rather than the heading.
    const toc = screen.getByRole("navigation", { name: "On this page" });
    const first = within(toc).getByText("First step") as HTMLAnchorElement;
    const second = within(toc).getByText("Second step") as HTMLAnchorElement;
    expect(first.getAttribute("href")).toBe("#first-step");
    expect(second.getAttribute("href")).toBe("#second-step");

    // The heading in the body itself carries the same id the entry points
    // at -- one pass produced both, so they cannot disagree.
    expect(container.querySelector("#first-step")?.tagName).toBe("H2");
  });
});

describe("Article, related articles", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists the collection's other articles, excluding this one", async () => {
    vi.stubGlobal(
      "fetch",
      routedFetch({
        article: ARTICLE,
        ancestors: [{ name: "Billing", slug: "billing" }],
        related: [
          { id: "a1", title: "Refund timing", slug: "refund-timing", excerpt: "", path: "billing/refund-timing" },
          { id: "a2", title: "Chargebacks", slug: "chargebacks", excerpt: "How disputes work.", path: "billing/chargebacks" },
        ],
      }),
    );

    render(<Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={() => {}} />);

    expect(await screen.findByText("Related articles")).toBeTruthy();
    expect(screen.getByText("Chargebacks")).toBeTruthy();
    // Not itself.
    expect(screen.queryAllByText("Refund timing").length).toBe(1); // the h1 only
  });

  it("opens a related article in place, on the same lateral move as any other article row", async () => {
    const onOpen = vi.fn();
    vi.stubGlobal(
      "fetch",
      routedFetch({
        article: ARTICLE,
        ancestors: [{ name: "Billing", slug: "billing" }],
        related: [
          { id: "a2", title: "Chargebacks", slug: "chargebacks", excerpt: "", path: "billing/chargebacks" },
        ],
      }),
    );

    render(<Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={onOpen} />);

    fireEvent.click(await screen.findByText("Chargebacks"));
    expect(onOpen).toHaveBeenCalledWith("billing/chargebacks");
  });

  it("renders no related-articles section at all when there are none", async () => {
    vi.stubGlobal("fetch", routedFetch({ article: ARTICLE, ancestors: [{ name: "Billing", slug: "billing" }], related: [] }));

    render(<Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={() => {}} />);

    await screen.findByRole("heading", { name: "Refund timing" });
    expect(screen.queryByText("Related articles")).toBeNull();
  });

  it("renders no related-articles section for an article with no ancestors to search", async () => {
    vi.stubGlobal("fetch", routedFetch({ article: ARTICLE, ancestors: [] }));

    render(<Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={() => {}} />);

    await screen.findByRole("heading", { name: "Refund timing" });
    await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull());
    expect(screen.queryByText("Related articles")).toBeNull();
  });
});

describe("Article, the way out to the full help site", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("links to the article on the help site, opening a new tab rather than navigating the panel's own iframe", async () => {
    vi.stubGlobal("fetch", routedFetch({ article: ARTICLE }));

    render(<Article widgetKey="rdw_test" path="billing/refund-timing" onCompose={() => {}} onOpen={() => {}} />);

    const link = (await screen.findByText("Open in help center")) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("/help/billing/refund-timing");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noreferrer");
  });
});

describe("Article, telling the panel its own title", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reports null while loading, the title once loaded, and null again on failure", async () => {
    const onTitleChange = vi.fn();
    vi.stubGlobal("fetch", routedFetch({ article: ARTICLE }));

    render(
      <Article
        widgetKey="rdw_test"
        path="billing/refund-timing"
        onCompose={() => {}}
        onOpen={() => {}}
        onTitleChange={onTitleChange}
      />,
    );

    expect(onTitleChange).toHaveBeenCalledWith(null);
    await waitFor(() => expect(onTitleChange).toHaveBeenCalledWith("Refund timing"));
  });

  it("reports null when the article cannot be found", async () => {
    const onTitleChange = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(null), { status: 404 })));

    render(
      <Article
        widgetKey="rdw_test"
        path="missing"
        onCompose={() => {}}
        onOpen={() => {}}
        onTitleChange={onTitleChange}
      />,
    );

    await screen.findByText(/could not be found/i);
    expect(onTitleChange).toHaveBeenCalledWith(null);
    expect(onTitleChange).not.toHaveBeenCalledWith("Refund timing");
  });

  it("offers a handful of related articles, not the whole collection", async () => {
    // `related` is the collection flattened -- its own articles plus every
    // section's -- so without a cap an eighty-article collection puts
    // seventy-nine rows under every article in it.
    const many = Array.from({ length: 30 }, (_, index) => ({
      id: `a${index}`,
      title: `Related ${index}`,
      slug: `related-${index}`,
      excerpt: "",
      path: `billing/related-${index}`,
    }));
    vi.stubGlobal(
      "fetch",
      routedFetch({ article: ARTICLE, ancestors: [{ name: "Billing", slug: "billing" }], related: many }),
    );

    render(
      <Article
        widgetKey="rdw_test"
        path="billing/refund-timing"
        onBack={() => {}}
        onOpen={() => {}}
        onCompose={() => {}}
      />,
    );

    await screen.findByText("Related 0");
    // The first five of the thirty, in order.
    expect(screen.getByText("Related 4")).toBeTruthy();
    expect(screen.getAllByText(/^Related \d+$/)).toHaveLength(5);
  });
});
