import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Ask } from "@/components/widget/ask";

/** One SSE-framed byte stream, built from the same event shape the API
 * actually emits (`event: text`/`data: {text}`, `event: done`/`data:
 * {outcome, citations}`) -- see `relaydesk.api.widget.ask`. */
function sseStream(events: { event: string; data: unknown }[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const bytes = events
    .map((entry) => `event: ${entry.event}\ndata: ${JSON.stringify(entry.data)}\n\n`)
    .join("");
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(bytes));
      controller.close();
    },
  });
}

function mockAskFetch(events: { event: string; data: unknown }[]) {
  return vi.fn(async () => new Response(sseStream(events), { status: 200 }));
}

async function askQuestion(question: string) {
  fireEvent.change(screen.getByPlaceholderText("Ask a question"), {
    target: { value: question },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

/** Replies in the composer exactly as a visitor would -- the same input
 * and send button used for the original question, since none of the
 * escalation steps change the composer's placeholder or label. */
async function reply(text: string) {
  fireEvent.change(screen.getByPlaceholderText("Ask a question"), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

describe("Ask", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("falls back when the stream ends without ever saying it is done", async () => {
    // The server guarantees a `done` frame on every path it controls, but
    // it does not control every way a stream ends -- a dropped connection,
    // a crashed upstream, a proxy giving up mid-answer. Without a fallback
    // here the visitor's question hangs with nothing to do next, which is
    // worse than an error.
    const onDegrade = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "text", data: { text: "Refunds land within" } }]),
    );

    render(<Ask widgetKey="rdw_test" onDegrade={onDegrade} onCompose={() => {}} />);
    await askQuestion("How do refunds work?");

    await waitFor(() => expect(onDegrade).toHaveBeenCalledTimes(1));
  });

  it("renders a citation as a link to the article", async () => {
    vi.stubGlobal(
      "fetch",
      mockAskFetch([
        { event: "text", data: { text: "Refunds land within 14 days." } },
        {
          event: "done",
          data: {
            outcome: "answered",
            citations: [{ title: "Refunds", path: "billing/refunds" }],
          },
        },
      ]),
    );

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("How do refunds work?");

    const link = await screen.findByRole("link", { name: "Refunds" });
    expect(link.getAttribute("href")).toBe("/help/billing/refunds");
  });
});

