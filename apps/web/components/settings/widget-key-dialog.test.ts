import { describe, expect, it, vi } from "vitest";

// widget-key-dialog.tsx imports the console's server actions module, which
// pulls in server-only code when run outside Next's own compiler (its
// "use server" functions have no meaning to plain Vitest) -- mocked out
// here the same way sibling dialog tests do, since this file only exercises
// parseOrigins and never touches either action.
vi.mock("@/app/(console)/settings/widget/actions", () => ({
  createWidgetKeyAction: vi.fn(),
  updateWidgetKeyAction: vi.fn(),
}));

import { parseOrigins } from "@/components/settings/widget-key-dialog";

describe("parseOrigins", () => {
  it("splits one origin per line", () => {
    expect(parseOrigins("https://acme.com\nhttps://app.acme.com")).toEqual([
      "https://acme.com",
      "https://app.acme.com",
    ]);
  });

  it("drops blank lines", () => {
    expect(parseOrigins("https://acme.com\n\nhttps://app.acme.com")).toEqual([
      "https://acme.com",
      "https://app.acme.com",
    ]);
  });

  it("ignores a trailing newline", () => {
    expect(parseOrigins("https://acme.com\n")).toEqual(["https://acme.com"]);
  });

  it("trims surrounding whitespace on each line", () => {
    expect(parseOrigins("  https://acme.com  \n\thttps://app.acme.com\t")).toEqual([
      "https://acme.com",
      "https://app.acme.com",
    ]);
  });

  it("round-trips a value the textarea would already hold", () => {
    // `WidgetKeyForm` seeds the textarea with `allowedOrigins.join("\n")`
    // on open -- parsing that straight back must reproduce the same list
    // untouched, or reopening the dialog on an existing embed would drift.
    const origins = ["https://acme.com", "https://app.acme.com"];
    expect(parseOrigins(origins.join("\n"))).toEqual(origins);
  });

  it("returns an empty list for blank input", () => {
    expect(parseOrigins("")).toEqual([]);
    expect(parseOrigins("   \n  \n")).toEqual([]);
  });
});
