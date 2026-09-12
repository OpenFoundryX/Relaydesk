import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Panel } from "@/components/widget/panel";

const workspace = { workspaceName: "Beacon", monogram: "BE", settings: {} };

describe("Panel", () => {
  it("offers search when the knowledge base has articles", () => {
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByPlaceholderText("Search for an answer")).toBeTruthy();
  });

  it("skips search entirely when there are no articles", () => {
    // The day-one state for every new customer: a search box over nothing
    // makes the product look broken on the day it is being judged.
    render(<Panel {...workspace} articleCount={0} />);
    expect(screen.queryByPlaceholderText("Search for an answer")).toBeNull();
    expect(screen.getByLabelText("Your message")).toBeTruthy();
  });

  it("prefills the compose form from the loader's data-email/data-name, when given", () => {
    // Regression for a plan defect spanning tasks 8 and 9: the loader
    // (public/widget.js) has always sent these as query params, but
    // nothing downstream read them until now.
    render(<Panel {...workspace} articleCount={0} email="ada@example.com" name="Ada" />);
    expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe("ada@example.com");
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Ada");
  });

  it("leaves the compose form empty when no prefill is given", () => {
    render(<Panel {...workspace} articleCount={0} />);
    expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("");
  });

  it("shows the configured name in the header instead of the workspace name, when set", () => {
    // spec D10, un-deferred: settings.name replaces the workspace name in
    // the header -- the whole point of a per-key display name.
    render(
      <Panel
        {...workspace}
        settings={{ name: "Acme Support" }}
        articleCount={12}
      />,
    );
    expect(screen.getByText("Acme Support")).toBeTruthy();
    expect(screen.queryByText("Beacon")).toBeNull();
  });

  it("falls back to the workspace name when no settings.name is configured", () => {
    // Absent means today's behaviour, unchanged.
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByText("Beacon")).toBeTruthy();
  });

  it("shows the configured greeting on Home instead of the default copy", () => {
    render(
      <Panel
        {...workspace}
        settings={{ greeting: "Hi! Need a hand?" }}
        articleCount={12}
      />,
    );
    expect(screen.getByText("Hi! Need a hand?")).toBeTruthy();
    expect(screen.queryByText("Hi there. How can we help?")).toBeNull();
  });

  it("falls back to the default greeting when none is configured", () => {
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByText("Hi there. How can we help?")).toBeTruthy();
  });

  it("still has nowhere to search after Sent sends an empty-knowledge-base visitor home", async () => {
    // Regression for a Critical finding: `empty` gated only the panel's
    // *initial* view, not the "go home" transition every one of Header's
    // back chevron, Compose's own back button, and Sent's "Back to home"
    // can reach. A visitor who submits a message on a zero-article
    // workspace and then goes home must land back on Compose, never on
    // Home -- landing on Home would render the search field this whole
    // screen exists to withhold (spec D7).
    const onSubmit = vi.fn().mockResolvedValue({ ok: true });
    render(<Panel {...workspace} articleCount={0} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Your message"), {
      target: { value: "Where is my order?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await screen.findByText("Message sent");
    fireEvent.click(screen.getByRole("button", { name: /back to home/i }));

    expect(screen.queryByPlaceholderText("Search for an answer")).toBeNull();
    expect(screen.getByLabelText("Your message")).toBeTruthy();
  });
});

