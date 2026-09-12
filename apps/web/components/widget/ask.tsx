"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { ArrowUp } from "lucide-react";

// `Citation` carries the number the SERVER issued (spec D3): a model that
// invents an article id produces no link, because the id resolves to
// nothing -- and `Answer` drops the marker rather than printing it.
import { Answer, type Citation } from "@/components/widget/answer";

import type { SubmitWidgetTicketResult } from "@/app/(widget)/widget/frame/actions";

/** `collecting` marks a turn that belongs to the escalation dialogue --
 *  the bot asking for an email, the visitor giving one -- rather than to
 *  the conversation about the problem. It stays on screen (the visitor
 *  just had it) and is kept OUT of the transcript an agent reads: they
 *  already have the address in the From field, and a page of the bot
 *  collecting it buries the one thing they need. */
type Turn =
  | { role: "visitor"; text: string; collecting?: boolean }
  | { role: "assistant"; text: string; citations: Citation[]; collecting?: boolean };

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
  | { stage: "issue" }
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
/** How many answers a visitor sits through before the bot asks whether
 *  they would rather talk to someone. Three is "this is not landing"
 *  without being so eager that a visitor reading a good answer is
 *  interrupted by an offer to escalate. */
const OFFER_AFTER_ANSWERS = 3;

