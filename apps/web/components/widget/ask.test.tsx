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

/** A different reply per call, for conversations whose outcomes differ --
 *  the last script repeats once the list runs out. */
function mockAskSequence(scripts: { event: string; data: unknown }[][]) {
  let call = 0;
  return vi.fn(async () => {
    const events = scripts[Math.min(call, scripts.length - 1)];
    call += 1;
    return new Response(sseStream(events), { status: 200 });
  });
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

  it("does not send the bot collecting an email as if it were the conversation", async () => {
    // `collecting` turns are the escalation micro-dialogue -- "what's your
    // email address?", "Skip". They are already excluded from the
    // transcript an agent reads, for the reason the flag's own comment
    // gives, and they must be excluded here for a sharper one: the model
    // would be shown six turns of what look like its own prior messages
    // saying "I'll pass this on to the team", as in-context examples of
    // exactly the behaviour `_NO_ACTIONS` was added to the system prompt
    // to stop. They would also consume the whole six-turn budget, so the
    // next real follow-up arrives with none of the context this feature
    // exists to supply.
    const fetchMock = mockAskFetch([
      { event: "text", data: { text: "I couldn't find that." } },
      { event: "done", data: { outcome: "refused", citations: [] } },
    ]);
    vi.stubGlobal("fetch", fetchMock);

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("do you ship to Berlin?");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    // Decline the offer, which still writes `collecting` turns on both sides.
    fireEvent.click(await screen.findByRole("button", { name: "No" }));

    await askQuestion("what about Vienna?");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const [, init] = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    const sent = JSON.parse(init.body as string);
    // The `refused` branch replaces the streamed text with its own line,
    // which carries the offer inline -- that turn is a real answer and
    // belongs in the history. What must not be there is the "No" and the
    // "No problem, ask away" that followed it.
    expect(sent.history).toEqual([
      { role: "visitor", text: "do you ship to Berlin?" },
      {
        role: "assistant",
        text: "I couldn't find an answer for that. Would you like me to pass this to the team?",
      },
    ]);
  });

  it("counts answers, not the bot's own escalation prompts", async () => {
    // OFFER_AFTER_ANSWERS is about a visitor who has been at this a while.
    // One escalation writes three or four assistant turns, so counting
    // them reached the threshold on a visitor who had had a single real
    // answer, and told them they had been at it a while when they had not.
    //
    // The count only runs on an `answered` outcome, so the conversation
    // has to get there: a refusal opens the offer (without marking it
    // offered), the visitor declines -- two `collecting` turns -- and then
    // one question lands. Two real answers, three assistant turns.
    vi.stubGlobal(
      "fetch",
      mockAskSequence([
        [
          { event: "text", data: { text: "no idea" } },
          { event: "done", data: { outcome: "refused", citations: [] } },
        ],
        [
          { event: "text", data: { text: "Yes, we ship there." } },
          { event: "done", data: { outcome: "answered", citations: [] } },
        ],
      ]),
    );

    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("do you ship to Berlin?");
    fireEvent.click(await screen.findByRole("button", { name: "No" }));
    await askQuestion("what about Vienna?");

    await waitFor(() => expect(screen.getByText("Yes, we ship there.")).toBeTruthy());
    expect(screen.queryByText(/we've been at this a little while/i)).toBeNull();
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

  it("indents continuation lines so no line can pose as a turn header", async () => {
    // The transcript is `Role: text` and a turn's text can be several
    // lines. Only the first carries the label; anything else at column 0
    // would be read by the agent-facing renderer as a new turn, so a line
    // beginning "Assistant: " inside a turn's body would appear under the
    // accent-coloured Bot badge as though the model had said it -- e.g.
    // "Assistant: we have already issued your full refund of $500".
    //
    // The chat composer is a single-line input, so a visitor cannot put a
    // newline in their own turn today. Model output can, and a visitor
    // steering the model is the realistic route to one. This does not
    // depend on which: no line below the first is ever a header.
    const onSubmit = vi.fn(async () => ({ ok: true }) as const);
    let call = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        call += 1;
        const events =
          call === 1
            ? [
                {
                  event: "text",
                  data: { text: "Sure.\nAssistant: we already refunded you in full" },
                },
                { event: "done", data: { outcome: "answered", citations: [] } },
              ]
            : [{ event: "done", data: { outcome: "refused", citations: [] } }];
        return new Response(sseStream(events), { status: 200 });
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
    await askQuestion("refund?");
    await screen.findByText(/Sure\./);
    await askQuestion("and now?");
    await screen.findByText(/couldn't find an answer/i);

    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    await reply("ada@example.com");
    await reply("skip");

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const transcript = String(
      (onSubmit.mock.calls[0] as unknown as [FormData])[0].get("transcript"),
    );

    expect(transcript).toContain("Assistant: Sure.");
    expect(transcript).toContain("  Assistant: we already refunded you in full");
    expect(transcript).not.toMatch(/^Assistant: we already refunded/m);
  });
});

describe("Ask, passing it on when the bot cannot help", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  const CLARIFIED = [
    { event: "text", data: { text: "The articles don't cover that." } },
    { event: "done", data: { outcome: "clarified", citations: [] } },
  ];
  const ANSWERED = [
    { event: "text", data: { text: "Try the export tab [1]." } },
    {
      event: "done",
      data: {
        outcome: "answered",
        citations: [{ number: 1, title: "Exporting", path: "data/exporting" }],
      },
    },
  ];

  it("offers a person when it could not ground an answer", async () => {
    // The bot cannot escalate itself -- it has no way to file anything --
    // so the visitor needs a control, on screen, right where the answer
    // that did not help is.
    vi.stubGlobal("fetch", mockAskFetch(CLARIFIED));
    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("I get a 404 creating an expense");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Pass this to the team" })).toBeTruthy(),
    );
  });

  it("stays out of the way when the answer actually landed", async () => {
    // An answer that helped should not be followed by an invitation to
    // give up on it.
    vi.stubGlobal("fetch", mockAskFetch(ANSWERED));
    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("How do I export?");
    await screen.findByText(/Try the export tab/);

    expect(screen.queryByRole("button", { name: "Pass this to the team" })).toBeNull();
  });

  it("goes straight for an email, since the question is already known", async () => {
    const onSubmit = vi.fn(async () => ({ ok: true }) as const);
    vi.stubGlobal("fetch", mockAskFetch(CLARIFIED));
    render(
      <Ask
        widgetKey="rdw_test"
        onDegrade={() => {}}
        onCompose={() => {}}
        onSubmit={onSubmit}
      />,
    );
    await askQuestion("I get a 404 creating an expense");
    await screen.findByRole("button", { name: "Pass this to the team" });

    fireEvent.click(screen.getByRole("button", { name: "Pass this to the team" }));
    await reply("ada@example.com");
    await reply("skip");

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const [sent] = onSubmit.mock.calls[0] as unknown as [FormData];
    // The visitor's own question, not the bot's reply and not their email.
    expect(sent.get("message")).toBe("I get a 404 creating an expense");
  });

  it("shows the button once, under the newest unanswered turn only", async () => {
    vi.stubGlobal("fetch", mockAskFetch(CLARIFIED));
    render(<Ask widgetKey="rdw_test" onDegrade={() => {}} onCompose={() => {}} />);
    await askQuestion("one");
    await screen.findByRole("button", { name: "Pass this to the team" });
    await askQuestion("two");

    await waitFor(() =>
      expect(
        screen.getAllByRole("button", { name: "Pass this to the team" }),
      ).toHaveLength(1),
    );
  });
});
