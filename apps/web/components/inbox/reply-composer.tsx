"use client";

import { Sparkles } from "lucide-react";
import { useLayoutEffect, useRef, useState, useTransition } from "react";

import { discardDraftAction, sendReplyAction } from "@/app/(console)/conversations/actions";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { matchSnippets } from "@/lib/snippets/match";
import { renderSnippet, type SnippetContext } from "@/lib/snippets/render";
import {
  applySnippet,
  snippetTrigger,
  type SnippetTrigger,
} from "@/lib/snippets/trigger";
import { cn } from "@/lib/utils";
import type { Snippet } from "@/lib/types";

export function ReplyComposer({
  conversationId,
  customerEmail,
  from,
  draft,
  snippets,
  snippetContext,
}: {
  conversationId: string;
  customerEmail: string;
  from: string;
  draft: string | null;
  snippets: Snippet[];
  snippetContext: SnippetContext;
}) {
  const [body, setBody] = useState(draft ?? "");
  const [trigger, setTrigger] = useState<SnippetTrigger | null>(null);
  const [highlight, setHighlight] = useState(0);
  // Set only when a snippet has just been inserted, to put the caret after
  // it. React re-renders the textarea from `body` and would otherwise leave
  // the caret at the end of the reply rather than the end of the insertion.
  const caret = useRef<number | null>(null);
  const [pending, start] = useTransition();
  const field = useRef<HTMLTextAreaElement>(null);
  const usingDraft = draft !== null && body === draft;

  const matches = trigger ? matchSnippets(snippets, trigger.query) : [];
  // A trigger with nothing to offer is not a menu. Typing `/zzz` leaves the
  // text alone and gets out of the way.
  const open = matches.length > 0;
  const selected = matches[Math.min(highlight, matches.length - 1)];

  useLayoutEffect(() => {
    const at = caret.current;
    if (at === null) return;
    caret.current = null;
    field.current?.focus();
    field.current?.setSelectionRange(at, at);
  }, [body]);

  const send = (resolve: boolean) =>
    start(async () => {
      await sendReplyAction(conversationId, body, resolve);
      setBody("");
      setTrigger(null);
    });

  function edit(event: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = event.target.value;
    setBody(value);
    setTrigger(snippetTrigger(value, event.target.selectionStart ?? value.length));
    setHighlight(0);
  }

  function insert(snippet: Snippet) {
    if (!trigger) return;
    const next = applySnippet(
      body,
      trigger,
      renderSnippet(snippet.content, snippetContext),
    );
    setBody(next.value);
    setTrigger(null);
    caret.current = next.caret;
  }

  function navigate(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((current) => (current + 1) % matches.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((current) => (current - 1 + matches.length) % matches.length);
    } else if (event.key === "Enter") {
      // The menu owns Enter for as long as it is open: no newline, and
      // nothing that could send a reply with a bare `/gre` still in it.
      event.preventDefault();
      if (selected) insert(selected);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setTrigger(null);
    }
  }

  return (
    <div className="shrink-0 border-t border-ink-200 bg-white px-4 py-3">
      <div className="relative rounded-lg border border-ink-200 focus-within:border-ink-300">
        {open && (
          <ul
            role="listbox"
            aria-label="Snippets"
            className="absolute bottom-full left-0 z-10 mb-1 max-h-56 w-64 overflow-y-auto rounded-md border border-ink-200 bg-white py-1 shadow-lg"
          >
            {matches.map((snippet, index) => (
              <li key={snippet.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={snippet.id === selected?.id}
                  // The textarea keeps focus so the caret survives, so the
                  // press must land before the blur that mousedown starts.
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => insert(snippet)}
                  onMouseEnter={() => setHighlight(index)}
                  className={cn(
                    "block w-full px-3 py-1.5 text-left text-[13px] text-ink-700",
                    snippet.id === selected?.id && "bg-ink-100 text-ink-900",
                  )}
                >
                  {snippet.title}
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="flex flex-wrap items-center gap-x-1.5 border-b border-ink-100 px-3 py-2 text-[12px] text-ink-500">
          <span className="font-medium text-ink-700">From</span> {from}
          <span className="text-ink-300">·</span>
          {usingDraft && (
            <span className="inline-flex items-center gap-1 font-medium text-accent-800">
              <Sparkles className="size-3" aria-hidden />
              AI draft
            </span>
          )}
          <span className="font-medium text-ink-700">To</span> {customerEmail}
        </p>
        <Textarea
          ref={field}
          value={body}
          onChange={edit}
          onKeyDown={navigate}
          placeholder="Write a reply, or type / to insert a snippet…"
          aria-label="Reply"
          className="min-h-28 resize-y border-0 px-3 py-2.5 focus-visible:ring-0"
        />
      </div>
      <div className="mt-2 flex items-center gap-2">
        {draft !== null && (
          <Button
            size="sm"
            variant="ghost"
            disabled={pending}
            onClick={() =>
              start(async () => {
                await discardDraftAction(conversationId);
                setBody("");
              })
            }
          >
            Discard draft
          </Button>
        )}
        <div className="flex-1" />
        <Button size="sm" variant="secondary" disabled={pending || !body.trim()} onClick={() => send(true)}>
          Send &amp; resolve
        </Button>
        <Button size="sm" variant="primary" disabled={pending || !body.trim()} onClick={() => send(false)}>
          Send reply
        </Button>
      </div>
    </div>
  );
}