// The four-outcome contract (spec: this slice). `answered` and the
// existing degrade-before-any-conversation paths above are unchanged;
// these cover the other three.
describe("Ask escalation offer", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers to escalate when the model refuses to answer", async () => {
    const onDegrade = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockAskFetch([
        { event: "text", data: { text: "Something ungrounded." } },
        { event: "done", data: { outcome: "refused", citations: [] } },
      ]),
    );

    render(<Ask widgetKey="rdw_test" onDegrade={onDegrade} onCompose={() => {}} />);
    await askQuestion("How do refunds work?");

    expect(await screen.findByText(/couldn't find an answer/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Yes" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "No" })).toBeTruthy();
    // A refusal is not "no conversation possible" -- it must not also
    // bounce the visitor back to search.
    expect(onDegrade).not.toHaveBeenCalled();
  });

  it("offers to escalate when the answer degrades mid-conversation", async () => {
    // Superseded case: `degraded` used to call `onDegrade` and bounce the
    // visitor to search. It is now itself an outcome that offers
    // escalation, since a conversation is already under way.
    const onDegrade = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "done", data: { outcome: "degraded" } }]),
    );

    render(<Ask widgetKey="rdw_test" onDegrade={onDegrade} onCompose={() => {}} />);
    await askQuestion("How do refunds work?");

    expect(await screen.findByRole("button", { name: "Yes" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "No" })).toBeTruthy();
    expect(onDegrade).not.toHaveBeenCalled();
  });

  it("does not offer to escalate when the model just clarifies or greets", async () => {
    const onDegrade = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockAskFetch([
        { event: "text", data: { text: "Which plan are you on?" } },
        { event: "done", data: { outcome: "clarified", citations: [] } },
      ]),
    );

    render(<Ask widgetKey="rdw_test" onDegrade={onDegrade} onCompose={() => {}} />);
    await askQuestion("It's not working");

    expect(await screen.findByText("Which plan are you on?")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Yes" })).toBeNull();
    expect(screen.queryByRole("button", { name: "No" })).toBeNull();
    expect(onDegrade).not.toHaveBeenCalled();
  });

  it("carries on normally after declining", async () => {
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "done", data: { outcome: "refused", citations: [] } }]),
    );

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("How do refunds work?");
    await screen.findByRole("button", { name: "No" });

    fireEvent.click(screen.getByRole("button", { name: "No" }));

    expect(await screen.findByText(/no problem/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Yes" })).toBeNull();
    // The composer is free again for another question.
    expect((screen.getByPlaceholderText("Ask a question") as HTMLInputElement).disabled).toBe(
      false,
    );
  });

  it("collects an email and a name, then files the ticket with the transcript attached", async () => {
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "done", data: { outcome: "refused", citations: [] } }]),
    );
    const onSubmit = vi.fn().mockResolvedValue({ ok: true });

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} onSubmit={onSubmit} />);
    await askQuestion("How do refunds work?");
    await screen.findByRole("button", { name: "Yes" });

    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    await screen.findByText(/what's your email address/i);

    await reply("ada@example.com");
    await screen.findByText(/and your name/i);

    await reply("Ada Lovelace");

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const [sent] = onSubmit.mock.calls[0] as unknown as [FormData];
    expect(sent.get("email")).toBe("ada@example.com");
    expect(sent.get("name")).toBe("Ada Lovelace");
    // The ticket's message is the original unanswered question, not the
    // visitor's most recent reply (their name).
    expect(sent.get("message")).toBe("How do refunds work?");
    const transcript = sent.get("transcript") as string;
    expect(transcript).toContain("Visitor: How do refunds work?");
    // The escalation dialogue is deliberately NOT in the transcript. An
    // agent already has the address in the From field, and a page of the
    // bot asking for it buries the one thing they need to read.
    expect(transcript).not.toContain("ada@example.com");
    expect(transcript).not.toContain("Ada Lovelace");
    expect(transcript).not.toContain("best email address");

    expect(await screen.findByText(/team has it/i)).toBeTruthy();
  });

  it("accepts a skipped name and files with an empty name field", async () => {
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "done", data: { outcome: "degraded" } }]),
    );
    const onSubmit = vi.fn().mockResolvedValue({ ok: true });

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} onSubmit={onSubmit} />);
    await askQuestion("Where is my order?");
    await screen.findByRole("button", { name: "Yes" });
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    await reply("ada@example.com");
    await screen.findByRole("button", { name: "Skip" });
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const [sent] = onSubmit.mock.calls[0] as unknown as [FormData];
    expect(sent.get("name")).toBe("");
  });

  it("reprompts for an email that doesn't look like one, without filing anything", async () => {
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "done", data: { outcome: "refused", citations: [] } }]),
    );
    const onSubmit = vi.fn().mockResolvedValue({ ok: true });

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} onSubmit={onSubmit} />);
    await askQuestion("How do refunds work?");
    await screen.findByRole("button", { name: "Yes" });
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    await reply("not an email");

    expect(await screen.findByText(/doesn't quite look like an email/i)).toBeTruthy();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("tells the visitor plainly when filing fails, and lets them try again", async () => {
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "done", data: { outcome: "refused", citations: [] } }]),
    );
    const onSubmit = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, message: "Too many requests." })
      .mockResolvedValueOnce({ ok: true });

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} onSubmit={onSubmit} />);
    await askQuestion("How do refunds work?");
    await screen.findByRole("button", { name: "Yes" });
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    await reply("ada@example.com");
    await reply("skip");

    expect(await screen.findByText(/too many requests/i)).toBeTruthy();
    const retry = await screen.findByRole("button", { name: "Try again" });

    fireEvent.click(retry);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/team has it/i)).toBeTruthy();
  });

  it("tells the visitor plainly when the network itself fails, without leaving them unsure", async () => {
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "done", data: { outcome: "refused", citations: [] } }]),
    );
    const onSubmit = vi.fn().mockRejectedValue(new Error("network down"));

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} onSubmit={onSubmit} />);
    await askQuestion("How do refunds work?");
    await screen.findByRole("button", { name: "Yes" });
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    await reply("ada@example.com");
    await reply("skip");

    expect(await screen.findByText(/couldn't reach the server/i)).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

describe("Ask, in conversation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends the conversation so far with each question", async () => {
    // Without this the model answers every follow-up with no idea what it
    // follows. The API accepted `history` for a while before anything sent
    // it, and every answer looked fine in isolation.
    const fetchMock = mockAskFetch([
      { event: "text", data: { text: "Within 14 days." } },
      { event: "done", data: { outcome: "answered", citations: [] } },
    ]);
    vi.stubGlobal("fetch", fetchMock);

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("How do refunds work?");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await askQuestion("What about annually?");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const [, init] = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    const second = JSON.parse(init.body as string);
    expect(second.question).toBe("What about annually?");
    expect(second.history).toEqual([
      { role: "visitor", text: "How do refunds work?" },
      { role: "assistant", text: "Within 14 days." },
    ]);
  });

  it("offers a person once the answers stop landing", async () => {
    // Every answer here succeeds, so `refused` never fires. A visitor
    // asking the same thing four ways would otherwise be answered four
    // times and never asked whether they want a human.
    vi.stubGlobal(
      "fetch",
      mockAskFetch([
        { event: "text", data: { text: "Try this." } },
        { event: "done", data: { outcome: "answered", citations: [] } },
      ]),
    );

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    for (const question of ["one", "two", "three"]) {
      await askQuestion(question);
      await waitFor(() =>
        expect(screen.getAllByText("Try this.").length).toBeGreaterThan(0),
      );
    }

    await waitFor(() =>
      expect(screen.getByText(/would you like me to pass this to the team/i)).toBeTruthy(),
    );
  });
});

