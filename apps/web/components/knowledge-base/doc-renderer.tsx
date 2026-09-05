import type { ReactNode } from "react";

// A ProseMirror document node: `type` selects a renderer from the table
// below, `content` holds child nodes, and `attrs`/`marks`/`text` carry
// node-specific data. Everything here is untrusted — it was authored by a
// workspace member and, once published, is read by anonymous visitors — so
// every field is read defensively rather than assumed to be shaped right.
type DocNodeShape = {
  type?: unknown;
  content?: unknown;
  attrs?: unknown;
  marks?: unknown;
  text?: unknown;
};

type MarkShape = {
  type?: unknown;
  attrs?: unknown;
};

export type DocRendererProps = {
  doc: unknown;
  imageSrc: (id: string) => string;
};

// A link href comes from the editor, but the editor is a text field and a
// member could paste anything. Only http, https, and mailto survive.
const SAFE_PROTOCOLS = ["http:", "https:", "mailto:"];

function safeHref(href: unknown): string | undefined {
  if (typeof href !== "string") return undefined;
  try {
    return SAFE_PROTOCOLS.includes(new URL(href, "https://x.invalid").protocol)
      ? href
      : undefined;
  } catch {
    return undefined;
  }
}

function asAttrs(attrs: unknown): Record<string, unknown> {
  return attrs && typeof attrs === "object" ? (attrs as Record<string, unknown>) : {};
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function children(node: DocNodeShape, imageSrc: (id: string) => string): ReactNode {
  return Array.isArray(node.content)
    ? node.content.map((child, i) => (
        <DocNode key={i} node={child} imageSrc={imageSrc} />
      ))
    : null;
}

// Wraps a text node's rendered content with its marks, innermost first, so
// e.g. bold + link nests the bold text inside the anchor.
function applyMarks(content: ReactNode, marks: unknown): ReactNode {
  if (!Array.isArray(marks)) return content;

  return marks.reduce((acc: ReactNode, mark: unknown, i: number) => {
    const shape = mark as MarkShape;
    const attrs = asAttrs(shape.attrs);

    switch (shape.type) {
      case "bold":
        return <strong key={i}>{acc}</strong>;
      case "italic":
        return <em key={i}>{acc}</em>;
      case "code":
        return <code key={i}>{acc}</code>;
      case "link": {
        const href = safeHref(attrs.href);
        if (!href) return acc;
        return (
          <a key={i} href={href} rel="noopener noreferrer">
            {acc}
          </a>
        );
      }
      default:
        return acc;
    }
  }, content);
}

function renderText(node: DocNodeShape): ReactNode {
  const text = asString(node.text);
  if (text === undefined) return null;
  return applyMarks(text, node.marks);
}

// Every node type this renderer understands. A type absent from this table
// falls through to `null` in DocNode below — never to raw text, never to
// markup. That is the whole safety argument for this file: there is no path
// from a stored document to injected HTML because there is no HTML here.
const NODE_TABLE: Record<
  string,
  (node: DocNodeShape, imageSrc: (id: string) => string) => ReactNode
> = {
  doc: (node, imageSrc) => children(node, imageSrc),
  paragraph: (node, imageSrc) => <p>{children(node, imageSrc)}</p>,
  heading: (node, imageSrc) => {
    const level = asAttrs(node.attrs).level;
    const content = children(node, imageSrc);
    switch (level) {
      case 2:
        return <h2>{content}</h2>;
      case 3:
        return <h3>{content}</h3>;
      default:
        return <h1>{content}</h1>;
    }
  },
  bulletList: (node, imageSrc) => <ul>{children(node, imageSrc)}</ul>,
  orderedList: (node, imageSrc) => <ol>{children(node, imageSrc)}</ol>,
  listItem: (node, imageSrc) => <li>{children(node, imageSrc)}</li>,
  blockquote: (node, imageSrc) => <blockquote>{children(node, imageSrc)}</blockquote>,
  codeBlock: (node, imageSrc) => (
    <pre>
      <code>{children(node, imageSrc)}</code>
    </pre>
  ),
  horizontalRule: () => <hr />,
  table: (node, imageSrc) => (
    <table>
      <tbody>{children(node, imageSrc)}</tbody>
    </table>
  ),
  tableRow: (node, imageSrc) => <tr>{children(node, imageSrc)}</tr>,
  tableCell: (node, imageSrc) => <td>{children(node, imageSrc)}</td>,
  tableHeader: (node, imageSrc) => <th>{children(node, imageSrc)}</th>,
  image: (node, imageSrc) => {
    const attrs = asAttrs(node.attrs);
    const id = asString(attrs.id);
    if (!id) return null;
    // next/image needs a configured remote pattern or loader at build time;
    // this component is reused by the console preview and the public help
    // site, each resolving image ids through a different `imageSrc`, so the
    // source is never known until render.
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={imageSrc(id)} alt={asString(attrs.alt) ?? ""} />;
  },
  hardBreak: () => <br />,
  text: renderText,
};

function DocNode({
  node,
  imageSrc,
}: {
  node: unknown;
  imageSrc: (id: string) => string;
}): ReactNode {
  if (!node || typeof node !== "object") return null;

  const shape = node as DocNodeShape;
  const type = asString(shape.type);
  if (!type) return null;

  const render = NODE_TABLE[type];
  if (!render) return null;

  return render(shape, imageSrc);
}

/**
 * Renders a stored ProseMirror JSON document as React elements. Every node
 * type is looked up in a fixed table; anything not in the table renders
 * nothing rather than falling back to raw text or markup. There is no
 * dangerouslySetInnerHTML in this file, and there must never be one — that
 * is what makes it safe to render a member-authored document on a page
 * anonymous visitors read.
 */
export function DocRenderer({ doc, imageSrc }: DocRendererProps) {
  return <DocNode node={doc} imageSrc={imageSrc} />;
}
