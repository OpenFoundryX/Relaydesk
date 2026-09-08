import { describe, expect, it } from "vitest";

import { matchSnippets } from "./match";
import type { Snippet } from "@/lib/types";

const snippets: Snippet[] = [
  { id: "1", title: "Follow up", content: "..." },
  { id: "2", title: "Greeting", content: "..." },
  { id: "3", title: "Issue resolved", content: "..." },
  { id: "4", title: "Request more info", content: "..." },
];

const titles = (query: string) => matchSnippets(snippets, query).map((s) => s.title);

describe("matchSnippets", () => {
  it("offers everything before anything is typed", () => {
    expect(titles("")).toEqual([
      "Follow up",
      "Greeting",
      "Issue resolved",
      "Request more info",
    ]);
  });

  it("matches a prefix regardless of case", () => {
    expect(titles("gre")).toEqual(["Greeting"]);
    expect(titles("GRE")).toEqual(["Greeting"]);
  });

  it("matches a word later in the title", () => {
    // Titles are phrases, and the word an agent reaches for is often not
    // the first one — "/resolved" should find "Issue resolved".
    expect(titles("resolved")).toEqual(["Issue resolved"]);
  });

  it("puts a title that starts with the query first", () => {
    const ranked = matchSnippets(
      [
        { id: "1", title: "Escalate to billing", content: "..." },
        { id: "2", title: "Billing question", content: "..." },
      ],
      "billing",
    );

    expect(ranked.map((s) => s.title)).toEqual([
      "Billing question",
      "Escalate to billing",
    ]);
  });

  it("returns nothing when the query matches no title", () => {
    expect(titles("zzz")).toEqual([]);
  });
});
