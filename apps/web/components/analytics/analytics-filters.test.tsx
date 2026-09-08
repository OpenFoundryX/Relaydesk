import { describe, expect, it } from "vitest";

import { filterHref } from "./analytics-filters";

// Radix's `Select` opens on `pointerdown`, which jsdom does not synthesise
// from a click, so driving it in a test is unreliable. `filterHref` is the
// pure routing decision underneath `onValueChange` -- testing it directly is
// a smaller and more honest unit than a Radix interaction.
describe("filterHref", () => {
  it("puts a non-default range in the query", () => {
    expect(filterHref("/analytics", "7d", null)).toBe("/analytics?range=7d");
  });

  it("omits the default range so the common case is a clean pathname", () => {
    expect(filterHref("/analytics", "30d", null)).toBe("/analytics");
  });

  it("includes an assignee in the query", () => {
    expect(filterHref("/analytics", "30d", "u1")).toBe("/analytics?assignee=u1");
  });

  it("returns a bare pathname when no filters are set", () => {
    expect(filterHref("/analytics", "30d", null)).toBe("/analytics");
  });

  it("combines a non-default range and an assignee", () => {
    expect(filterHref("/analytics", "7d", "u1")).toBe(
      "/analytics?range=7d&assignee=u1",
    );
  });
});
