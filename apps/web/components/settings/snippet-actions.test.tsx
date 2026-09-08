import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnippetActions } from "./snippet-actions";

const { deleteSnippetAction } = vi.hoisted(() => ({
  deleteSnippetAction: vi.fn(),
}));
vi.mock("@/app/(console)/settings/templates/actions", () => ({
  deleteSnippetAction,
  createSnippetAction: vi.fn(),
  updateSnippetAction: vi.fn(),
}));

const snippet = { id: "s1", title: "Greeting", content: "Hi!" };

beforeEach(() => {
  deleteSnippetAction.mockReset();
});

describe("SnippetActions", () => {
  it("opens the edit dialog on the snippet's current text", () => {
    render(<SnippetActions snippet={snippet} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit Greeting" }));

    expect((screen.getByLabelText(/^Content/) as HTMLTextAreaElement).value).toBe("Hi!");
  });

  it("deletes by id", () => {
    deleteSnippetAction.mockResolvedValue({ ok: true });
    render(<SnippetActions snippet={snippet} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete Greeting" }));

    expect(deleteSnippetAction).toHaveBeenCalledWith("s1");
  });

  it("reports a refused delete rather than looking like it worked", async () => {
    deleteSnippetAction.mockResolvedValue({
      ok: false,
      message: "This action requires an admin.",
    });
    render(<SnippetActions snippet={snippet} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete Greeting" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "This action requires an admin.",
    );
  });
});