describe("Ask, opening choices", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers both ways in before anything is asked", () => {
    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    expect(screen.getByRole("button", { name: /Ask a question/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Create a support ticket/ })).toBeTruthy();
  });

  it("files a ticket without ever asking the bot", async () => {
    // Someone who already knows they want a person should not have to ask
    // the bot first and wait to be turned down.
    const onSubmit = vi.fn(async () => ({ ok: true }) as const);
    render(
      <Ask
        widgetKey="rdw_test"
        onDegrade={() => {}}
        onCompose={() => {}}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Create a support ticket/ }));
    await reply("The export button does nothing");
    await reply("ada@example.com");
    await reply("Ada");

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const [sent] = onSubmit.mock.calls[0] as unknown as [FormData];
    expect(sent.get("email")).toBe("ada@example.com");
    expect(sent.get("message")).toBe("The export button does nothing");
  });

  it("hides the choices once the conversation starts", async () => {
    vi.stubGlobal(
      "fetch",
      mockAskFetch([
        { event: "text", data: { text: "Here you go." } },
        { event: "done", data: { outcome: "answered", citations: [] } },
      ]),
    );
    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("How do refunds work?");

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /Create a support ticket/ })).toBeNull(),
    );
  });
});

describe("Ask, the transcript an agent reads", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("names the articles the bot already showed", async () => {
    // Otherwise an agent's first instinct is to send a link the visitor
    // has already read and bounced off, which is the most annoying
    // possible reply.
    const onSubmit = vi.fn(async () => ({ ok: true }) as const);
    const answered = [
      { event: "text", data: { text: "Within 14 days [1]." } },
      {
        event: "done",
        data: {
          outcome: "answered",
          citations: [{ number: 1, title: "Refunds", path: "billing/refunds" }],
        },
      },
    ];
    const refused = [{ event: "done", data: { outcome: "refused", citations: [] } }];
    let call = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        call += 1;
        return new Response(sseStream(call === 1 ? answered : refused), { status: 200 });
      }),
    );

    render(
      <Ask
        widgetKey="rdw_test"
        onDegrade={() => {}}
        onCompose={() => {}}
        onSubmit={onSubmit}
      />,
    );
    await askQuestion("How do refunds work?");
    await screen.findByText(/Within 14 days/);

    await askQuestion("What about annually?");
    await screen.findByText(/couldn't find an answer/i);

    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    await reply("ada@example.com");
    await reply("skip");

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const [sent] = onSubmit.mock.calls[0] as unknown as [FormData];
    expect(sent.get("transcript") as string).toContain("articles shown: Refunds");
  });
});