// The deflection baseline's write side (task 11): `searched`, `read` and
// `submitted` posted to the panel's own `/widget/session` route, each at
// most once per panel -- see panel.tsx's `recordEvent`.
describe("Panel deflection events", () => {
  const article = {
    id: "a1",
    title: "Refunds",
    slug: "refunds",
    excerpt: "",
    path: "billing/refunds",
    doc: { type: "doc", content: [] },
    publishedAt: null,
    updatedAt: "2026-01-01T00:00:00Z",
    author: null,
  };

  function mockFetch(searchResults: unknown[] = [article]) {
    return vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.startsWith("/widget/kb/search")) {
        return new Response(JSON.stringify(searchResults), { status: 200 });
      }
      if (url.startsWith("/widget/kb/article")) {
        return new Response(JSON.stringify(article), { status: 200 });
      }
      if (url === "/widget/session") {
        return new Response(null, { status: 204 });
      }
      return new Response(null, { status: 404 });
    });
  }

  function sessionCalls(fetchMock: ReturnType<typeof mockFetch>) {
    return fetchMock.mock.calls.filter(([input]) => {
      const url = typeof input === "string" ? input : (input as URL).toString();
      return url === "/widget/session";
    });
  }

  function sessionBody(fetchMock: ReturnType<typeof mockFetch>, index: number): unknown {
    const init = sessionCalls(fetchMock)[index][1];
    return JSON.parse(init?.body as string);
  }

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts searched once, not once per search, and never on every keystroke", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<Panel {...workspace} articleCount={12} widgetKey="rdw_test" />);

    fireEvent.change(screen.getByPlaceholderText("Search for an answer"), {
      target: { value: "billing" },
    });
    // Typing alone must never fire the counter -- only a submitted search.
    expect(sessionCalls(fetchMock)).toHaveLength(0);

    fireEvent.submit(screen.getByRole("search"));
    await waitFor(() => expect(sessionCalls(fetchMock)).toHaveLength(1));
    expect(sessionBody(fetchMock, 0)).toMatchObject({ kind: "searched" });

    // Back to Home and search again: still one `searched` post in total.
    fireEvent.click(screen.getByRole("button", { name: "Back to home" }));
    fireEvent.change(screen.getByPlaceholderText("Search for an answer"), {
      target: { value: "refunds" },
    });
    fireEvent.submit(screen.getByRole("search"));
    await screen.findByText(/results for/i);
    expect(sessionCalls(fetchMock)).toHaveLength(1);
  });

  it("posts read once, on the first article opened, not on a second", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<Panel {...workspace} articleCount={12} widgetKey="rdw_test" />);

    fireEvent.change(screen.getByPlaceholderText("Search for an answer"), {
      target: { value: "billing" },
    });
    fireEvent.submit(screen.getByRole("search"));
    fireEvent.click(await screen.findByText("Refunds"));

    // Two posts so far: `searched` (from the search above) then `read`.
    await waitFor(() => expect(sessionCalls(fetchMock)).toHaveLength(2));
    expect(sessionBody(fetchMock, 1)).toMatchObject({ kind: "read" });

    // Back out and open the same article again: no further `read` post.
    fireEvent.click(screen.getByRole("button", { name: "Back to home" }));
    fireEvent.change(screen.getByPlaceholderText("Search for an answer"), {
      target: { value: "billing" },
    });
    fireEvent.submit(screen.getByRole("search"));
    fireEvent.click(await screen.findByText("Refunds"));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(sessionCalls(fetchMock)).toHaveLength(2);
  });

  it("posts submitted after a successful send", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    const onSubmit = vi.fn().mockResolvedValue({ ok: true });
    render(
      <Panel
        {...workspace}
        articleCount={0}
        widgetKey="rdw_test"
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Your message"), {
      target: { value: "Where is my order?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await screen.findByText("Message sent");
    await waitFor(() => expect(sessionCalls(fetchMock)).toHaveLength(1));
    expect(sessionBody(fetchMock, 0)).toMatchObject({ kind: "submitted" });
  });

  it("never fires without a widget key, and never breaks the panel when the post fails", async () => {
    // No `widgetKey`: the same shape a bare test render already exercises
    // above. `fetch` would throw if `recordEvent` ever called it.
    const fetchMock = vi.fn(() => {
      throw new Error("must not be called");
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<Panel {...workspace} articleCount={12} />);

    fireEvent.change(screen.getByPlaceholderText("Search for an answer"), {
      target: { value: "billing" },
    });
    fireEvent.submit(screen.getByRole("search"));
    await screen.findByText(/results for/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("swallows a failed counter post and still completes the visible flow", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/widget/session") return Promise.reject(new Error("network down"));
      return new Response(JSON.stringify([]), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<Panel {...workspace} articleCount={12} widgetKey="rdw_test" />);

    fireEvent.change(screen.getByPlaceholderText("Search for an answer"), {
      target: { value: "billing" },
    });
    fireEvent.submit(screen.getByRole("search"));

    // The visible flow (the search results screen) must render regardless
    // of the counter post's outcome -- a support request can never depend
    // on it.
    await screen.findByText(/results for/i);
  });
});

describe("the panel's day-one view", () => {
  it("opens on the conversation when the workspace can answer", () => {
    render(<Panel {...workspace} articleCount={12} aiEnabled />);
    expect(screen.getByPlaceholderText("Ask a question")).toBeTruthy();
  });

  it("opens on search when AI is not configured", () => {
    // Without this the panel would show a question box that could only
    // bounce the visitor back to search after they typed.
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.queryByPlaceholderText("Ask a question")).toBeNull();
  });

  it("still opens on the form when the knowledge base is empty", () => {
    // Slice 8's rule outranks AI: a model with nothing to ground an answer
    // in cannot answer either.
    render(<Panel {...workspace} articleCount={0} aiEnabled />);
    expect(screen.queryByPlaceholderText("Ask a question")).toBeNull();
  });
});

describe("the panel on a laptop", () => {
  it("scales itself up when the host page is wide", () => {
    const { container } = render(<Panel {...workspace} articleCount={12} wide />);
    const root = container.querySelector('[role="dialog"]') as HTMLElement;
    expect(root.style.zoom).toBe("1.12");
    // `zoom` scales the element's own box, so a panel asking for 100vh
    // would render 112% of the iframe and clip its own header and footer.
    // The height is divided back out; jsdom normalises the calc, so assert
    // the property rather than the literal we wrote.
    expect(root.style.height).toContain("vh");
    expect(root.style.height).not.toBe("100vh");
  });

  it("leaves a phone alone", () => {
    // There the panel is already a full-screen takeover at the reader's
    // own text size; scaling it would fight the device, not help it.
    const { container } = render(<Panel {...workspace} articleCount={12} />);
    const root = container.querySelector('[role="dialog"]') as HTMLElement;
    expect(root.style.zoom).toBe("");
    expect(root.style.height).toBe("");
  });
});
