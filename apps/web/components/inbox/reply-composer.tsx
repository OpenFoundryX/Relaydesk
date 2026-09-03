"use client";

import { Sparkles } from "lucide-react";
import { useState, useTransition } from "react";

import { discardDraftAction, sendReplyAction } from "@/app/(console)/conversations/actions";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function ReplyComposer({
  conversationId,
  customerEmail,
  from,
  draft,
}: {
  conversationId: string;
  customerEmail: string;
  from: string;
  draft: string | null;
}) {
  const [body, setBody] = useState(draft ?? "");
  const [pending, start] = useTransition();
  const usingDraft = draft !== null && body === draft;

  const send = (resolve: boolean) =>
    start(async () => {
      await sendReplyAction(conversationId, body, resolve);
      setBody("");
    });

  return (
    <div className="shrink-0 border-t border-ink-200 bg-white px-4 py-3">
      <div className="rounded-lg border border-ink-200 focus-within:border-ink-300">
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
          value={body}
          onChange={(event) => setBody(event.target.value)}
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
