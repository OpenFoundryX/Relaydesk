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

import {
  buildSettingsInput,
  isValidAccentColour,
  parseOrigins,
} from "@/components/settings/widget-key-dialog";

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

describe("buildSettingsInput", () => {
  const blank = { name: "", greeting: "", accentColour: "", position: "right" as const };

  it("omits every field left blank -- absent means today's behaviour", () => {
    expect(buildSettingsInput(blank)).toEqual({});
  });

  it("trims and includes only the fields given", () => {
    expect(
      buildSettingsInput({ ...blank, name: "  Acme Support  ", greeting: " Hi! " }),
    ).toEqual({ name: "Acme Support", greeting: "Hi!" });
  });

  it("includes the accent colour when set", () => {
    expect(buildSettingsInput({ ...blank, accentColour: "#4F46E5" })).toEqual({
      accentColour: "#4F46E5",
    });
  });

  it("omits position when it is 'right', the default", () => {
    expect(buildSettingsInput({ ...blank, position: "right" })).toEqual({});
  });

  it("includes position only when it is 'left'", () => {
    expect(buildSettingsInput({ ...blank, position: "left" })).toEqual({
      position: "left",
    });
  });
});

describe("isValidAccentColour", () => {
  it("accepts an empty value -- accent colour is optional", () => {
    expect(isValidAccentColour("")).toBe(true);
    expect(isValidAccentColour("   ")).toBe(true);
  });

  it("accepts 3- and 6-digit hex colours", () => {
    expect(isValidAccentColour("#fff")).toBe(true);
    expect(isValidAccentColour("#4F46E5")).toBe(true);
  });

  it("rejects a non-hex value", () => {
    // The colour lands in an inline style on a stranger's page (D5/D6) --
    // an unvalidated value there is an injection surface.
    expect(isValidAccentColour("red")).toBe(false);
    expect(isValidAccentColour("javascript:alert(1)")).toBe(false);
  });
});
