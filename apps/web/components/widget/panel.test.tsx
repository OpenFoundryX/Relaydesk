import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Panel } from "@/components/widget/panel";

const workspace = { workspaceName: "Beacon", monogram: "BE", settings: {} };

describe("Panel", () => {
  it("offers a way to search when the knowledge base has articles", () => {
    // The search box itself now lives behind the Help tab (built
    // separately, in help.tsx) -- Home only ever offers the card that
    // switches to it.
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByRole("button", { name: /browse help articles/i })).toBeTruthy();
  });

  it("skips the search affordance entirely when there are no articles", () => {
    // The day-one state for every new customer: a search box over nothing
    // makes the product look broken on the day it is being judged.
    render(<Panel {...workspace} articleCount={0} />);
    expect(screen.queryByRole("button", { name: /browse help articles/i })).toBeNull();
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
    // Appears twice -- once in Header, once in Home's own dark band, which
    // carries the display name alongside the greeting -- so this asserts
    // presence rather than a single match.
    expect(screen.getAllByText("Acme Support").length).toBeGreaterThan(0);
    expect(screen.queryByText("Beacon")).toBeNull();
  });

  it("falls back to the workspace name when no settings.name is configured", () => {
    // Absent means today's behaviour, unchanged.
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getAllByText("Beacon").length).toBeGreaterThan(0);
  });

  // `settings.greeting` no longer surfaces on Home -- the new Home screen's
  // copy is fixed ("How can we help?", plus "Hello {name}." when the
  // visitor's own name is known). It still opens Ask's conversation,
  // unchanged -- see "the panel's day-one view" below and ask.test.tsx.
  it("still passes a configured greeting through to Ask, not Home", () => {
    render(
      <Panel
        {...workspace}
        settings={{ greeting: "Hi! Need a hand?" }}
        articleCount={12}
        aiEnabled
      />,
    );
    // Home no longer shows it -- the conversation does, once opened.
    expect(screen.queryByText("Hi! Need a hand?")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Ask a question/ }));
    expect(screen.getByText("Hi! Need a hand?")).toBeTruthy();
  });

  it("shows the fixed greeting on Home when no name is known", () => {
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByText("How can we help?")).toBeTruthy();
  });

  it("greets the visitor by name on Home, when the loader supplied one", () => {
    render(<Panel {...workspace} articleCount={12} name="Ada" />);
    expect(screen.getByText("Hello Ada.")).toBeTruthy();
    expect(screen.getByText("How can we help?")).toBeTruthy();
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

    expect(screen.queryByRole("button", { name: /browse help articles/i })).toBeNull();
    expect(screen.getByLabelText("Your message")).toBeTruthy();
  });
});

