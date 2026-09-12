import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Help } from "@/components/widget/help";

const COLLECTIONS = [
  {
    id: "c1",
    name: "Billing",
    slug: "billing",
    description: "Invoices and refunds",
    icon: "",
    articleCount: 12,
  },
  {
    id: "c2",
    name: "Getting started",
    slug: "getting-started",
    description: "",
    icon: "",
    articleCount: 1,
  },
];

const BILLING_ARTICLES = {
  collection: COLLECTIONS[0],
  articles: [
    {
      id: "a1",
      title: "Refund timing",
      slug: "refund-timing",
      excerpt: "How long a refund takes to land.",
      path: "billing/refund-timing",
    },
  ],
};

const REFUND_ARTICLE = {
  id: "a1",
  title: "Refund timing",
  slug: "refund-timing",
  excerpt: "How long a refund takes to land.",
  path: "billing/refund-timing",
  doc: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "14 days." }] }] },
  publishedAt: null,
  updatedAt: "2026-01-01T00:00:00Z",
  author: null,
};

// `/widget/kb/article` answers with the article's own ancestors alongside
// it (see `getWidgetArticle`), not the article on its own -- Article reads
// the nearest one to find its "Related articles".
const REFUND_ARTICLE_PAGE = {
  article: REFUND_ARTICLE,
  ancestors: [{ name: "Billing", slug: "billing" }],
};

/** Routes a stubbed `fetch` by the request URL, the way each of Help's
 * three reads (collections, a collection's articles, search) actually
 * differ from one another -- by path, not by anything else. */
function routedFetch(routes: Record<string, unknown>) {
  return vi.fn(async (input: string) => {
    const url = new URL(input, "http://panel.test");
    for (const [prefix, body] of Object.entries(routes)) {
      if (url.pathname === prefix) {
        return new Response(JSON.stringify(body), { status: 200 });
      }
    }
    return new Response(JSON.stringify(null), { status: 404 });
  });
}

async function openBilling() {
  await screen.findByText("Billing");
  fireEvent.click(screen.getByText("Billing"));
  await screen.findByText("Refund timing");
}

