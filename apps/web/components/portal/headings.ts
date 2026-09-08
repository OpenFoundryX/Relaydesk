/**
 * The headings a reader can jump to, and the ids they are rendered with.
 *
 * One pass over the document produces both. That is the point of the
 * module: the table of contents links to `#what-is-a-pos-terminal` and the
 * heading itself carries that id, and the two come from the same walk
 * rather than from two functions that agree until one of them changes.
 *
 * Derived in the browser bundle rather than sent by the API for the same
 * reason -- the API would have to slugify in Python, `DocRenderer` would
 * still have to put an id on the heading here, and those are two
 * implementations of one rule.
 *
 * The document is authored by a workspace member and read by anonymous
 * visitors, so nothing about its shape is assumed; see `DocRenderer`,
 * which reads it with the same suspicion.
 */

/** A row in the table of contents. Only h2 and h3 -- see `articleHeadings`. */
export interface ArticleHeading {
  id: string;
  text: string;
  level: 2 | 3;
}

export interface ArticleHeadings {
  list: ArticleHeading[];
  /** The id given to this exact node, for the renderer to put on the tag. */
  idFor: (node: object) => string | undefined;
}

type Node = { type?: unknown; attrs?: unknown; content?: unknown; text?: unknown };

function asNode(value: unknown): Node | null {
  return value && typeof value === "object" ? (value as Node) : null;
}

/** The visible words of a node, including any nested inline content. */
function textOf(node: Node): string {
  if (typeof node.text === "string") return node.text;
  if (!Array.isArray(node.content)) return "";
  return node.content
    .map((child) => {
      const parsed = asNode(child);
      return parsed ? textOf(parsed) : "";
    })
    .join("");
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function levelOf(node: Node): 2 | 3 | null {
  const attrs = node.attrs && typeof node.attrs === "object" ? node.attrs : {};
  const level = (attrs as { level?: unknown }).level;
  // h1 is the article's title, rendered by the page rather than the body,
  // so a document that also uses one is not offering a second place to jump
  // to. Anything deeper than h3 is too fine-grained for a contents list.
  return level === 2 || level === 3 ? level : null;
}

export function articleHeadings(doc: unknown): ArticleHeadings {
  const list: ArticleHeading[] = [];
  const ids = new WeakMap<object, string>();
  const taken = new Set<string>();

  function visit(value: unknown): void {
    const node = asNode(value);
    if (!node) return;

    if (node.type === "heading") {
      const level = levelOf(node);
      const text = textOf(node).trim();
      if (level !== null && text) {
        // A heading whose words slugify to nothing ("!!!") still needs an
        // id, or its row in the contents scrolls nowhere.
        const base = slugify(text) || `section-${list.length + 1}`;
        let id = base;
        for (let n = 2; taken.has(id); n += 1) id = `${base}-${n}`;
        taken.add(id);
        ids.set(node, id);
        list.push({ id, text, level });
      }
    }

    if (Array.isArray(node.content)) node.content.forEach(visit);
  }

  visit(doc);

  return { list, idFor: (node) => ids.get(node) };
}
