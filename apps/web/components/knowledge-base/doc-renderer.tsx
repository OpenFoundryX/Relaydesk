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
  /**
   * The id to put on a heading, keyed by the heading node itself. Supplied
   * by `articleHeadings` (components/portal/headings.ts) so a table of
   * contents links to anchors this renderer actually emits. Omitted where
   * there is no contents list -- the console preview -- and headings then
   * render without ids.
   */
  headingId?: (node: object) => string | undefined;
};

/** Everything threaded down the tree, so adding one more is a field. */
type RenderContext = {
  imageSrc: (id: string) => string;
  headingId?: (node: object) => string | undefined;
};

// A link href comes from the editor, but the editor is a text field and a
// member could paste anything. Only http, https, and mailto survive.
const SAFE_PROTOCOLS = ["http:", "https:", "mailto:"];

// A neutral base to resolve every href against, purely so relative hrefs
// parse instead of throwing. The host is never meant to be reachable and
// its origin string is compared against below to tell "this href specified
// its own host" apart from "this href is same-page relative."
const DUMMY_ORIGIN = "https://x.invalid";

// Validating a href and rendering it must use the same value, or the
// renderer's safety depends on two URL parsers (this one, and whatever
// resolves the anchor at click time) agreeing on every edge case -- NUL
// bytes, backslash-as-slash, protocol-relative "//host" links, unicode
// confusables. So every return here is built only from fields the WHATWG
// `URL` parser itself produced, never from the original input string.
function safeHref(href: unknown): string | undefined {
  if (typeof href !== "string") return undefined;

  let url: URL;
  try {
    url = new URL(href, DUMMY_ORIGIN);
  } catch {
    return undefined;
  }

  if (!SAFE_PROTOCOLS.includes(url.protocol)) return undefined;

  if (url.origin !== DUMMY_ORIGIN) {
    // The href resolved to a different host than our dummy base -- it
    // specified its own, whether as an ordinary absolute link
    // ("https://example.com/x"), a protocol-relative one ("//example.com"),
    // or a backslash-disguised one -- the parser resolves all three the
    // same way. Render exactly what was validated: the fully resolved URL.
    return url.href;
  }

  // Same origin as the dummy base means the href never specified a host of
  // its own: a same-page path, query, and/or fragment, which is common and
  // legitimate for in-hub links ("/category/article", "#section"). Render
  // only as much as the href actually asked for, built from the parsed
  // pieces -- a fragment-only href must stay a fragment rather than
  // becoming "/#section", and a bare path-relative href (no leading
  // "/", "?", or "#") is dropped rather than guessed at, because this
  // renderer has no page of its own to resolve it against.
  if (href.startsWith("/")) return url.pathname + url.search + url.hash;
  if (href.startsWith("?")) return url.search + url.hash;
  if (href.startsWith("#")) return url.hash;
  return undefined;
}

function asAttrs(attrs: unknown): Record<string, unknown> {
  return attrs && typeof attrs === "object" ? (attrs as Record<string, unknown>) : {};
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function children(node: DocNodeShape, ctx: RenderContext): ReactNode {
  return Array.isArray(node.content)
    ? node.content.map((child, i) => <DocNode key={i} node={child} ctx={ctx} />)
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
  (node: DocNodeShape, ctx: RenderContext) => ReactNode
> = {
  doc: (node, ctx) => children(node, ctx),
  paragraph: (node, ctx) => <p>{children(node, ctx)}</p>,
  heading: (node, ctx) => {
    const level = asAttrs(node.attrs).level;
    const content = children(node, ctx);
    const id = ctx.headingId?.(node);
    switch (level) {
      case 2:
        return <h2 id={id}>{content}</h2>;
      case 3:
        return <h3 id={id}>{content}</h3>;
      default:
        return <h1 id={id}>{content}</h1>;
    }
  },
  bulletList: (node, ctx) => <ul>{children(node, ctx)}</ul>,
  orderedList: (node, ctx) => <ol>{children(node, ctx)}</ol>,
  listItem: (node, ctx) => <li>{children(node, ctx)}</li>,
  blockquote: (node, ctx) => <blockquote>{children(node, ctx)}</blockquote>,
  codeBlock: (node, ctx) => (
    <pre>
      <code>{children(node, ctx)}</code>
    </pre>
  ),
  horizontalRule: () => <hr />,
  table: (node, ctx) => (
    <table>
      <tbody>{children(node, ctx)}</tbody>
    </table>
  ),
  tableRow: (node, ctx) => <tr>{children(node, ctx)}</tr>,
  tableCell: (node, ctx) => <td>{children(node, ctx)}</td>,
  tableHeader: (node, ctx) => <th>{children(node, ctx)}</th>,
  image: (node, ctx) => {
    const attrs = asAttrs(node.attrs);
    const id = asString(attrs.id);
    if (!id) return null;
    // next/image needs a configured remote pattern or loader at build time;
    // this component is reused by the console preview and the public help
    // site, each resolving image ids through a different `imageSrc`, so the
    // source is never known until render.
    //
    // Trust boundary: `imageSrc` is caller-supplied and its return value
    // goes straight into `src`, unvalidated by this file. That's deliberate
    // -- an `img src` cannot execute script in a modern browser the way an
    // `href` or injected markup can -- so each `imageSrc` implementation
    // (console preview, public help site) owns its own image-id resolution
    // rather than this renderer second-guessing it.
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={ctx.imageSrc(id)} alt={asString(attrs.alt) ?? ""} />;
  },
  hardBreak: () => <br />,
  text: renderText,
};

function DocNode({ node, ctx }: { node: unknown; ctx: RenderContext }): ReactNode {
  if (!node || typeof node !== "object") return null;

  const shape = node as DocNodeShape;
  const type = asString(shape.type);
  if (!type) return null;

  const render = NODE_TABLE[type];
  if (!render) return null;

  return render(shape, ctx);
}

/**
 * Renders a stored ProseMirror JSON document as React elements. Every node
 * type is looked up in a fixed table; anything not in the table renders
 * nothing rather than falling back to raw text or markup. There is no
 * dangerouslySetInnerHTML in this file, and there must never be one — that
 * is what makes it safe to render a member-authored document on a page
 * anonymous visitors read.
 */
export function DocRenderer({ doc, imageSrc, headingId }: DocRendererProps) {
  return <DocNode node={doc} ctx={{ imageSrc, headingId }} />;
}
