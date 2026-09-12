"use client";

import { useState, type FormEvent } from "react";

import { WidgetButton } from "@/components/widget/button";

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
  onDegrade,
  onCompose,
}: {
  widgetKey: string | undefined;
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

        if (done) return;
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
    <div className="flex flex-1 flex-col gap-4 px-4 py-6">
      <h1 className="text-[13px] text-ink-500 dark:text-ink-400">Ask a question</h1>

      {/* Announces each answer as it streams in and settles -- the one
          region spec D9's token-by-token output actually needs read out. */}
      <div
        aria-live="polite"
        className="flex flex-1 flex-col gap-3 text-[13px] leading-relaxed"
      >
        {turns.map((turn, index) =>
          turn.role === "visitor" ? (
            <p key={index} className="font-medium text-ink-900 dark:text-white">
              {turn.text}
            </p>
          ) : (
            <div key={index}>
              <p className="text-ink-800 dark:text-ink-200">{turn.text}</p>
              {turn.citations.length > 0 && (
                <ul className="mt-2 flex flex-col gap-1">
                  {turn.citations.map((citation) => (
                    <li key={citation.path}>
                      <a
                        href={`/help/${citation.path}`}
                        className="text-[12px] text-accent-950 underline dark:text-accent-400"
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
        {asking && <p className="text-ink-400">{draft || "Thinking…"}</p>}
      </div>

      <form onSubmit={submit} className="flex flex-col gap-2">
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
          className="h-9 w-full rounded-md border border-ink-200 bg-white px-3 text-[13px] text-ink-900 placeholder:text-ink-400 transition-colors hover:border-ink-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50 dark:border-ink-700 dark:bg-ink-800 dark:text-white dark:placeholder:text-ink-400"
        />
        <WidgetButton type="submit" variant="primary" disabled={asking || !typed.trim()}>
          {asking ? "Asking…" : "Ask"}
        </WidgetButton>
      </form>

      <div className="mt-auto pt-2">
        <WidgetButton
          type="button"
          variant="secondary"
          onClick={() => onCompose(transcriptText(turns))}
        >
          Send a message
        </WidgetButton>
      </div>
    </div>
  );
}
