import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReplyComposer } from "./reply-composer";
import type { SnippetContext } from "@/lib/snippets/render";
import type { Snippet } from "@/lib/types";

const { sendReplyAction, discardDraftAction } = vi.hoisted(() => ({
  sendReplyAction: vi.fn(),
  discardDraftAction: vi.fn(),
}));
vi.mock("@/app/(console)/conversations/actions", () => ({
  sendReplyAction,
  discardDraftAction,
}));

const snippets: Snippet[] = [
  { id: "1", title: "Follow up", content: "Any luck, {{customer.first_name}}?" },
  { id: "2", title: "Greeting", content: "Hi {{customer.first_name}}!" },
  { id: "3", title: "Issue resolved", content: "Glad that is sorted." },
];

const snippetContext: SnippetContext = {
  customerName: "Priya Raman",
  customerEmail: "priya@northwind.io",
  ticketNumber: 412,
  ticketSubject: "Checkout fails with a 402",
  agentName: "Nilesh Pant",
  workspaceName: "Chronon",
};

function setup() {
  render(
    <ReplyComposer
      conversationId="c1"
      customerEmail="priya@northwind.io"
      from="support@chronon.co"
      draft={null}
      snippets={snippets}
      snippetContext={snippetContext}
    />,
  );
  return screen.getByLabelText("Reply") as HTMLTextAreaElement;
}

/** Type into the textarea and put the caret where a person's would be. */
function type(field: HTMLTextAreaElement, value: string, caret = value.length) {
  fireEvent.change(field, { target: { value, selectionStart: caret } });
}

beforeEach(() => {
  sendReplyAction.mockReset();
  discardDraftAction.mockReset();
});

describe("the snippet menu", () => {
  it("opens on a slash and lists every snippet", () => {
    const field = setup();

    type(field, "/");

    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Follow up",
      "Greeting",
      "Issue resolved",
    ]);
  });

  it("narrows to what has been typed after the slash", () => {
    const field = setup();

    type(field, "/gre");

    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Greeting",
    ]);
  });

  it("stays shut when the slash is part of a URL", () => {
    const field = setup();

    type(field, "See https://example.com/help");

    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("closes and offers nothing when no title matches", () => {
    const field = setup();

    type(field, "/zzz");

    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("inserts the snippet with its variables filled in", () => {
    const field = setup();
    type(field, "/gre");

    fireEvent.click(screen.getByRole("option", { name: "Greeting" }));

    expect(field.value).toBe("Hi Priya!");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("keeps the reply written either side of the trigger", () => {
    const field = setup();
    type(field, "Morning. /gre");

    fireEvent.click(screen.getByRole("option", { name: "Greeting" }));

    expect(field.value).toBe("Morning. Hi Priya!");
  });

  it("inserts the highlighted snippet on Enter instead of a newline", () => {
    const field = setup();
    type(field, "/gre");

    fireEvent.keyDown(field, { key: "Enter" });

    expect(field.value).toBe("Hi Priya!");
    expect(field.value).not.toContain("\n");
  });

  it("moves the highlight with the arrow keys", () => {
    const field = setup();
    type(field, "/");

    fireEvent.keyDown(field, { key: "ArrowDown" });
    fireEvent.keyDown(field, { key: "Enter" });

    expect(field.value).toBe("Hi Priya!");
  });

  it("closes on Escape and leaves the typed text alone", () => {
    const field = setup();
    type(field, "/gre");

    fireEvent.keyDown(field, { key: "Escape" });

    expect(screen.queryByRole("listbox")).toBeNull();
    expect(field.value).toBe("/gre");
  });

  it("never sends while the menu is open", () => {
    // Enter is the menu's key for as long as it is open. Nothing here may
    // reach the send action, which is what a reply half-composed around a
    // `/gre` would be.
    const field = setup();
    type(field, "/gre");

    fireEvent.keyDown(field, { key: "Enter" });

    expect(sendReplyAction).not.toHaveBeenCalled();
  });
});

describe("the composer itself", () => {
  it("still sends the typed reply", () => {
    const field = setup();

    type(field, "Sorted, thanks.");
    fireEvent.click(screen.getByRole("button", { name: "Send reply" }));

    expect(sendReplyAction).toHaveBeenCalledWith("c1", "Sorted, thanks.", false);
  });
});