describe("Help, browsing collections", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists each collection with its description and a pluralised article count", async () => {
    vi.stubGlobal(
      "fetch",
      routedFetch({ "/widget/kb/collections": COLLECTIONS }),
    );

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);

    await screen.findByText("Billing");
    expect(screen.getByText("Invoices and refunds")).toBeTruthy();
    expect(screen.getByText("12 articles")).toBeTruthy();
    expect(screen.getByText("Getting started")).toBeTruthy();
    // Singular count, not "1 articles" -- a small thing a visitor still notices.
    expect(screen.getByText("1 article")).toBeTruthy();
  });

  it("opens a collection to its own articles, with a back control and its name", async () => {
    vi.stubGlobal(
      "fetch",
      routedFetch({
        "/widget/kb/collections": COLLECTIONS,
      }),
    );
    // Re-stub once the collection is known, so the second request (with
    // `path=billing`) resolves differently from the first (no `path`).
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        const url = new URL(input, "http://panel.test");
        if (url.searchParams.get("path") === "billing") {
          return new Response(JSON.stringify(BILLING_ARTICLES), { status: 200 });
        }
        if (url.pathname === "/widget/kb/collections") {
          return new Response(JSON.stringify(COLLECTIONS), { status: 200 });
        }
        return new Response(JSON.stringify(null), { status: 404 });
      }),
    );

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);
    await openBilling();

    expect(screen.getByRole("heading", { name: "Billing" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Back/ })).toBeTruthy();
  });

  it("opens an article from a collection, and its back control returns to that collection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        const url = new URL(input, "http://panel.test");
        if (url.pathname === "/widget/kb/article") {
          return new Response(JSON.stringify(REFUND_ARTICLE_PAGE), { status: 200 });
        }
        if (url.searchParams.get("path") === "billing") {
          return new Response(JSON.stringify(BILLING_ARTICLES), { status: 200 });
        }
        if (url.pathname === "/widget/kb/collections") {
          return new Response(JSON.stringify(COLLECTIONS), { status: 200 });
        }
        return new Response(JSON.stringify(null), { status: 404 });
      }),
    );

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);
    await openBilling();

    fireEvent.click(screen.getByText("Refund timing"));
    expect(await screen.findByRole("heading", { name: "Refund timing" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Back/ }));

    // Back at the collection, not bounced all the way out to the root list.
    expect(await screen.findByRole("heading", { name: "Billing" })).toBeTruthy();
    expect(screen.getByText("Refund timing")).toBeTruthy();
  });

  it("tells the visitor plainly when a workspace has no collections", async () => {
    vi.stubGlobal("fetch", routedFetch({ "/widget/kb/collections": [] }));

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);

    expect(await screen.findByText(/nothing to browse yet/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send a message" })).toBeTruthy();
  });

  it("degrades to the same empty state when the collections request fails outright", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);

    // A visitor must never see the thrown error or a stack trace -- only
    // the same friendly copy an empty workspace gets.
    expect(await screen.findByText(/nothing to browse yet/i)).toBeTruthy();
    expect(screen.queryByText(/network down/i)).toBeNull();
  });

  it("never reaches the network when there is no widget key", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<Help widgetKey={undefined} onCompose={() => {}} />);

    expect(await screen.findByText(/nothing to browse yet/i)).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("Help, searching", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows nothing until submitted, then shows matching articles", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      const url = new URL(input, "http://panel.test");
      if (url.pathname === "/widget/kb/search") {
        expect(url.searchParams.get("q")).toBe("refund");
        return new Response(JSON.stringify([REFUND_ARTICLE]), { status: 200 });
      }
      return new Response(JSON.stringify(COLLECTIONS), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);
    await screen.findByText("Billing");

    fireEvent.change(screen.getByPlaceholderText("Search for help"), {
      target: { value: "refund" },
    });
    // Typing alone must not search -- only submitting does (spec D8).
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("kb/search"))).toBe(false);

    fireEvent.submit(screen.getByRole("search"));

    expect(await screen.findByText("Refund timing")).toBeTruthy();
    expect(screen.queryByText("Billing")).toBeNull();
  });

  it("opens a searched article, and its back control returns to the results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        const url = new URL(input, "http://panel.test");
        if (url.pathname === "/widget/kb/search") return new Response(JSON.stringify([REFUND_ARTICLE]), { status: 200 });
        if (url.pathname === "/widget/kb/article") return new Response(JSON.stringify(REFUND_ARTICLE_PAGE), { status: 200 });
        return new Response(JSON.stringify(COLLECTIONS), { status: 200 });
      }),
    );

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText("Search for help"), {
      target: { value: "refund" },
    });
    fireEvent.submit(screen.getByRole("search"));
    await screen.findByText("Refund timing");

    fireEvent.click(screen.getByText("Refund timing"));
    expect(await screen.findByRole("heading", { name: "Refund timing" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Back/ }));

    expect(await screen.findByText(/Results for/)).toBeTruthy();
    expect(screen.getByText("Refund timing")).toBeTruthy();
  });

  it("tells the visitor plainly when nothing matched", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        const url = new URL(input, "http://panel.test");
        if (url.pathname === "/widget/kb/search") return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify(COLLECTIONS), { status: 200 });
      }),
    );

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText("Search for help"), {
      target: { value: "unobtainium" },
    });
    fireEvent.submit(screen.getByRole("search"));

    expect(await screen.findByText(/nothing matched/i)).toBeTruthy();
  });

  it("clearing the search box by hand returns to the collections list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        const url = new URL(input, "http://panel.test");
        if (url.pathname === "/widget/kb/search") return new Response(JSON.stringify([REFUND_ARTICLE]), { status: 200 });
        return new Response(JSON.stringify(COLLECTIONS), { status: 200 });
      }),
    );

    render(<Help widgetKey="rdw_test" onCompose={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText("Search for help"), {
      target: { value: "refund" },
    });
    fireEvent.submit(screen.getByRole("search"));
    await screen.findByText("Refund timing");

    fireEvent.change(screen.getByPlaceholderText("Search for help"), { target: { value: "" } });

    expect(await screen.findByText("Billing")).toBeTruthy();
  });
});

