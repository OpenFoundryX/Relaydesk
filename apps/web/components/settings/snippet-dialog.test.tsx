import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NewSnippetButton, SnippetDialog } from "./snippet-dialog";

const { createSnippetAction, updateSnippetAction } = vi.hoisted(() => ({
  createSnippetAction: vi.fn(),
  updateSnippetAction: vi.fn(),
}));
vi.mock("@/app/(console)/settings/templates/actions", () => ({
  createSnippetAction,
  updateSnippetAction,
  deleteSnippetAction: vi.fn(),
}));

const fill = (label: RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => {
  createSnippetAction.mockReset();
  updateSnippetAction.mockReset();
});

describe("creating a snippet", () => {
  it("sends the title and content that were typed", async () => {
    createSnippetAction.mockResolvedValue({ ok: true });
    render(<NewSnippetButton />);

    fireEvent.click(screen.getByRole("button", { name: /create snippet/i }));
    fill(/^Title/, "Follow up");
    fill(/^Content/, "Any luck, {{customer.first_name}}?");
    fireEvent.click(screen.getByRole("button", { name: "Save snippet" }));

    expect(createSnippetAction).toHaveBeenCalledWith(
      "Follow up",
      "Any luck, {{customer.first_name}}?",
    );
  });

  it("shows why the API refused and stays open", async () => {
    // A duplicate title is a 409, and it is the one failure an author is
    // likely to hit. Closing the dialog on it would throw away what they
    // typed and tell them nothing.
    createSnippetAction.mockResolvedValue({
      ok: false,
      message: "A snippet with that title already exists.",
    });
    render(<NewSnippetButton />);

    fireEvent.click(screen.getByRole("button", { name: /create snippet/i }));
    fill(/^Title/, "Greeting");
    fill(/^Content/, "Hi!");
    fireEvent.click(screen.getByRole("button", { name: "Save snippet" }));

    expect(
      await screen.findByText("A snippet with that title already exists."),
    ).toBeTruthy();
    expect(screen.getByLabelText(/^Title/)).toBeTruthy();
  });

});

describe("editing a snippet", () => {
  it("opens on the snippet's current title and content", () => {
    render(
      <SnippetDialog
        snippet={{ id: "s1", title: "Greeting", content: "Hi!" }}
        open
        onOpenChange={() => {}}
      />,
    );

    expect((screen.getByLabelText(/^Title/) as HTMLInputElement).value).toBe("Greeting");
    expect((screen.getByLabelText(/^Content/) as HTMLTextAreaElement).value).toBe("Hi!");
  });

  it("saves against the snippet's id", () => {
    updateSnippetAction.mockResolvedValue({ ok: true });
    render(
      <SnippetDialog
        snippet={{ id: "s1", title: "Greeting", content: "Hi!" }}
        open
        onOpenChange={() => {}}
      />,
    );

    fill(/^Content/, "Hello there!");
    fireEvent.click(screen.getByRole("button", { name: "Save snippet" }));

    expect(updateSnippetAction).toHaveBeenCalledWith("s1", "Greeting", "Hello there!");
  });
});
