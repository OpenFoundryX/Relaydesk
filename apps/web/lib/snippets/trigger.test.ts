import { describe, expect, it } from "vitest";

import { applySnippet, snippetTrigger } from "./trigger";

describe("snippetTrigger", () => {
  it("opens on a slash at the very start of an empty reply", () => {
    expect(snippetTrigger("/", 1)).toEqual({ query: "", start: 0, end: 1 });
  });

  it("carries the word typed after the slash as the query", () => {
    expect(snippetTrigger("/fol", 4)).toEqual({ query: "fol", start: 0, end: 4 });
  });

  it("opens mid-sentence when the slash follows a space", () => {
    expect(snippetTrigger("Hi /fol", 7)).toEqual({ query: "fol", start: 3, end: 7 });
  });

  it("opens at the start of a new line", () => {
    expect(snippetTrigger("Hi\n/fol", 7)).toEqual({ query: "fol", start: 3, end: 7 });
  });

  it("stays shut inside a URL", () => {
    // The single most common way a slash gets typed into a support reply.
    // Requiring whitespace before it is what keeps the menu out of the way.
    expect(snippetTrigger("See https://example.com/help", 28)).toBeNull();
  });

  it("stays shut when there is no slash at all", () => {
    expect(snippetTrigger("Hi there", 8)).toBeNull();
  });

  it("closes once a space is typed after the query", () => {
    // Titles have spaces in them, but the query must not: something has to
    // end the trigger, and the space is what an agent types when they meant
    // to write a literal slash and carried on.
    expect(snippetTrigger("/fol lowup", 10)).toBeNull();
  });

  it("ignores a slash that sits after the caret", () => {
    expect(snippetTrigger("/fol", 0)).toBeNull();
  });

  it("tracks the slash nearest the caret", () => {
    expect(snippetTrigger("/one /two", 9)).toEqual({ query: "two", start: 5, end: 9 });
  });

  it("reads the query up to the caret, not to the end of the text", () => {
    // The agent moved the caret back into a word they had already typed.
    expect(snippetTrigger("/follow", 4)).toEqual({ query: "fol", start: 0, end: 4 });
  });
});

describe("applySnippet", () => {
  it("replaces the trigger with the snippet and leaves the caret after it", () => {
    const trigger = snippetTrigger("/fol", 4)!;

    expect(applySnippet("/fol", trigger, "Just checking in")).toEqual({
      value: "Just checking in",
      caret: 16,
    });
  });

  it("keeps the text on both sides of the trigger", () => {
    const trigger = snippetTrigger("Hi /fol!", 7)!;

    expect(applySnippet("Hi /fol!", trigger, "there")).toEqual({
      value: "Hi there!",
      caret: 8,
    });
  });

  it("inserts a multi-line snippet whole", () => {
    const trigger = snippetTrigger("/sig", 4)!;

    expect(applySnippet("/sig", trigger, "Thanks,\nNilesh")).toEqual({
      value: "Thanks,\nNilesh",
      caret: 14,
    });
  });
});