// The deflection baseline's write side (task 11): `searched`, `read` and
// `submitted` posted to the panel's own `/widget/session` route, each at
// most once per panel -- see panel.tsx's `recordEvent`.
//
// `searched` and `read` moved out of this file along with the search box,
// results list and article view they instrument -- those now live behind
// the Help tab, built separately in `help.tsx`. There is nothing left in
// panel.tsx that fires either kind any more (see `recordEvent`'s comment),
// so the two tests that exercised them are gone rather than updated: they
// tested a code path this file no longer contains. Whoever wires the real
// Help component in is the right place for that instrumentation to return.
// `submitted` is untouched -- Compose still lives on the Home tab, exactly
// as before.
describe("Panel deflection events", () => {
  function mockFetch() {
    return vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
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
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("swallows a failed counter post and still completes the visible flow", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/widget/session") return Promise.reject(new Error("network down"));
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    const onSubmit = vi.fn().mockResolvedValue({ ok: true });
    render(
      <Panel {...workspace} articleCount={0} widgetKey="rdw_test" onSubmit={onSubmit} />,
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Your message"), {
      target: { value: "Where is my order?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    // The visible flow (the "Message sent" screen) must render regardless
    // of the counter post's outcome -- a support request can never depend
    // on it.
    await screen.findByText("Message sent");
  });
});

describe("the panel's day-one view", () => {
  it("opens on Home, with the conversation one tap away", () => {
    // An earlier rule opened a configured workspace straight into the
    // conversation. The tab bar hides inside one, so that meant a visitor
    // never saw Home, Help or the tabs at all.
    render(<Panel {...workspace} articleCount={12} aiEnabled />);
    expect(screen.queryByPlaceholderText("Ask a question")).toBeNull();
    expect(screen.getByRole("button", { name: "Home" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Ask a question/ }));
    expect(screen.getByPlaceholderText("Ask a question")).toBeTruthy();
  });

  it("opens on Home when AI is not configured", () => {
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

describe("the panel's tab bar", () => {
  it("shows Home, Messages and Help, with Home active by default", () => {
    render(<Panel {...workspace} articleCount={12} />);
    const home = screen.getByRole("button", { name: "Home" });
    expect(home.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: /Messages/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Help" }).getAttribute("aria-current")).toBeNull();
  });

  it("disables Messages -- no way to read a conversation back without identity", () => {
    // A visitor's past thread cannot be shown safely until there is some
    // way to verify who is asking; an unsigned `data-email` would let
    // anyone read a different customer's history. A disabled tab, not a
    // conversation list with nothing in it.
    render(<Panel {...workspace} articleCount={12} />);
    const messages = screen.getByRole("button", { name: /Messages/ }) as HTMLButtonElement;
    expect(messages.disabled).toBe(true);
  });

  it("switches to the Help tab and marks it current", () => {
    render(<Panel {...workspace} articleCount={12} />);
    fireEvent.click(screen.getByRole("button", { name: "Help" }));
    expect(screen.getByRole("button", { name: "Help" }).getAttribute("aria-current")).toBe(
      "page",
    );
    expect(screen.getByRole("button", { name: "Home" }).getAttribute("aria-current")).toBeNull();
  });

  it("hides the tab bar once a conversation is under way, and restores it going home", async () => {
    render(<Panel {...workspace} articleCount={12} aiEnabled />);
    // Present on Home, gone the moment a conversation is open.
    expect(screen.getByRole("button", { name: "Home" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Ask a question/ }));
    expect(screen.queryByRole("button", { name: "Home" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Talk to a person instead/i }));
    expect(screen.getByLabelText("Your message")).toBeTruthy();
    // Compose is a full-height screen with its own back control too.
    expect(screen.queryByRole("button", { name: "Home" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("button", { name: "Home" })).toBeTruthy();
  });

  it("keeps the tab bar visible on Home's own landing screen", () => {
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByRole("button", { name: "Home" })).toBeTruthy();
  });

  it("keeps the Home tab mounted, not remounted, after switching to Help and back", () => {
    // The mechanism behind "switching tabs does not lose where the
    // visitor was": each tab's content stays mounted the whole time and
    // only its CSS visibility toggles. Proven here by identity -- if
    // switching tabs tore Home down and rebuilt it, this would be a
    // different DOM node with the same text, not the same one.
    render(<Panel {...workspace} articleCount={12} />);
    const before = screen.getByText("Browse help articles");

    fireEvent.click(screen.getByRole("button", { name: "Help" }));
    // `getByText` does not filter on CSS visibility the way `getByRole`
    // does -- it still finds Home's content here precisely because this
    // is a hidden, still-mounted screen rather than an absent one.
    expect(screen.getByText("Browse help articles")).toBe(before);

    fireEvent.click(screen.getByRole("button", { name: "Home" }));
    expect(screen.getByText("Browse help articles")).toBe(before);
  });
});

describe("the panel's Home screen", () => {
  it("offers Send us a message, not Ask a question, without AI", () => {
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByText("Send us a message")).toBeTruthy();
    expect(screen.queryByText("Ask a question")).toBeNull();
    fireEvent.click(screen.getByText("Send us a message"));
    expect(screen.getByLabelText("Your message")).toBeTruthy();
  });

  it("shows Ask a question once back on Home, when AI is configured", async () => {
    // Open the conversation from Home, then come back the way a real
    // total failure would: no widget key, so asking degrades to Home.
    render(<Panel {...workspace} articleCount={12} aiEnabled />);
    fireEvent.click(screen.getByRole("button", { name: /Ask a question/ }));
    fireEvent.change(screen.getByPlaceholderText("Ask a question"), {
      target: { value: "Hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    const card = await screen.findByRole("button", { name: /Ask a question/ });
    expect(card).toBeTruthy();
    expect(screen.queryByText("Send us a message")).toBeNull();
    fireEvent.click(card);
    expect(screen.getByPlaceholderText("Ask a question")).toBeTruthy();
  });

  it("names the article count on the Browse help articles card", () => {
    render(<Panel {...workspace} articleCount={21} />);
    expect(screen.getByText("Browse 21 articles")).toBeTruthy();
  });

  it("uses the singular for exactly one article", () => {
    render(<Panel {...workspace} articleCount={1} />);
    expect(screen.getByText("Browse 1 article")).toBeTruthy();
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

describe("the panel growing when it needs room", () => {
  function messages() {
    const sent: unknown[] = [];
    vi.spyOn(window.parent, "postMessage").mockImplementation((message) => {
      sent.push(message);
    });
    return sent;
  }

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("asks to grow on entering a conversation and to shrink on the way out", () => {
    const sent = messages();
    render(<Panel {...workspace} articleCount={12} aiEnabled wide />);

    fireEvent.click(screen.getByRole("button", { name: /Ask a question/ }));
    expect(sent).toContain("relaydesk:expand");

    fireEvent.click(screen.getByRole("button", { name: "Back to home" }));
    expect(sent).toContain("relaydesk:collapse");
  });

  it("offers the control only where there is room to grow", () => {
    // Below a laptop the panel is already as large as it gets, and on a
    // phone it is the whole screen. A control that does nothing is worse
    // than no control.
    render(<Panel {...workspace} articleCount={12} wide />);
    expect(screen.getByRole("button", { name: "Expand" })).toBeTruthy();

    cleanup();
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.queryByRole("button", { name: "Expand" })).toBeNull();
  });

  it("stops guessing once the visitor has said what they want", () => {
    const sent = messages();
    render(<Panel {...workspace} articleCount={12} aiEnabled wide />);

    fireEvent.click(screen.getByRole("button", { name: "Expand" }));
    expect(screen.getByRole("button", { name: "Shrink" })).toBeTruthy();

    // Entering a conversation would normally expand; the visitor has
    // already chosen, so nothing more is sent on their behalf.
    const before = sent.length;
    fireEvent.click(screen.getByRole("button", { name: /Ask a question/ }));
    expect(sent.length).toBe(before);
  });
});
