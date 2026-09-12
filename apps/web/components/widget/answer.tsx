import type { ReactNode } from "react";

/** One citation the SERVER resolved. `number` is the number the server
 *  issued to that article when it built the prompt, which is what makes an
 *  inline `[n]` marker resolvable back to a real link. */
export type Citation = { number: number; title: string; path: string };

/**
 * A model's answer, rendered.
 *
 * The model writes markdown whether or not anyone asked it to -- `**bold**`,
 * bullet lists, the occasional heading -- and printing that raw leaves
 * asterisks all over a support answer. This renders the small subset that
 * actually turns up, and the citation markers alongside it.
 *
 * **It never emits HTML.** Every branch below builds React elements, so the
 * model's text is escaped by React on the way in. That is the whole reason
 * this exists rather than a markdown library with a sanitiser bolted on: the
 * answer is untrusted input (spec D7 -- the message and the knowledge base
 * are both untrusted, and the model sits downstream of both), and the safest
 * way to render untrusted text is never to have an HTML path at all.
 * Anything this parser does not recognise stays as literal text, which is
 * the failure mode you want -- a stray backtick is ugly, an injected
 * `<script>` is not.
 */
export function Answer({ text, citations }: { text: string; citations: Citation[] }) {
  const byNumber = new Map(citations.map((citation) => [citation.number, citation]));

  return (
    <>
      {blocks(text).map((block, index) => {
        if (block.kind === "heading") {
          return (
            <p key={index} className="mt-2 mb-1 font-semibold first:mt-0">
              {inline(block.text, byNumber)}
            </p>
          );
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List
              key={index}
              className={[
                "my-1 flex flex-col gap-1 pl-4",
                block.ordered ? "list-decimal" : "list-disc",
              ].join(" ")}
            >
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="pl-0.5">
                  {inline(item, byNumber)}
                </li>
              ))}
            </List>
          );
        }
        return (
          <p key={index} className="my-1 first:mt-0 last:mb-0">
            {inline(block.text, byNumber)}
          </p>
        );
      })}
    </>
  );
}

type Block =
  | { kind: "paragraph"; text: string }
  | { kind: "heading"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] };

const HEADING = /^#{1,6}\s+(.*)$/;
const BULLET = /^[-*]\s+(.*)$/;
const NUMBERED = /^\d{1,2}[.)]\s+(.*)$/;

/** Split into blocks a line at a time. Deliberately not a full markdown
 *  grammar: no tables, no nesting, no block quotes. A model that emits one
 *  gets its literal text rendered, which reads as slightly odd rather than
 *  as broken. */
function blocks(text: string): Block[] {
  const out: Block[] = [];
  let paragraph: string[] = [];

  const flush = () => {
    if (paragraph.length > 0) {
      out.push({ kind: "paragraph", text: paragraph.join(" ") });
      paragraph = [];
    }
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();

    if (line === "") {
      flush();
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      flush();
      out.push({ kind: "heading", text: heading[1] });
      continue;
    }

    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      const item = (bullet ?? numbered)![1];
      flush();
      const last = out[out.length - 1];
      if (last?.kind === "list" && last.ordered === ordered) last.items.push(item);
      else out.push({ kind: "list", ordered, items: [item] });
      continue;
    }

    paragraph.push(line);
  }

  flush();
  return out;
}

// One pass, one alternation: bold, italic, inline code, citation marker.
// Ordered so `**` is tried before `*`, or every bold would parse as two
// empty italics.
const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`|\[\d{1,2}\])/g;
const MARKER = /^\[(\d{1,2})\]$/;

function inline(text: string, byNumber: Map<number, Citation>): ReactNode[] {
  return text
    .split(INLINE)
    .filter((piece) => piece !== "")
    .map((piece, index) => {
      const marker = MARKER.exec(piece);
      if (marker) {
        const citation = byNumber.get(Number(marker[1]));
        // A number the model invented resolves to nothing and is DROPPED,
        // not printed. Spec D3 already guarantees it produces no link;
        // leaving "[9]" sitting in the prose just looks like a broken one.
        if (!citation) return null;
        return (
          <a
            key={index}
            href={`/help/${citation.path}`}
            target="_blank"
            rel="noreferrer"
            title={citation.title}
            className="mx-0.5 inline-flex size-4 -translate-y-0.5 items-center justify-center rounded bg-ink-200 align-middle text-[10px] font-semibold text-ink-700 no-underline transition-colors hover:bg-ink-300 hover:text-ink-900 dark:bg-ink-700 dark:text-ink-200 dark:hover:bg-ink-600 dark:hover:text-white"
          >
            {citation.number}
          </a>
        );
      }
      if (
        (piece.startsWith("**") && piece.endsWith("**")) ||
        (piece.startsWith("__") && piece.endsWith("__"))
      ) {
        return (
          <strong key={index} className="font-semibold">
            {piece.slice(2, -2)}
          </strong>
        );
      }
      if (
        (piece.startsWith("*") && piece.endsWith("*")) ||
        (piece.startsWith("_") && piece.endsWith("_"))
      ) {
        return <em key={index}>{piece.slice(1, -1)}</em>;
      }
      if (piece.startsWith("`") && piece.endsWith("`")) {
        return (
          <code
            key={index}
            className="rounded bg-ink-200 px-1 py-0.5 font-mono text-[11px] dark:bg-ink-700"
          >
            {piece.slice(1, -1)}
          </code>
        );
      }
      return piece;
    });
}
