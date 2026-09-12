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
    const sent = onSubmit.mock.calls[0][0] as FormData;
    expect(sent.get("email")).toBe("ada@example.com");
    expect(sent.get("name")).toBe("Ada Lovelace");
    // The ticket's message is the original unanswered question, not the
    // visitor's most recent reply (their name).
    expect(sent.get("message")).toBe("How do refunds work?");
    const transcript = sent.get("transcript") as string;
    expect(transcript).toContain("Visitor: How do refunds work?");
    expect(transcript).toContain("Visitor: ada@example.com");

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
    const sent = onSubmit.mock.calls[0][0] as FormData;
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
