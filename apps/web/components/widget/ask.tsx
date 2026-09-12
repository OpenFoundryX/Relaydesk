"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { ArrowUp } from "lucide-react";

// `Citation` carries the number the SERVER issued (spec D3): a model that
// invents an article id produces no link, because the id resolves to
// nothing -- and `Answer` drops the marker rather than printing it.
import { Answer, type Citation } from "@/components/widget/answer";

import type { SubmitWidgetTicketResult } from "@/app/(widget)/widget/frame/actions";

type Turn =
  | { role: "visitor"; text: string }
  | { role: "assistant"; text: string; citations: Citation[] };

/**
 * Where the escalation offer is, in the conversation. `closed` is "not
 * offering, not collecting" -- the ordinary state a fresh panel opens in
 * and the state every path here eventually returns to, one way or
 * another. The rest is a strict pipeline: an unhelpful answer opens
 * `offer`; "Yes" moves to `email`, a plausible-looking address moves to
 * `name`, and either a name or a skip moves to `filing` and then to
 * `closed` (sent) or `failed` (say so, offer to retry). Carrying
 * `question`/`email`/`name` forward on each stage, rather than reading
 * them back out of `turns`, is what lets `fileTicket` below rebuild the
 * exact same request on a retry without re-parsing the transcript.
 */
type Escalation =
  | { stage: "closed" }
  | { stage: "offer"; question: string }
  | { stage: "email"; question: string }
  | { stage: "name"; question: string; email: string }
  | { stage: "filing"; question: string; email: string; name: string }
  | { stage: "failed"; question: string; email: string; name: string; message: string };

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

/** Good enough to move on from, not a real validator -- the API's own
 * `EmailStr` is the actual gate, at filing time. This only exists so a
 * visitor who mistypes gets a same-breath nudge instead of finding out
 * after a round trip that files the ticket. */
function looksLikeEmail(value: string): boolean {
  return value.includes("@");
}

/** A blank reply or the word "skip" (either the composer or the dedicated
 * button below can produce it) both mean "no name given". */
function isSkip(value: string): boolean {
  const trimmed = value.trim();
  return trimmed === "" || trimmed.toLowerCase() === "skip";
}

/**
 * The panel's conversation. A visitor asks a question in plain language;
 * the answer streams in token by token (spec D9) and, when it is grounded,
 * ends with links back to the articles it cited.
 *
 * Holds the transcript in component state only -- nothing is persisted,
 * and a reload starts fresh (spec D2).
 *
 * The `done` frame's `outcome` carries four values (the backend's
 * contract, not this file's): `answered` renders normally; `clarified`
 * renders exactly the same way -- it is the model asking a question or
 * greeting, not failing -- but never offers escalation, because it has
 * just asked the visitor something itself and an offer would talk over
 * it; `refused` and `degraded` both mean the bot has nothing to say, so
 * both open the same inline offer to escalate rather than discarding
 * whatever text streamed alongside them -- a citation-less answer is not
 * shown as if it were grounded, ever.
 *
 * `onDegrade` is now reserved for the narrower case where no conversation
 * was possible at all: no key, no response body, a stream that never
 * says it is done, or `fetch` itself throwing. Those still hand the
 * visitor back to `home` (spec D4) -- there is nothing to offer
 * escalation on top of, because nothing was said.
 */
