import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { articleHeadings } from "@/components/portal/headings";

import { DocRenderer } from "./doc-renderer";

const src = (id: string) => `/api/kb/images/${id}`;

const doc = (...content: unknown[]) => ({ type: "doc", content });
const para = (text: string) => ({
  type: "paragraph",
  content: [{ type: "text", text }],
});

describe("DocRenderer", () => {
  it("renders paragraphs in order", () => {
    render(<DocRenderer doc={doc(para("First."), para("Second."))} imageSrc={src} />);

    expect(screen.getByText("First.")).toBeDefined();
    expect(screen.getByText("Second.")).toBeDefined();
  });

  it("renders nested lists", () => {
    render(
      <DocRenderer
        doc={doc({
          type: "bulletList",
          content: [{ type: "listItem", content: [para("Alpha")] }],
        })}
        imageSrc={src}
      />,
    );

    expect(screen.getByRole("listitem").textContent).toBe("Alpha");
  });

  it("renders a list nested inside another list's item", () => {
    render(
      <DocRenderer
        doc={doc({
          type: "bulletList",
          content: [
            {
              type: "listItem",
              content: [
                para("Parent"),
                {
                  type: "bulletList",
                  content: [{ type: "listItem", content: [para("Child")] }],
                },
              ],
            },
          ],
        })}
        imageSrc={src}
      />,
    );

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);

    const child = screen.getByText("Child");
    // The nested <ul><li> must actually be inside the parent <li>, not a
    // sibling produced by a flattened render.
    expect(items[0].contains(child)).toBe(true);
  });

  it("renders an unknown node as nothing, without dropping its siblings", () => {
    render(
      <DocRenderer
        doc={doc(para("Before"), { type: "somethingNew" }, para("After"))}
        imageSrc={src}
      />,
    );

    expect(screen.getByText("Before")).toBeDefined();
    expect(screen.getByText("After")).toBeDefined();
  });

  it("renders a link's text but never a javascript: href", () => {
    render(
      <DocRenderer
        doc={doc({
          type: "paragraph",
          content: [
            {
              type: "text",
              text: "click me",
              marks: [{ type: "link", attrs: { href: "javascript:alert(1)" } }],
            },
          ],
        })}
        imageSrc={src}
      />,
    );

    const link = screen.queryByRole("link");
    expect(link?.getAttribute("href") ?? "").not.toContain("javascript:");
  });

  it("builds image sources through the provided resolver", () => {
    render(
      <DocRenderer
        doc={doc({ type: "image", attrs: { id: "abc", alt: "A screenshot" } })}
        imageSrc={src}
      />,
    );

    expect(screen.getByAltText("A screenshot").getAttribute("src")).toBe(
      "/api/kb/images/abc",
    );
  });

  it("renders nothing for a malformed document rather than throwing", () => {
    render(<DocRenderer doc={{} as never} imageSrc={src} />);
    render(<DocRenderer doc={{ type: "doc", content: "nope" } as never} imageSrc={src} />);
  });

  it("drops an unknown node's children rather than leaking them through a fallback", () => {
    render(
      <DocRenderer
        doc={doc({
          type: "somethingNew",
          content: [para("Should not appear")],
        })}
        imageSrc={src}
      />,
    );

    expect(screen.queryByText("Should not appear")).toBeNull();
  });

  it.each([
    ["uppercase", "JAVASCRIPT:alert(1)"],
    ["leading whitespace", "   javascript:alert(1)"],
    ["a leading control character", "\rjavascript:alert(1)"],
    ["an embedded tab", "java\tscript:alert(1)"],
    ["data: HTML", "data:text/html,<script>alert(1)</script>"],
    ["vbscript:", "vbscript:msgbox(1)"],
  ])("never links a %s javascript-equivalent href", (_label, href) => {
    render(
      <DocRenderer
        doc={doc({
          type: "paragraph",
          content: [{ type: "text", text: "click me", marks: [{ type: "link", attrs: { href } }] }],
        })}
        imageSrc={src}
      />,
    );

    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("click me")).toBeDefined();
  });

  it("keeps a safe link's href and marks it noopener noreferrer", () => {
    render(
      <DocRenderer
        doc={doc({
          type: "paragraph",
          content: [
            {
              type: "text",
              text: "docs",
              marks: [{ type: "link", attrs: { href: "https://example.com/docs" } }],
            },
          ],
        })}
        imageSrc={src}
      />,
    );

    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("https://example.com/docs");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it.each([
    ["a same-hub path", "/docs/refunds", "/docs/refunds"],
    ["an in-page fragment", "#section", "#section"],
  ])("keeps a relative %s link working rather than absolutizing it", (_label, href, expected) => {
    render(
      <DocRenderer
        doc={doc({
          type: "paragraph",
          content: [{ type: "text", text: "click me", marks: [{ type: "link", attrs: { href } }] }],
        })}
        imageSrc={src}
      />,
    );

    expect(screen.getByRole("link").getAttribute("href")).toBe(expected);
  });

  it.each([
    ["protocol-relative to another host", "//evil.example/x"],
    ["backslash-disguised host", "/\\evil.example/x"],
  ])("resolves a %s href fully rather than rendering it as same-hub", (_label, href) => {
    render(
      <DocRenderer
        doc={doc({
          type: "paragraph",
          content: [{ type: "text", text: "click me", marks: [{ type: "link", attrs: { href } }] }],
        })}
        imageSrc={src}
      />,
    );

    const rendered = screen.getByRole("link").getAttribute("href") ?? "";
    // Whatever comes out must be the fully resolved external URL (still
    // http/https, still validated), never the raw "//" or "\" input treated
    // as if it were a same-hub path.
    expect(rendered).toMatch(/^https:\/\/evil\.example\//);
  });

  it.each([
    ["a node with no type", { content: [para("x")] }],
    ["a node whose type is not a string", { type: 42, content: [para("x")] }],
    ["null in place of a node", null],
    ["a deeply nested malformed structure", { type: "doc", content: [{ type: "doc", content: [{ type: "doc", content: null }] }] }],
    ["attrs that is a string instead of an object", { type: "image", attrs: "not-an-object" }],
    ["a heading with no attrs", { type: "heading", content: [{ type: "text", text: "Untitled" }] }],
  ])("renders %s without throwing", (_label, node) => {
    expect(() =>
      render(<DocRenderer doc={doc(node)} imageSrc={src} />),
    ).not.toThrow();
  });

  it("never turns node attrs into arbitrary DOM attributes or event handlers", () => {
    const { container } = render(
      <DocRenderer
        doc={doc({
          type: "paragraph",
          attrs: { onclick: "alert(1)", style: "background:red", id: "injected" },
          content: [{ type: "text", text: "Safe text" }],
        } as never)}
        imageSrc={src}
      />,
    );

    const p = container.querySelector("p");
    expect(p?.getAttribute("onclick")).toBeNull();
    expect(p?.getAttribute("style")).toBeNull();
    expect(p?.id).toBe("");
  });

  it("puts the table of contents' anchor on the heading itself", () => {
    // The id the contents list links to and the id the heading carries are
    // the same value from one pass over the document -- see
    // components/portal/headings.ts.
    const doc_ = doc({
      type: "heading",
      attrs: { level: 2 },
      content: [{ type: "text", text: "What is a POS terminal?" }],
    });
    const headings = articleHeadings(doc_);

    render(
      <DocRenderer doc={doc_} imageSrc={src} headingId={headings.idFor} />,
    );

    expect(
      screen.getByRole("heading", { name: "What is a POS terminal?" }).id,
    ).toBe(headings.list[0].id);
  });

  it("renders a heading with no id when none is offered", () => {
    // The console editor's preview renders the same component without a
    // contents list beside it.
    render(
      <DocRenderer
        doc={doc({
          type: "heading",
          attrs: { level: 2 },
          content: [{ type: "text", text: "Plain" }],
        })}
        imageSrc={src}
      />,
    );

    expect(screen.getByRole("heading", { name: "Plain" }).id).toBe("");
  });
});
