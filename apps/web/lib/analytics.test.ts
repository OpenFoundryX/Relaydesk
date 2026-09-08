import { describe, expect, it } from "vitest";

import { safeAssignee, safeRange } from "@/lib/analytics";

const team = [
  { id: "11111111-1111-1111-1111-111111111111" },
  { id: "22222222-2222-2222-2222-222222222222" },
];

describe("safeRange", () => {
  it("keeps a range the API knows", () => {
    expect(safeRange("90d")).toBe("90d");
  });

  it("falls back rather than handing the API something it will refuse", () => {
    expect(safeRange("all-time")).toBe("30d");
    expect(safeRange(undefined)).toBe("30d");
  });
});

describe("safeAssignee", () => {
  it("keeps a teammate who is still on the roster", () => {
    expect(safeAssignee(team[0].id, team)).toBe(team[0].id);
  });

  it("keeps the unassigned bucket, which is nobody's user id", () => {
    expect(safeAssignee("unassigned", team)).toBe("unassigned");
  });

  it("drops a teammate who has left the workspace", () => {
    // The bookmarked-link case. The API 422s an assignee it does not
    // recognise, and that reaches the reader as the console error boundary
    // -- "the change may not have been saved" on a page that saves nothing,
    // and a Try again button that re-renders into the same 422. All
    // assignees is correct, complete data with the select saying so.
    expect(safeAssignee("33333333-3333-3333-3333-333333333333", team)).toBeNull();
  });

  it("drops a hand-edited query string", () => {
    expect(safeAssignee("me", team)).toBeNull();
    expect(safeAssignee("", team)).toBeNull();
    expect(safeAssignee(undefined, team)).toBeNull();
  });
});