/** What the visitor has already been told, rendered as the plain-text
 * transcript the ticket route accepts -- see `apps/api/src/relaydesk/api/
 * widget.py`'s `submit`. Turns still in flight (the streaming draft) are
 * not included: this only ever runs once a turn has settled into state
 * one way or the other. */
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
  onSubmit,
}: {
  widgetKey: string | undefined;
  /** The workspace's own opening line, from its widget settings. */
  greeting?: string;
  onDegrade: () => void;
  /** Escalating via the quiet link at the foot of the panel carries the
   * transcript so far (spec D8) -- empty when the visitor asked nothing
   * before reaching for a human, which leaves the ticket exactly as it
   * looks today. Hidden for the life of the inline offer below (`offer`
   * through `failed`), since the two ways out would otherwise compete. */
  onCompose: (transcript: string) => void;
  /**
   * The ticket-submission server action, already bound to `widgetKey` by
   * the frame page -- the same prop `compose.tsx` takes, and for the same
   * reason: a Client Component may take a Server Action as a prop, but
   * importing the module that defines one would pull `lib/api/widget.ts`
   * -- `server-only` -- into this file's module graph. Absent only in a
   * bare test render; the inline offer below says so plainly rather than
   * pretending to have sent anything.
   */
  onSubmit?: (formData: FormData) => Promise<SubmitWidgetTicketResult>;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  // Mirrors `turns`, kept in lock-step by `appendTurn` rather than read
  // back out of the `turns` state variable. `setState` updaters inside
  // one synchronous handler (e.g. `submitName` appending a turn and then
  // immediately filing) do not see each other's results until the next
  // render, but the ticket needs the *just* -added turn in its transcript
  // -- so this ref, not `turns`, is what `fileTicket` reads from.
  const turnsRef = useRef<Turn[]>([]);
  function appendTurn(turn: Turn) {
    turnsRef.current = [...turnsRef.current, turn];
    setTurns(turnsRef.current);
  }

  const [typed, setTyped] = useState("");
  const [draft, setDraft] = useState("");
  const [asking, setAsking] = useState(false);
  const [escalation, setEscalation] = useState<Escalation>({ stage: "closed" });

  // Follow the conversation as it grows, the way a messenger does. Without
  // this a streaming answer runs off the bottom of a short panel and the
  // visitor watches a static first line while the rest arrives unseen.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [turns, draft, asking, escalation.stage]);

  async function ask(question: string) {
    // A fresh question abandons whatever the offer was doing -- the
    // visitor typing past it is as much a "no" as clicking the button,
    // and nothing here should keep expecting an email that is never
    // coming.
    setEscalation({ stage: "closed" });
    appendTurn({ role: "visitor", text: question });
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
            const outcome = parsed.data.outcome;
            if (outcome === "answered" || outcome === "clarified") {
              // `clarified` never carries citations of its own -- it is a
              // question back to the visitor, not a grounded answer -- so
              // only `answered` ever reads the field at all.
              const citations =
                outcome === "answered" && Array.isArray(parsed.data.citations)
                  ? (parsed.data.citations as Citation[])
                  : [];
              appendTurn({ role: "assistant", text: full, citations });
            } else if (outcome === "refused" || outcome === "degraded") {
              appendTurn({
                role: "assistant",
                text:
                  outcome === "refused"
                    ? "I couldn't find an answer for that. Would you like me to pass this to the team?"
                    : "Sorry, something's gone wrong on my end. Would you like me to pass this to the team?",
                citations: [],
              });
              setEscalation({ stage: "offer", question });
            } else {
              // A fifth outcome value would be new to the wire and
              // unrecognised here -- treat it exactly like any other
              // shape this parser cannot make sense of (see `parseEvent`)
              // rather than leaving the visitor's question hanging.
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

  // "Yes" -- opens the one field the ticket cannot do without. Nobody is
  // asked for an email they did not agree to give: this is the only path
  // that ever moves `escalation` into `email`.
  function acceptEscalation() {
    if (escalation.stage !== "offer") return;
    appendTurn({ role: "visitor", text: "Yes" });
    appendTurn({
      role: "assistant",
      text: "Sure — what's your email address? I'll pass this on to the team so they can get back to you.",
      citations: [],
    });
    setEscalation({ stage: "email", question: escalation.question });
  }

  // "No" -- acknowledges and lets the conversation carry on exactly as it
  // would have if nothing had gone wrong.
  function declineEscalation() {
    if (escalation.stage !== "offer") return;
    appendTurn({ role: "visitor", text: "No" });
    appendTurn({
      role: "assistant",
      text: "No problem — ask away if anything else comes to mind.",
      citations: [],
    });
    setEscalation({ stage: "closed" });
  }

  // The composer's reply while `escalation.stage === "email"`. A
  // not-quite-an-address reply reprompts rather than filing anything --
  // the ticket would only bounce back from the API's own `EmailStr`
  // later, after a round trip the visitor has no way to see coming.
  function submitEmail(raw: string) {
    if (escalation.stage !== "email") return;
    appendTurn({ role: "visitor", text: raw });
    if (!looksLikeEmail(raw)) {
      appendTurn({
        role: "assistant",
        text: "That doesn't quite look like an email address — mind trying again?",
        citations: [],
      });
      return;
    }
    appendTurn({
      role: "assistant",
      text: 'Thanks. And your name, if you\'d like to share it — or just say "skip".',
      citations: [],
    });
    setEscalation({ stage: "name", question: escalation.question, email: raw });
  }

  // The composer's reply while `escalation.stage === "name"`, and the
  // dedicated Skip button both funnel through here -- an empty reply and
  // the word "skip" mean the same thing (spec: name is optional).
  function submitName(raw: string) {
    if (escalation.stage !== "name") return;
    const skipped = isSkip(raw);
    appendTurn({ role: "visitor", text: skipped ? "Skip" : raw });
    void fileTicket(escalation.question, escalation.email, skipped ? "" : raw.trim());
  }

  // Confirms what is about to be sent, files it, and always -- success,
  // API failure, or a thrown network error -- leaves the visitor certain
  // one way or the other whether it went. A visitor must never be left
  // unsure whether their message was sent.
  async function fileTicket(question: string, email: string, name: string) {
    setEscalation({ stage: "filing", question, email, name });
    appendTurn({
      role: "assistant",
      text: `Sending this to the team now, as ${email}${name ? ` (${name})` : ""}.`,
      citations: [],
    });

    if (!onSubmit) {
      appendTurn({
        role: "assistant",
        text: "This widget isn't set up to send messages right now, so that hasn't gone anywhere. Sorry about that.",
        citations: [],
      });
      setEscalation({
        stage: "failed",
        question,
        email,
        name,
        message: "This widget isn't set up to send messages right now.",
      });
      return;
    }

    try {
      const formData = new FormData();
      formData.set("email", email);
      formData.set("name", name);
      formData.set("message", question);
      formData.set("transcript", transcriptText(turnsRef.current));
      const result = await onSubmit(formData);
      if (result.ok) {
        appendTurn({
          role: "assistant",
          text: "Done — the team has it and will follow up by email.",
          citations: [],
        });
        setEscalation({ stage: "closed" });
      } else {
        appendTurn({
          role: "assistant",
          text: `That didn't send: ${result.message} Want to try again?`,
          citations: [],
        });
        setEscalation({ stage: "failed", question, email, name, message: result.message });
      }
    } catch {
      appendTurn({
        role: "assistant",
        text: "I couldn't reach the server, so that hasn't sent yet. Want to try again?",
        citations: [],
      });
      setEscalation({ stage: "failed", question, email, name, message: "network" });
    }
  }

  function retryFiling() {
    if (escalation.stage !== "failed") return;
    void fileTicket(escalation.question, escalation.email, escalation.name);
  }

  const busy = asking || escalation.stage === "filing";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = typed.trim();
    if (!text || busy) return;
    setTyped("");

    if (escalation.stage === "email") {
      submitEmail(text);
      return;
    }
    if (escalation.stage === "name") {
      submitName(text);
      return;
    }
    void ask(text);
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
              <Bubble from="assistant">
                <Answer text={turn.text} citations={turn.citations} />
              </Bubble>
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

        {/* The inline offer -- real buttons, not links, so a keyboard or
            screen-reader visitor reaches them exactly as they would any
            other control. Nobody is asked for an email they did not
            agree to give: this is the only door into that. */}
        {escalation.stage === "offer" && (
          <div className="flex justify-start gap-2 pl-1">
            <button
              type="button"
              onClick={acceptEscalation}
              className="rounded-full border border-ink-200 bg-white px-3 py-1 text-[12px] font-medium text-ink-700 transition-colors hover:border-ink-300 hover:text-ink-900 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200 dark:hover:text-white"
            >
              Yes
            </button>
            <button
              type="button"
              onClick={declineEscalation}
              className="rounded-full border border-ink-200 bg-white px-3 py-1 text-[12px] font-medium text-ink-700 transition-colors hover:border-ink-300 hover:text-ink-900 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200 dark:hover:text-white"
            >
              No
            </button>
          </div>
        )}

        {/* The name step accepts a blank reply as a skip, but the
            composer's send button is disabled on empty input -- so this
            is the only way to skip without typing the word. */}
        {escalation.stage === "name" && (
          <div className="flex justify-start pl-1">
            <button
              type="button"
              onClick={() => submitName("")}
              className="rounded-full border border-ink-200 bg-white px-3 py-1 text-[12px] font-medium text-ink-700 transition-colors hover:border-ink-300 hover:text-ink-900 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200 dark:hover:text-white"
            >
              Skip
            </button>
          </div>
        )}

        {escalation.stage === "failed" && (
          <div className="flex justify-start pl-1">
            <button
              type="button"
              onClick={retryFiling}
              className="rounded-full border border-ink-200 bg-white px-3 py-1 text-[12px] font-medium text-ink-700 transition-colors hover:border-ink-300 hover:text-ink-900 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200 dark:hover:text-white"
            >
              Try again
            </button>
          </div>
        )}

        {asking &&
          (draft ? (
            <Bubble from="assistant">
              <Answer text={draft} citations={[]} />
            </Bubble>
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
          visitor has already used puts them. Its placeholder and label
          never change for the escalation steps above -- the visitor is
          always just replying, in the same box, to whatever was asked. */}
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
          disabled={busy}
          className="h-10 min-w-0 flex-1 rounded-full border border-ink-200 bg-white px-4 text-[13px] text-ink-900 placeholder:text-ink-400 transition-colors hover:border-ink-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50 dark:border-ink-700 dark:bg-ink-800 dark:text-white dark:placeholder:text-ink-400"
        />
        <button
          type="submit"
          aria-label="Ask"
          disabled={busy || !typed.trim()}
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-ink-950 text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-30 dark:bg-white dark:text-ink-900"
        >
          <ArrowUp className="size-4" aria-hidden />
        </button>
      </form>

      {/* Quiet by design, and only on offer while the inline flow above is
          not already running -- two ways to reach a human at once is not
          a better offer, just a confusing one. */}
      {escalation.stage === "closed" && (
        <div className="shrink-0 px-4 pb-3 text-center">
          <button
            type="button"
            onClick={() => onCompose(transcriptText(turns))}
            className="text-[12px] text-ink-500 underline underline-offset-2 transition-colors hover:text-ink-900 dark:text-ink-400 dark:hover:text-white"
          >
            Talk to a person instead
          </button>
        </div>
      )}
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
