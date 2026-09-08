import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PortalSearch } from "./portal-search";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push }),
}));

const INDEX = [
  {
    id: "1",
    title: "Add a receipt",
    excerpt: "Attach the paperwork.",
    path: "for-spenders/expenses/add-a-receipt",
    collections: ["For spenders", "Expenses"],
  },
  {
    id: "2",
    title: "Approve a report",
    excerpt: "Acting on a report.",
    path: "for-approvers/approve-a-report",
    collections: ["For approvers"],
  },
];

beforeEach(() => {
  push.mockClear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => INDEX })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PortalSearch", () => {
  it("stays a plain GET form, so search works without JavaScript", () => {
    // The results page is the fallback for everything the browser index
    // cannot answer -- article bodies -- and the only search a visitor with
    // no JavaScript has at all.
    const { container } = render(<PortalSearch />);
    const form = container.querySelector("form");

    expect(form?.getAttribute("action")).toBe("/help/search");
    expect(form?.getAttribute("method")).not.toBe("post");
  });

  it("shows no results until something is typed", () => {
    render(<PortalSearch />);

    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("suggests matching articles as you type", async () => {
    render(<PortalSearch />);
    const box = screen.getByRole("combobox");

    fireEvent.focus(box);
    fireEvent.change(box, { target: { value: "receipt" } });

    const option = await screen.findByRole("option", { name: /Add a receipt/ });
    expect(option.querySelector("a")?.getAttribute("href")).toBe(
      "/help/for-spenders/expenses/add-a-receipt",
    );
  });

  it("fetches the index once, however much is typed", async () => {
    render(<PortalSearch />);
    const box = screen.getByRole("combobox");

    fireEvent.focus(box);
    fireEvent.change(box, { target: { value: "receipt" } });
    await screen.findByRole("option", { name: /Add a receipt/ });
    fireEvent.change(box, { target: { value: "receipt again" } });

    await waitFor(() => expect(vi.mocked(fetch).mock.calls.length).toBe(1));
  });

  it("does not fetch anything until the reader shows an interest", () => {
    // A visitor who reads one article and leaves should not pay for an
    // index they never used.
    render(<PortalSearch />);

    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });

  it("opens the highlighted article on Enter", async () => {
    render(<PortalSearch />);
    const box = screen.getByRole("combobox");

    fireEvent.focus(box);
    fireEvent.change(box, { target: { value: "receipt" } });
    await screen.findByRole("option", { name: /Add a receipt/ });
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "Enter" });

    expect(push).toHaveBeenCalledWith("/help/for-spenders/expenses/add-a-receipt");
  });

  it("closes the suggestions on Escape", async () => {
    render(<PortalSearch />);
    const box = screen.getByRole("combobox");

    fireEvent.focus(box);
    fireEvent.change(box, { target: { value: "receipt" } });
    await screen.findByRole("option", { name: /Add a receipt/ });
    fireEvent.keyDown(box, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
  });

  it("says so when nothing matches, rather than showing an empty box", async () => {
    render(<PortalSearch />);
    const box = screen.getByRole("combobox");

    fireEvent.focus(box);
    fireEvent.change(box, { target: { value: "kubernetes" } });

    expect(await screen.findByText(/No articles match/)).toBeDefined();
  });
});
