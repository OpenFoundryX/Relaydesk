"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { ArrowUp } from "lucide-react";

/** One resolved citation -- server-side only (spec D3): a model that
 * invents an article id produces no link, because the id resolves to
 * nothing. */
type Citation = { title: string; path: string };

type Turn =
  | { role: "visitor"; text: string }
  | { role: "assistant"; text: string; citations: Citation[] };

/** One event off the wire: `event: text` carries `{text}`, `event: done`
 * carries `{outcome, citations}`. Anything else (a blank keep-alive line, a
 * frame this parser does not recognise) is dropped rather than thrown on --
 * a visitor must never see a parse error where an answer was meant to be. */
function parseEvent(raw: string): { event: string; data: Record<string, unknown> } | null {
  let event: string | null = null;
  let data: string | null = null;
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data = line.slice(5).trim();
  }
  if (!event || data === null) return null;
  try {
    return { event, data: JSON.parse(data) as Record<string, unknown> };
  } catch {
    return null;
  }
}

/**
 * The panel's conversation. A visitor asks a question in plain language;
 * the answer streams in token by token (spec D9) and, when it is grounded,
 * ends with links back to the articles it cited.
 *
 * Holds the transcript in component state only -- nothing is persisted,
 * and a reload starts fresh (spec D2). Every failure this component can
 * see -- no stream body, a network error, or a `done` event whose outcome
 * is anything other than `answered` -- is handed to `onDegrade` rather
 * than rendered: `refused` (nothing grounded to say) and `degraded`
 * (something went wrong) are deliberately indistinguishable here, exactly
 * as spec D4 asks, and `onDegrade` is wired by `panel.tsx` to the same
 * `home` view the widget has always had. There is nothing here to catch
 * as an "error" -- the route never answers with one (Task 8's contract):
 * a failure always arrives as content, on a 200.
 */
/** What the visitor has already been told, rendered as the plain-text
 * transcript the ticket route accepts -- see `apps/api/src/relaydesk/api/
 * widget.py`'s `submit`. Turns still in flight (the streaming draft) are
 * not included: this only ever runs from the "Send a message" click,
 * after a turn has settled into state one way or the other. */
function transcriptText(turns: Turn[]): string {
  return turns
    .map((turn) => `${turn.role === "visitor" ? "Visitor" : "Assistant"}: ${turn.text}`)
    .join("\n");
}

