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

describe("Ask", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("falls back to search and the form when the answer degrades", async () => {
    // Every AI failure must look like the widget that already works, not
    // like an error -- spec D4.
    const onDegrade = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockAskFetch([{ event: "done", data: { outcome: "degraded", citations: [] } }]),
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
