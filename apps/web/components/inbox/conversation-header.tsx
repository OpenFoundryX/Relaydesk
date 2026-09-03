"use client";

import Link from "next/link";
import { ArrowLeft, Check, ChevronDown, ChevronUp, Hourglass, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { setStatusAction } from "@/app/(console)/conversations/actions";
import { AssigneePicker } from "@/components/inbox/pickers";
import type { Conversation, TeamMember } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

export function ConversationHeader({
  conversation,
  team,
  prevId,
  nextId,
}: {
  conversation: Conversation;
  team: TeamMember[];
  prevId: string | null;
  nextId: string | null;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const listHref = `/conversations?status=${conversation.status}`;

  const move = (status: "resolved" | "on_hold" | "trash") =>
    start(async () => {
      await setStatusAction(conversation.id, status);
      router.push(nextId ? `/conversations/${nextId}` : listHref);
    });

  return (
    <div className="flex h-12 shrink-0 items-center gap-2 border-b border-ink-200 bg-white px-3">
      <Link
        href={listHref}
        aria-label="Back to inbox"
        className="rounded-md p-1.5 text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
      >
        <ArrowLeft className="size-4" />
      </Link>
      <h1 className="truncate text-sm font-semibold tracking-tight text-ink-900">
        {conversation.subject}
      </h1>
      <div className="flex-1" />

      <HeaderAction label="Resolve" disabled={pending} onClick={() => move("resolved")}>
        <Check />
      </HeaderAction>
      <HeaderAction label="Put on hold" disabled={pending} onClick={() => move("on_hold")}>
        <Hourglass />
      </HeaderAction>
      <HeaderAction label="Move to trash" disabled={pending} onClick={() => move("trash")}>
        <Trash2 />
      </HeaderAction>
      <AssigneePicker
        conversationId={conversation.id}
        assignee={conversation.assignee}
        team={team}
        variant="icon"
        className="size-7"
      />

      <span className="mx-1 h-4 w-px bg-ink-200" aria-hidden />

      <NavArrow href={prevId ? `/conversations/${prevId}` : null} label="Previous ticket">
        <ChevronUp />
      </NavArrow>
      <NavArrow href={nextId ? `/conversations/${nextId}` : null} label="Next ticket">
        <ChevronDown />
      </NavArrow>
    </div>
  );
}

const iconButton =
  "flex size-7 items-center justify-center rounded-md text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900 disabled:opacity-40 [&_svg]:size-4";

function HeaderAction({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled} className={iconButton}>
      {children}
    </button>
  );
}

function NavArrow({ href, label, children }: { href: string | null; label: string; children: React.ReactNode }) {
  if (!href) {
    return (
      <span aria-hidden className={cn(iconButton, "opacity-30 hover:bg-transparent")}>
        {children}
      </span>
    );
  }
  return (
    <Link href={href} aria-label={label} title={label} className={iconButton}>
      {children}
    </Link>
  );
}
