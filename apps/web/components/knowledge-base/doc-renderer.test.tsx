import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
});
