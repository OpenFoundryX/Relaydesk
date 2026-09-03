"use client";

import { Check, Trash2, X } from "lucide-react";
import { useState, useTransition } from "react";

import { setStatusBulkAction } from "@/app/(console)/conversations/actions";
import { ConversationRow } from "@/components/inbox/conversation-row";
import { Button } from "@/components/ui/button";
import type { Conversation, Label, TeamMember } from "@/lib/mock/types";

export function InboxList({
  conversations,
  labels,
  team,
}: {
  conversations: Conversation[];
  labels: Label[];
  team: TeamMember[];
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pending, start] = useTransition();

  const toggle = (id: string, value: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (value) next.add(id);
      else next.delete(id);
      return next;
    });

  const bulk = (status: "resolved" | "trash") =>
    start(async () => {
      await setStatusBulkAction([...selected], status);
      setSelected(new Set());
    });

  return (
    <>
      {selected.size > 0 && (
        <div className="flex h-10 shrink-0 items-center gap-2 border-b border-ink-200 bg-accent-50 px-4 text-[13px] text-ink-800">
          <span className="tabular font-medium">{selected.size} selected</span>
          <Button size="sm" variant="secondary" disabled={pending} onClick={() => bulk("resolved")}>
            <Check />
            Resolve
          </Button>
          <Button size="sm" variant="secondary" disabled={pending} onClick={() => bulk("trash")}>
            <Trash2 />
            Trash
          </Button>
          <button
            type="button"
            onClick={() => setSelected(new Set())}
            className="ml-auto rounded p-1 text-ink-500 hover:text-ink-900"
            aria-label="Clear selection"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {conversations.map((conversation) => (
          <ConversationRow
            key={conversation.id}
            conversation={conversation}
            labels={labels}
            team={team}
            selected={selected.has(conversation.id)}
            onSelectedChange={(value) => toggle(conversation.id, value)}
          />
        ))}
      </ul>
    </>
  );
}
