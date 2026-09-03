"use client";

import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  CircleDot,
  Flag,
  Globe,
  Hash,
  Mail,
  Sparkles,
  Tag,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState, useTransition, type ReactNode } from "react";

import { generateSummaryAction } from "@/app/(console)/conversations/actions";
import { AssigneePicker, LabelPicker, PriorityPicker, StatusPicker } from "@/components/inbox/pickers";
import { StatusPill } from "@/components/inbox/status-meta";
import { Button } from "@/components/ui/button";
import type { ActivityEvent, Conversation, Label, TeamMember } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

export function DetailsSidebar({
  conversation,
  activity,
  labels,
  team,
  workspaceName,
}: {
  conversation: Conversation;
  activity: ActivityEvent[];
  labels: Label[];
  team: TeamMember[];
  workspaceName: string;
}) {
  return (
    <aside className="flex w-[22rem] shrink-0 flex-col overflow-y-auto border-l border-ink-200 bg-white">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-ink-200 px-4">
        <span className="flex size-6 items-center justify-center rounded-full bg-ink-900 text-[10px] font-semibold uppercase text-white">
          {conversation.customerName
            .split(" ")
            .map((part) => part[0])
            .join("")
            .slice(0, 2)}
        </span>
        <span className="truncate text-[13px] font-semibold text-ink-900">
          {conversation.customerName}
        </span>
      </div>

      <Section title="Details">
        <DetailRow icon={Mail}>
          <span className="truncate text-[13px] text-ink-800">{conversation.customerEmail}</span>
        </DetailRow>
        <DetailRow icon={Hash}>
          <span className="tabular text-[13px] text-ink-800">{conversation.number}</span>
        </DetailRow>
        <DetailRow icon={Globe}>
          <span className="text-[13px] text-ink-800">{workspaceName}</span>
        </DetailRow>
        <DetailRow icon={CircleDot}>
          <StatusPicker conversationId={conversation.id} status={conversation.status} />
        </DetailRow>
        <DetailRow icon={Flag}>
          <PriorityPicker conversationId={conversation.id} priority={conversation.priority} />
        </DetailRow>
        <DetailRow icon={UserRound}>
          <AssigneePicker conversationId={conversation.id} assignee={conversation.assignee} team={team} />
        </DetailRow>
        <DetailRow icon={Tag}>
          <LabelPicker conversationId={conversation.id} labelIds={conversation.labelIds} labels={labels} />
        </DetailRow>
      </Section>

      <Section title="Summary">
        <Summary conversation={conversation} />
      </Section>

      <Section title="Timeline">
        <Timeline events={activity} />
      </Section>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border-b border-ink-200">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex h-11 w-full items-center px-4 text-left"
      >
        <span className="text-[14px] font-semibold text-ink-900">{title}</span>
        <ChevronDown
          className={cn("ml-auto size-4 text-ink-400 transition-transform", !open && "-rotate-90")}
          aria-hidden
        />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

function DetailRow({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <div className="flex min-h-8 items-center gap-3 py-0.5">
      <Icon className="size-4 shrink-0 text-ink-400" aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function Summary({ conversation }: { conversation: Conversation }) {
  const [pending, start] = useTransition();
  const generate = () => start(() => generateSummaryAction(conversation.id));

  if (conversation.summaryState === "ready" && conversation.summary) {
    return <p className="text-[13px] leading-relaxed text-ink-700">{conversation.summary}</p>;
  }
  if (conversation.summaryState === "failed") {
    return (
      <div className="space-y-2">
        <p className="text-[13px] text-danger-600">Failed to generate summary</p>
        <Button size="sm" variant="secondary" disabled={pending} onClick={generate}>
          Try again
        </Button>
      </div>
    );
  }
  return (
    <Button size="sm" variant="secondary" disabled={pending} onClick={generate}>
      <Sparkles />
      {pending ? "Summarising…" : "Generate summary"}
    </Button>
  );
}

function Timeline({ events }: { events: ActivityEvent[] }) {
  const [newestFirst, setNewestFirst] = useState(true);
  const ordered = newestFirst ? events : [...events].reverse();
  const Arrow = newestFirst ? ArrowDown : ArrowUp;

  return (
    <div>
      <button
        type="button"
        onClick={() => setNewestFirst((value) => !value)}
        className="mb-3 inline-flex items-center gap-1 text-[12px] text-ink-500 hover:text-ink-900"
      >
        <Arrow className="size-3" aria-hidden />
        {newestFirst ? "Newest first" : "Oldest first"}
      </button>
      <ol className="relative space-y-4 before:absolute before:bottom-2 before:left-3 before:top-2 before:w-px before:bg-ink-200">
        {ordered.map((event) => (
          <li key={event.id} className="relative flex gap-3">
            <span className="relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full bg-ink-900 text-[9px] font-semibold uppercase text-white ring-2 ring-white">
              {event.actor
                .split(" ")
                .map((part) => part[0])
                .join("")
                .slice(0, 2)}
            </span>
            <div className="min-w-0 text-[12px] leading-5 text-ink-500">
              <p className="flex flex-wrap items-center gap-x-1">
                <span className="font-medium text-ink-900">{event.actor}</span>
                {event.verb}
                {event.status ? (
                  <StatusPill status={event.status} />
                ) : (
                  <span className="font-medium text-ink-800">{event.value}</span>
                )}
              </p>
              <p className="text-[11px] text-ink-400">{event.at}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
