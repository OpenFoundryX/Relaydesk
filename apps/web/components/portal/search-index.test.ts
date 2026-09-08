import { describe, expect, it } from "vitest";

import { buildSearchIndex, searchArticles, type SearchEntry } from "./search-index";

const entries: SearchEntry[] = [
  {
    id: "1",
    title: "Creating expenses",
    excerpt: "How to file an expense.",
    path: "for-spenders/expenses/creating-expenses",
    collections: ["For spenders", "Expenses"],
  },
  {
    id: "2",
    title: "Create a mileage expense",
    excerpt: "Claiming for a journey you drove.",
    path: "for-spenders/expenses/create-a-mileage-expense",
    collections: ["For spenders", "Expenses"],
  },
  {
    id: "3",
    title: "Add a receipt",
    excerpt: "Attach the paperwork to a mileage claim after the fact.",
    path: "for-spenders/expenses/add-a-receipt",
    collections: ["For spenders", "Expenses"],
  },
  {
    id: "4",
    title: "Approve a report",
    excerpt: "Acting on a report.",
    path: "for-approvers/approve-a-report",
    collections: ["For approvers"],
  },
];

const index = buildSearchIndex(entries);
const titles = (query: string) => searchArticles(index, query).map((r) => r.title);

describe("searchArticles", () => {
  it("finds an article by a word in its title", () => {
    expect(titles("receipt")).toContain("Add a receipt");
  });

  it("matches while the word is still being typed", () => {
    // The whole point of scoring locally: results appear mid-word, with no
    // round trip to wait on.
    expect(titles("expen")).toContain("Creating expenses");
  });

  it("ranks a title match above a body-text match on the same word", () => {
    const ranked = titles("mileage");

    expect(ranked.indexOf("Create a mileage expense")).toBeLessThan(
      ranked.indexOf("Add a receipt"),
    );
  });

  it("ranks the article that covers the whole query first", () => {
    // The failure this exists to prevent: scoring each term on its own lets
    // a common word carry the wrong article to the top. "expense" is in
    // half the index, so summing per-term points puts "Creating expenses"
    // level with the article that actually answers the question.
    expect(titles("mileage expense")[0]).toBe("Create a mileage expense");
  });

  it("penalises an article that matches only part of the query", () => {
    const results = searchArticles(index, "mileage expense");
    const best = results.find((r) => r.title === "Create a mileage expense");
    const partial = results.find((r) => r.title === "Creating expenses");

    if (!best || !partial) throw new Error("expected both articles to match");
    expect(best.score).toBeGreaterThan(partial.score * 2);
  });

  it("matches on the collection an article sits in", () => {
    // People describe an article by where it lives as often as by its name.
    expect(titles("approvers")).toContain("Approve a report");
  });

  it("ignores case and punctuation", () => {
    expect(titles("  ADD, A RECEIPT!  ")).toContain("Add a receipt");
  });

  it("returns nothing for a query that matches nothing", () => {
    expect(searchArticles(index, "kubernetes")).toEqual([]);
  });

  it("returns nothing for an empty query rather than everything", () => {
    expect(searchArticles(index, "   ")).toEqual([]);
  });

  it("caps how many results it returns", () => {
    expect(searchArticles(index, "a", 2)).toHaveLength(2);
  });
});
