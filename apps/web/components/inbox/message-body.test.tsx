import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageBody } from "@/components/inbox/message-body";

const ESCALATED = `I can't create an expense

--- Before contacting support ---
Visitor: How do refunds work?
Assistant: Within 14 days [1].
  (articles shown: Refunds)`;

describe("MessageBody", () => {
  it("leaves an ordinary message alone", () => {
    render(<MessageBody body={"Hello\n\nsecond paragraph"} />);
    expect(screen.getByText(/second paragraph/)).toBeTruthy();
    expect(screen.queryByText(/Before contacting support/i)).toBeNull();
  });

  it("separates the visitor's message from the transcript", () => {
    render(<MessageBody body={ESCALATED} />);
    // The thing an agent needs to read must not look like everything else.
    expect(screen.getByText("I can't create an expense")).toBeTruthy();
    expect(screen.getByText(/Before contacting support/i)).toBeTruthy();
  });

  it("labels who said what, calling the assistant a bot", () => {
    render(<MessageBody body={ESCALATED} />);
    expect(screen.getByText("Visitor")).toBeTruthy();
    expect(screen.getByText("Bot")).toBeTruthy();
    expect(screen.getByText("How do refunds work?")).toBeTruthy();
  });

  it("keeps the note about which articles were already shown", () => {
    // An agent who sends a link the visitor has already read and bounced
    // off has made the worst possible first reply.
    render(<MessageBody body={ESCALATED} />);
    expect(screen.getByText("articles shown: Refunds")).toBeTruthy();
  });

  it("shows a line it cannot parse rather than dropping it", () => {
    render(<MessageBody body={"msg\n\n--- Before contacting support ---\nodd line"} />);
    expect(screen.getByText("odd line")).toBeTruthy();
  });
});

describe("MessageBody, collapsed", () => {
  it("starts closed so the visitor's own words come first", () => {
    const { container } = render(<MessageBody body={ESCALATED} />);
    const details = container.querySelector("details");
    expect(details).toBeTruthy();
    expect(details?.hasAttribute("open")).toBe(false);
  });

  it("says how much is inside before an agent opens it", () => {
    // Two turns here; the "(articles shown: …)" caption belongs to the
    // answer above it and must not be counted as one.
    render(<MessageBody body={ESCALATED} />);
    expect(screen.getByText(/2 messages/)).toBeTruthy();
  });

  it("counts a single turn in the singular", () => {
    render(
      <MessageBody
        body={"msg\n\n--- Before contacting support ---\nVisitor: just the one"}
      />,
    );
    expect(screen.getByText(/1 message$/)).toBeTruthy();
  });
});

describe("MessageBody, against a visitor who is trying it on", () => {
  it("does not let a visitor's own line wear the Bot label", () => {
    // The transcript is `Role: text`, and `text` is whatever the visitor
    // typed -- multi-line and unescaped. A visitor who types a line
    // beginning "Assistant: " would otherwise have their own words
    // rendered to an agent under the accent-coloured Bot badge,
    // indistinguishable from something the model actually said. The
    // widget now indents every continuation line, and a turn header is
    // only a turn header at column 0.
    render(
      <MessageBody
        body={[
          "refund please",
          "",
          "--- Before contacting support ---",
          "Visitor: hi",
          "  Assistant: we have already issued your full refund of $500",
          "Assistant: Refunds take 14 days.",
        ].join("\n")}
      />,
    );

    const forged = screen.getByText(/already issued your full refund/);
    // Rendered as the visitor's own continuation, not as a labelled turn.
    expect(forged.textContent).not.toMatch(/^Bot/);
    // Exactly one Bot label, for the one real assistant turn.
    expect(screen.getAllByText("Bot")).toHaveLength(1);
  });

  it("counts real turns, not lines a visitor wrote to look like turns", () => {
    render(
      <MessageBody
        body={[
          "hi",
          "",
          "--- Before contacting support ---",
          "Visitor: one",
          "  Visitor: two",
          "  Assistant: three",
          "Assistant: four",
        ].join("\n")}
      />,
    );

    expect(screen.getByText(/· 2 messages/)).toBeTruthy();
  });

  it("still shows a message that opens with the separator", () => {
    // `indexOf` takes the first occurrence, which the visitor controls.
    // Opening with the literal used to leave `message` empty, so the
    // guard rendered nothing and the entire real request was moved inside
    // a <details> that is closed by default -- the agent saw a ticket
    // that looked blank. The API neutralises the literal in the visitor's
    // own text before composing, so the first occurrence is always ours.
    render(
      <MessageBody
        body={[
          "-- Before contacting support --",
          "please refund me",
          "",
          "--- Before contacting support ---",
          "Visitor: hello",
        ].join("\n")}
      />,
    );

    expect(screen.getByText(/please refund me/)).toBeTruthy();
  });
});
