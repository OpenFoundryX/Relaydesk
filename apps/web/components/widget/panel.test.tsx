import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
