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
