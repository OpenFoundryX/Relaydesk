import { describe, expect, it } from "vitest";

import { articleHeadings } from "./headings";

function doc(...content: unknown[]) {
  return { type: "doc", content };
}

function heading(level: number, text: string) {
  return {
    type: "heading",
    attrs: { level },
    content: [{ type: "text", text }],
  };
}

describe("articleHeadings", () => {
  it("collects the headings a reader can jump to, in document order", () => {
    const parsed = articleHeadings(
      doc(heading(2, "What is a POS terminal?"), heading(3, "Where to find it")),
    );

    expect(parsed.list).toEqual([
      { id: "what-is-a-pos-terminal", text: "What is a POS terminal?", level: 2 },
      { id: "where-to-find-it", text: "Where to find it", level: 3 },
    ]);
  });

  it("ignores h1 -- the article's title is the page's only h1", () => {
    const parsed = articleHeadings(doc(heading(1, "Title"), heading(2, "Real")));

    expect(parsed.list.map((h) => h.text)).toEqual(["Real"]);
  });

  it("gives two headings with the same words two different ids", () => {
    // Both would otherwise be `#overview`, and every link to the second one
    // would scroll to the first.
    const parsed = articleHeadings(doc(heading(2, "Overview"), heading(2, "Overview")));

    expect(parsed.list.map((h) => h.id)).toEqual(["overview", "overview-2"]);
  });

  it("skips a heading with nothing to show, but keeps one that slugifies to nothing", () => {
    // A blank heading has no row to put in a contents list. "!!!" does --
    // and it needs a positional id, because an empty one would be dropped
    // from the DOM and its row would scroll nowhere.
    const parsed = articleHeadings(doc(heading(2, "   "), heading(2, "!!!")));

    expect(parsed.list).toEqual([{ id: "section-1", text: "!!!", level: 2 }]);
  });

  it("gives the renderer the same id it gave the list, for the same node", () => {
    // This is the whole point of the module: the anchor the TOC links to
    // and the id the heading is rendered with come from one pass, so they
    // cannot disagree.
    const node = heading(2, "Overview");
    const parsed = articleHeadings(doc(node));

    expect(parsed.idFor(node)).toBe(parsed.list[0].id);
  });

  it("survives a document that is not shaped like one", () => {
    // The doc is authored content read by anonymous visitors; it is never
    // assumed to be well formed.
    expect(articleHeadings(null).list).toEqual([]);
    expect(articleHeadings({ content: "not an array" }).list).toEqual([]);
    expect(articleHeadings(doc({ type: "heading" })).list).toEqual([]);
  });
});
