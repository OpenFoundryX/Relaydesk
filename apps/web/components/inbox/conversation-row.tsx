"use client";

import Link from "next/link";
import { Check, Trash2 } from "lucide-react";
import { useTransition } from "react";

import { setStatusAction } from "@/app/(console)/conversations/actions";
import { AssigneePicker, LabelPicker, LabelSwatch, StatusPicker } from "@/components/inbox/pickers";
import { PriorityPip } from "@/components/inbox/priority-pip";
import { Checkbox } from "@/components/ui/checkbox";
import type { Conversation, Label, TeamMember } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

interface ConversationRowProps {
  conversation: Conversation;
  labels: Label[];
  team: TeamMember[];
  selected: boolean;
  onSelectedChange: (selected: boolean) => void;
}

export function ConversationRow({
  conversation,
  labels,
  team,
  selected,
  onSelectedChange,
}: ConversationRowProps) {
  const [, start] = useTransition();
  const rowLabels = labels.filter((label) => conversation.labelIds.includes(label.id));

  return (
    <li
      className={cn(
        "group relative flex h-11 items-center gap-3 border-b border-ink-100 pl-3 pr-4 transition-colors last:border-b-0",
        selected ? "bg-accent-50" : "hover:bg-ink-50",
      )}
    >
      {conversation.unread && (
        <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent-600" />
      )}

      <Checkbox
        checked={selected}
        onCheckedChange={(value) => onSelectedChange(value === true)}
        aria-label={`Select ${conversation.subject}`}
        className={cn("transition-opacity", !selected && "opacity-0 group-hover:opacity-100")}
      />

      <span
        className={cn(
          "flex w-44 shrink-0 items-center gap-1.5 truncate text-[13px]",
          conversation.unread ? "font-semibold text-ink-900" : "font-medium text-ink-700",
        )}
      >
        <span className="truncate">{conversation.customerName}</span>
        {conversation.unread && <span className="size-1.5 shrink-0 rounded-full bg-orange-400" />}
      </span>

      <span className="tabular w-8 shrink-0 text-right text-[11px] text-sky-600">
        {conversation.age}
      </span>

      <StatusPicker conversationId={conversation.id} status={conversation.status} variant="icon" />
      <PriorityPip priority={conversation.priority} />

      <Link
        href={`/conversations/${conversation.id}`}
        className={cn(
          "min-w-0 truncate text-[13px] outline-none",
          conversation.unread ? "font-medium text-ink-900" : "text-ink-800",
        )}
      >
        {conversation.subject}
      </Link>

      <AssigneePicker
        conversationId={conversation.id}
        assignee={conversation.assignee}
        team={team}
        variant="chip"
      />

      {rowLabels.map((label) => (
        <span
          key={label.id}
          className="inline-flex shrink-0 items-center gap-1 rounded-full border border-ink-200 px-2 py-0.5 text-[11px] text-ink-600"
        >
          <LabelSwatch color={label.color} />
          {label.name}
        </span>
      ))}

      {conversation.hasDraft && (
        <span className="shrink-0 rounded-full bg-accent-100 px-2 py-0.5 text-[11px] font-medium text-accent-950">
          AI draft
        </span>
      )}

      <span className="ml-auto shrink-0 text-[11px] text-ink-400 group-hover:invisible">
        {conversation.date}
      </span>

      <div className="absolute right-4 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 group-hover:flex">
        <RowAction
          label="Resolve"
          onClick={() => start(() => setStatusAction(conversation.id, "resolved"))}
        >
          <Check />
        </RowAction>
        <RowAction
          label="Move to trash"
          onClick={() => start(() => setStatusAction(conversation.id, "trash"))}
        >
          <Trash2 />
        </RowAction>
        <LabelPicker
          conversationId={conversation.id}
          labelIds={conversation.labelIds}
          labels={labels}
          variant="icon"
        />
      </div>
    </li>
  );
}

function RowAction({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="flex size-6 items-center justify-center rounded text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-900 [&_svg]:size-3.5"
    >
      {children}
    </button>
  );
}