export function Ask({
  widgetKey,
  greeting,
  onDegrade,
  onCompose,
}: {
  widgetKey: string | undefined;
  /** The workspace's own opening line, from its widget settings. */
  greeting?: string;
  onDegrade: () => void;
  /** Escalating carries the transcript so far (spec D8) -- empty when the
   * visitor asked nothing before reaching for a human, which leaves the
   * ticket exactly as it looks today. */
  onCompose: (transcript: string) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [typed, setTyped] = useState("");
  const [draft, setDraft] = useState("");
  const [asking, setAsking] = useState(false);

  // Follow the conversation as it grows, the way a messenger does. Without
  // this a streaming answer runs off the bottom of a short panel and the
  // visitor watches a static first line while the rest arrives unseen.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [turns, draft, asking]);

  async function ask(question: string) {
    setTurns((prev) => [...prev, { role: "visitor", text: question }]);
    setDraft("");
    setAsking(true);

    try {
      // No key at all is the shape a bare test render of this component
      // reaches -- see results.tsx/article.tsx for the same guard. It must
      // behave exactly like any other failure: home, not an error.
      if (!widgetKey) {
        onDegrade();
        return;
      }

      const response = await fetch("/widget/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: widgetKey, question }),
      });

      if (!response.body) {
        onDegrade();
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let full = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (value) buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const raw = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const parsed = parseEvent(raw);

          if (parsed?.event === "text" && typeof parsed.data.text === "string") {
            full += parsed.data.text;
            setDraft(full);
          } else if (parsed?.event === "done") {
            if (parsed.data.outcome === "answered") {
              const citations = Array.isArray(parsed.data.citations)
                ? (parsed.data.citations as Citation[])
                : [];
              setTurns((prev) => [...prev, { role: "assistant", text: full, citations }]);
            } else {
              // `refused` and `degraded` both land here, on purpose.
              onDegrade();
            }
            return;
          }

          boundary = buffer.indexOf("\n\n");
        }

        // The stream ended without a `done` frame ever arriving. Task 8
        // guarantees the server emits one on every path it controls, but
        // the server does not control every way a stream ends: a dropped
        // connection, a crashed upstream, a proxy timing out mid-answer.
        // Without this the visitor's question simply hangs, which is the
        // one outcome spec D4 exists to prevent -- worse than an error,
        // because nothing tells them to try something else.
        if (done) {
          onDegrade();
          return;
        }
      }
    } catch {
      // A rejected `fetch` (offline, blocked) or a reader that throws --
      // the same widget-that-already-works fallback as a `degraded` frame.
      onDegrade();
    } finally {
      setAsking(false);
      setDraft("");
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = typed.trim();
    if (!question || asking) return;
    setTyped("");
    void ask(question);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* The transcript. Scrolls on its own so the composer stays put --
          a chat whose input moves down the page as it fills is the thing
          this panel is most often mistaken for and should not be. */}
      <div
        ref={scrollRef}
        aria-live="polite"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4"
      >
        <Bubble from="assistant">
          {greeting?.trim() || "Hi! Ask a question and I'll answer from our help articles."}
        </Bubble>

        {turns.map((turn, index) =>
          turn.role === "visitor" ? (
            <Bubble key={index} from="visitor">
              {turn.text}
            </Bubble>
          ) : (
            <div key={index} className="flex flex-col items-start gap-1.5">
              <Bubble from="assistant">{turn.text}</Bubble>
              {turn.citations.length > 0 && (
                <ul className="flex flex-wrap gap-1.5 pl-1">
                  {turn.citations.map((citation) => (
                    <li key={citation.path}>
                      <a
                        href={`/help/${citation.path}`}
                        // The panel lives in the loader's iframe (spec
                        // D5), which has no chrome and no way back. A
                        // same-frame navigation would replace the widget
                        // with the article and strand the visitor there.
                        target="_blank"
                        rel="noreferrer"
                        className="inline-block rounded-full border border-ink-200 bg-white px-2.5 py-1 text-[11px] font-medium text-ink-700 transition-colors hover:border-ink-300 hover:text-ink-900 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200 dark:hover:text-white"
                      >
                        {citation.title}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ),
        )}

        {asking &&
          (draft ? (
            <Bubble from="assistant">{draft}</Bubble>
          ) : (
            <Bubble from="assistant">
              <span className="flex gap-1 py-0.5" aria-label="Thinking">
                <Dot delay="0ms" />
                <Dot delay="150ms" />
                <Dot delay="300ms" />
              </span>
            </Bubble>
          ))}
      </div>

      {/* Pinned. Input and send sit on one line, the way every messenger a
          visitor has already used puts them. */}
      <form
        onSubmit={submit}
        className="flex shrink-0 items-end gap-2 border-t border-ink-200 px-3 py-3 dark:border-ink-800"
      >
        <label htmlFor="widget-ask" className="sr-only">
          Ask a question
        </label>
        <input
          id="widget-ask"
          type="text"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          placeholder="Ask a question"
          disabled={asking}
          className="h-10 min-w-0 flex-1 rounded-full border border-ink-200 bg-white px-4 text-[13px] text-ink-900 placeholder:text-ink-400 transition-colors hover:border-ink-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50 dark:border-ink-700 dark:bg-ink-800 dark:text-white dark:placeholder:text-ink-400"
        />
        <button
          type="submit"
          aria-label="Ask"
          disabled={asking || !typed.trim()}
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-ink-950 text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-30 dark:bg-white dark:text-ink-900"
        >
          <ArrowUp className="size-4" aria-hidden />
        </button>
      </form>

      {/* Quiet by design. Escalating is always available, but it is not
          what the panel is inviting a visitor to do first. */}
      <div className="shrink-0 px-4 pb-3 text-center">
        <button
          type="button"
          onClick={() => onCompose(transcriptText(turns))}
          className="text-[12px] text-ink-500 underline underline-offset-2 transition-colors hover:text-ink-900 dark:text-ink-400 dark:hover:text-white"
        >
          Talk to a person instead
        </button>
      </div>
    </div>
  );
}

/** One message. Visitor right and filled, assistant left and quiet -- the
 *  shape every messenger a visitor has already used settled on. */
function Bubble({
  from,
  children,
}: {
  from: "visitor" | "assistant";
  children: React.ReactNode;
}) {
  const visitor = from === "visitor";
  return (
    <div className={visitor ? "flex justify-end" : "flex justify-start"}>
      <div
        className={[
          "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed",
          visitor
            ? "rounded-br-md bg-ink-950 text-white dark:bg-white dark:text-ink-900"
            : "rounded-bl-md bg-ink-100 text-ink-900 dark:bg-ink-800 dark:text-ink-100",
        ].join(" ")}
      >
        {children}
      </div>
    </div>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      aria-hidden
      style={{ animationDelay: delay }}
      className="size-1.5 animate-bounce rounded-full bg-ink-400 motion-reduce:animate-none dark:bg-ink-500"
    />
  );
}