function transcriptText(turns: Turn[]): string {
  const lines: string[] = [];
  for (const turn of turns) {
    if (turn.collecting) continue;
    lines.push(`${turn.role === "visitor" ? "Visitor" : "Assistant"}: ${turn.text}`);
    // The articles the bot already put in front of them. Without these an
    // agent's first instinct is to send a link the visitor has read and
    // bounced off, which is the most annoying possible reply.
    if (turn.role === "assistant" && turn.citations.length > 0) {
      const titles = turn.citations.map((citation) => citation.title).join(", ");
      lines.push(`  (articles shown: ${titles})`);
    }
  }
  return lines.join("\n");
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

  // Offered proactively at most once per conversation -- a ref rather than
  // state because nothing renders from it and it must be readable inside
  // the same handler that sets it.
  const offeredRef = useRef(false);

  const [typed, setTyped] = useState("");
  const [draft, setDraft] = useState("");
  const [asking, setAsking] = useState(false);
  const [escalation, setEscalation] = useState<Escalation>({ stage: "closed" });

  // Follow the conversation as it grows, the way a messenger does. Without
  // this a streaming answer runs off the bottom of a short panel and the
  // visitor watches a static first line while the rest arrives unseen.
  const inputRef = useRef<HTMLInputElement>(null);
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

      // The conversation so far, so a follow-up means something. Read from
      // the ref rather than the `turns` state: `ask` is called in the same
      // handler that appended the visitor's turn, and state updates are not
      // visible until the next render -- reading `turns` here would send a
      // history one turn stale, every turn.
      //
      // The server caps and truncates this; nothing is trimmed here beyond
      // dropping the turn just appended, which is the question itself.
      const history = turnsRef.current
        .slice(0, -1)
        .map((turn) => ({ role: turn.role, text: turn.text }));

      const response = await fetch("/widget/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: widgetKey, question, history }),
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
              // A visitor can be stuck while every answer technically
              // succeeds. Grounded answers keep coming, `refused` never
              // fires, and the offer below never opens -- so someone who
              // asks the same thing four different ways is answered four
              // times and never once asked whether they want a human.
              // After enough back-and-forth, offer. Once: a bot that keeps
              // asking is worse than one that asked and took no for an
              // answer.
              const answers = turnsRef.current.filter(
                (turn) => turn.role === "assistant",
              ).length;
              if (answers >= OFFER_AFTER_ANSWERS && !offeredRef.current) {
                offeredRef.current = true;
                appendTurn({
                  role: "assistant",
                  text: "We've been at this a little while — would you like me to pass this to the team, so a person can pick it up?",
                  citations: [],
                });
                setEscalation({ stage: "offer", question });
              }
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
    appendTurn({ role: "visitor", text: "Yes", collecting: true });
    appendTurn({
      role: "assistant",
      text: "Sure — what's your email address? I'll pass this on to the team so they can get back to you.",
      citations: [],
      collecting: true,
    });
    setEscalation({ stage: "email", question: escalation.question });
  }

  // "No" -- acknowledges and lets the conversation carry on exactly as it
  // would have if nothing had gone wrong.
  function declineEscalation() {
    if (escalation.stage !== "offer") return;
    appendTurn({ role: "visitor", text: "No", collecting: true });
    appendTurn({
      role: "assistant",
      text: "No problem — ask away if anything else comes to mind.",
      citations: [],
      collecting: true,
    });
    setEscalation({ stage: "closed" });
  }

  /** "Create a support ticket", chosen before anything was asked. There is
   *  no question to attach yet, so collect one -- the same field the bot
   *  would otherwise have inferred from what the visitor asked. */
  function startTicket() {
    appendTurn({
      role: "assistant",
      text: "Of course. What's the problem? A sentence or two is plenty — I'll pass it to the team.",
      citations: [],
      collecting: true,
    });
    setEscalation({ stage: "issue" });
  }

  /** The composer's reply while `escalation.stage === "issue"`: the
   *  problem itself, which becomes the ticket's message. */
  function submitIssue(raw: string) {
    if (escalation.stage !== "issue") return;
    appendTurn({ role: "visitor", text: raw, collecting: true });
    appendTurn({
      role: "assistant",
      text: "Thanks. What's the best email address to reach you on?",
      citations: [],
      collecting: true,
    });
    setEscalation({ stage: "email", question: raw });
  }

  // The composer's reply while `escalation.stage === "email"`. A
  // not-quite-an-address reply reprompts rather than filing anything --
  // the ticket would only bounce back from the API's own `EmailStr`
  // later, after a round trip the visitor has no way to see coming.
  function submitEmail(raw: string) {
    if (escalation.stage !== "email") return;
    appendTurn({ role: "visitor", text: raw, collecting: true });
    if (!looksLikeEmail(raw)) {
      appendTurn({
        role: "assistant",
        text: "That doesn't quite look like an email address — mind trying again?",
        citations: [],
        collecting: true,
      });
      return;
    }
    appendTurn({
      role: "assistant",
      text: 'Thanks. And your name, if you\'d like to share it — or just say "skip".',
      citations: [],
      collecting: true,
    });
    setEscalation({ stage: "name", question: escalation.question, email: raw });
  }

  // The composer's reply while `escalation.stage === "name"`, and the
  // dedicated Skip button both funnel through here -- an empty reply and
  // the word "skip" mean the same thing (spec: name is optional).
  function submitName(raw: string) {
    if (escalation.stage !== "name") return;
    const skipped = isSkip(raw);
    appendTurn({ role: "visitor", text: skipped ? "Skip" : raw, collecting: true });
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
      collecting: true,
    });

    if (!onSubmit) {
      appendTurn({
        role: "assistant",
        text: "This widget isn't set up to send messages right now, so that hasn't gone anywhere. Sorry about that.",
        citations: [],
        collecting: true,
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
          collecting: true,
        });
        setEscalation({ stage: "closed" });
      } else {
        appendTurn({
          role: "assistant",
          text: `That didn't send: ${result.message} Want to try again?`,
          citations: [],
          collecting: true,
        });
        setEscalation({ stage: "failed", question, email, name, message: result.message });
      }
    } catch {
      appendTurn({
        role: "assistant",
        text: "I couldn't reach the server, so that hasn't sent yet. Want to try again?",
        citations: [],
        collecting: true,
      });
      setEscalation({ stage: "failed", question, email, name, message: "network" });
    }
  }

  function retryFiling() {
    if (escalation.stage !== "failed") return;
    void fileTicket(escalation.question, escalation.email, escalation.name);
  }

  const busy = asking || escalation.stage === "filing";

  // The last assistant turn that is part of the conversation rather than
  // the escalation dialogue -- the only one that carries the button.
  const lastAnswerIndex = turns.reduce(
    (found, turn, index) =>
      turn.role === "assistant" && !turn.collecting ? index : found,
    -1,
  );

  /** "Pass this to the team", from under an answer. The visitor's own last
   *  question is what the ticket is about, so it needs no collecting. */
  function startTicketFromConversation() {
    const asked = [...turnsRef.current]
      .reverse()
      .find((turn) => turn.role === "visitor" && !turn.collecting);
    if (!asked) {
      startTicket();
      return;
    }
    offeredRef.current = true;
    appendTurn({
      role: "assistant",
      text: "Of course. What's the best email address to reach you on?",
      citations: [],
      collecting: true,
    });
    setEscalation({ stage: "email", question: asked.text });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = typed.trim();
    if (!text || busy) return;
    setTyped("");

    if (escalation.stage === "issue") {
      submitIssue(text);
      return;
    }
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

        {/* Both ways in, offered upfront. A visitor who already knows they
            want a person should not have to ask the bot first and wait to
            be turned down, and one who wants an answer should not have to
            guess that typing is allowed. Shown only on a fresh
            conversation -- once either has been taken, the conversation
            itself is the interface. */}
        {turns.length === 0 && escalation.stage === "closed" && (
          <div className="flex flex-col gap-2 pt-1">
            <button
              type="button"
              onClick={() => inputRef.current?.focus()}
              className="rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-left text-[13px] transition-colors hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:hover:border-ink-600"
            >
              <span className="block font-medium text-ink-900 dark:text-white">
                Ask a question
              </span>
              <span className="block text-[12px] text-ink-500 dark:text-ink-400">
                Answered from our help articles, with links
              </span>
            </button>
            <button
              type="button"
              onClick={startTicket}
              className="rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-left text-[13px] transition-colors hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:hover:border-ink-600"
            >
              <span className="block font-medium text-ink-900 dark:text-white">
                Create a support ticket
              </span>
              <span className="block text-[12px] text-ink-500 dark:text-ink-400">
                Goes straight to the team, no bot in the way
              </span>
            </button>
          </div>
        )}

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
              {/* Under the latest answer, always. A visitor who has just
                  read something that did not help should not have to work
                  out that a person is reachable, and the bot cannot do it
                  for them -- it has no way to file anything, and saying
                  otherwise is how it ends up promising help that never
                  comes. Only the latest, so the column does not fill with
                  the same button after every turn. */}
              {!turn.collecting &&
                index === lastAnswerIndex &&
                escalation.stage === "closed" && (
                  <button
                    type="button"
                    onClick={startTicketFromConversation}
                    className="rounded-full border border-ink-200 bg-white px-3 py-1.5 text-[12px] font-medium text-ink-700 transition-colors hover:border-ink-300 hover:text-ink-900 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200 dark:hover:text-white"
                  >
                    Pass this to the team
                  </button>
                )}
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
          ref={inputRef}
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