describe("Help, the deflection counters", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("counts a search", async () => {
    // Slice 8 counts searched / read / submitted to tell a workspace
    // whether the widget is saving them tickets. These two moved in here
    // when Help became a tab and stopped firing entirely -- which reads as
    // "nobody searched", not as "nothing is counting".
    const onEvent = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", { status: 200 })));
    render(<Help widgetKey="rdw_test" onCompose={() => {}} onEvent={onEvent} />);

    fireEvent.change(screen.getByPlaceholderText("Search for help"), {
      target: { value: "refunds" },
    });
    fireEvent.submit(screen.getByPlaceholderText("Search for help").closest("form")!);

    await waitFor(() => expect(onEvent).toHaveBeenCalledWith("searched"));
  });

  it("does not count an empty search", async () => {
    const onEvent = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", { status: 200 })));
    render(<Help widgetKey="rdw_test" onCompose={() => {}} onEvent={onEvent} />);

    fireEvent.submit(screen.getByPlaceholderText("Search for help").closest("form")!);

    expect(onEvent).not.toHaveBeenCalled();
  });
});

describe("Help, asking for room to read", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reports full-height while an article is open, and not before or after, carrying the article's own title once it loads", async () => {
    // The panel hides the tab bar and asks the loader to grow on this
    // signal, and swaps its header for the article's own title -- Only
    // Help knows which of its own screens is showing, and only `Article`
    // knows the title once it has loaded, so a panel deriving either from
    // the outside would be wrong the moment Help (or Article) changes.
    //
    // This used to assert only the boolean; the callback grew a second,
    // optional argument (task 5) once the panel header needed a way to
    // learn the open article's title, and this is the one place that
    // signal is proven to reach a caller end to end.
    const onFullScreenChange = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        const url = new URL(input, "http://panel.test");
        if (url.pathname === "/widget/kb/article") {
          return new Response(
            JSON.stringify({
              article: {
                id: "a",
                title: "Refunds",
                slug: "refunds",
                excerpt: "",
                path: "billing/refunds",
                doc: { type: "doc", content: [] },
                publishedAt: null,
                updatedAt: "2026-01-01T00:00:00Z",
                author: null,
              },
              ancestors: [{ name: "Billing", slug: "billing" }],
            }),
            { status: 200 },
          );
        }
        if (!url.searchParams.get("path")) {
          return new Response(
            JSON.stringify([
              {
                id: "c",
                name: "Billing",
                slug: "billing",
                description: "",
                icon: "",
                articleCount: 1,
              },
            ]),
            { status: 200 },
          );
        }
        return new Response(
          JSON.stringify({
            collection: { id: "c", name: "Billing", slug: "billing" },
            articles: [
              { id: "a", title: "Refunds", slug: "refunds", excerpt: "", path: "billing/refunds" },
            ],
          }),
          { status: 200 },
        );
      }),
    );

    render(
      <Help
        widgetKey="rdw_test"
        onCompose={() => {}}
        onFullScreenChange={onFullScreenChange}
      />,
    );

    // Browsing is not full-height, and carries no title.
    await waitFor(() => expect(onFullScreenChange).toHaveBeenCalledWith(false, undefined));

    fireEvent.click(await screen.findByText("Billing"));
    fireEvent.click(await screen.findByText("Refunds"));

    // Full-height fires immediately, before the article's title is known.
    await waitFor(() => expect(onFullScreenChange).toHaveBeenCalledWith(true, undefined));
    // The title follows once `Article` has loaded it.
    await waitFor(() => expect(onFullScreenChange).toHaveBeenCalledWith(true, "Refunds"));
  });
});
