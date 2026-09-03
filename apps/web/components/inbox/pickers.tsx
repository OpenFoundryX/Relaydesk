"use client";

import { Plus, Tag, UserRound } from "lucide-react";
import { useTransition, type ReactNode } from "react";

import {
  createLabelAction,
  setAssigneeAction,
  setPriorityAction,
  setStatusAction,
  toggleLabelAction,
} from "@/app/(console)/conversations/actions";
import { CommandPopover } from "@/components/inbox/command-popover";
import { PriorityPip } from "@/components/inbox/priority-pip";
import { StatusIcon, statusMeta } from "@/components/inbox/status-meta";
import type {
  ConversationStatus,
  Label,
  Priority,
  TeamMember,
} from "@/lib/mock/types";
import { cn } from "@/lib/utils";

const statusOrder: ConversationStatus[] = ["open", "pending", "on_hold", "resolved", "ignored", "trash"];
const priorityOrder: Priority[] = ["low", "medium", "high", "urgent"];
const priorityLabel: Record<Priority, string> = { low: "Low", medium: "Medium", high: "High", urgent: "Urgent" };

type Variant = "pill" | "icon" | "chip";

/** Shared trigger so every picker looks the same wherever it is placed. */
export function PickerTrigger({
  variant,
  label,
  children,
  className,
  ...props
}: {
  variant: Variant;
  label: string;
  children: ReactNode;
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex items-center gap-1.5 transition-colors",
        variant === "pill" &&
          "h-7 rounded-full border border-ink-200 bg-ink-50 px-2.5 text-[13px] font-medium text-ink-800 hover:border-ink-300 hover:bg-white",
        variant === "chip" &&
          "h-6 rounded-full border border-ink-200 bg-white px-2 text-[12px] font-medium text-ink-600 hover:border-ink-300 hover:text-ink-900",
        variant === "icon" &&
          "flex size-6 items-center justify-center rounded text-ink-400 hover:bg-ink-100 hover:text-ink-900 [&_svg]:size-3.5",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function StatusPicker({
  conversationId,
  status,
  variant = "pill",
  className,
}: {
  conversationId: string;
  status: ConversationStatus;
  variant?: Variant;
  className?: string;
}) {
  const [, start] = useTransition();
  return (
    <CommandPopover
      placeholder="Select status..."
      heading="Set status"
      items={statusOrder.map((value, index) => ({
        id: value,
        label: statusMeta[value].label,
        icon: <StatusIcon status={value} />,
        shortcut: String(index + 1),
        selected: value === status,
      }))}
      onSelect={(id) => start(() => setStatusAction(conversationId, id as ConversationStatus))}
      trigger={
        <PickerTrigger variant={variant} label="Change status" className={className}>
          <StatusIcon status={status} />
          {variant === "pill" && statusMeta[status].label}
        </PickerTrigger>
      }
    />
  );
}

export function PriorityPicker({
  conversationId,
  priority,
  variant = "pill",
  className,
}: {
  conversationId: string;
  priority: Priority;
  variant?: Variant;
  className?: string;
}) {
  const [, start] = useTransition();
  return (
    <CommandPopover
      placeholder="Select priority..."
      heading="Set priority"
      items={priorityOrder.map((value, index) => ({
        id: value,
        label: priorityLabel[value],
        icon: <PriorityPip priority={value} />,
        shortcut: String(index + 1),
        selected: value === priority,
      }))}
      onSelect={(id) => start(() => setPriorityAction(conversationId, id as Priority))}
      trigger={
        <PickerTrigger variant={variant} label="Change priority" className={className}>
          <PriorityPip priority={priority} />
          {variant === "pill" && priorityLabel[priority]}
        </PickerTrigger>
      }
    />
  );
}

function Monogram({ name, className }: { name: string; className?: string }) {
  return (
    <span
      className={cn(
        "flex size-5 items-center justify-center rounded-full bg-ink-900 text-[9px] font-semibold uppercase text-white",
        className,
      )}
    >
      {name
        .split(" ")
        .map((part) => part[0])
        .join("")
        .slice(0, 2)}
    </span>
  );
}

export function AssigneePicker({
  conversationId,
  assignee,
  team,
  variant = "pill",
  className,
}: {
  conversationId: string;
  assignee: string | null;
  team: TeamMember[];
  variant?: Variant;
  className?: string;
}) {
  const [, start] = useTransition();
  return (
    <CommandPopover
      placeholder="Search team members..."
      heading="Assign to"
      items={[
        {
          id: "__unassigned",
          label: "Unassigned",
          icon: <span className="size-4 rounded-full border border-dashed border-ink-300" />,
          shortcut: "1",
          selected: assignee === null,
        },
        ...team.map((member, index) => ({
          id: member.name,
          label: member.name,
          hint: member.email,
          icon: <Monogram name={member.name} className="size-4 text-[8px]" />,
          shortcut: String(index + 2),
          selected: member.name === assignee,
        })),
      ]}
      onSelect={(id) =>
        start(() => setAssigneeAction(conversationId, id === "__unassigned" ? null : id))
      }
      trigger={
        <PickerTrigger variant={variant} label="Assign" className={className}>
          {assignee ? (
            <>
              <Monogram name={assignee} className="size-4 text-[8px]" />
              {variant !== "icon" && assignee}
            </>
          ) : variant === "icon" ? (
            <UserRound />
          ) : (
            <>
              <Plus className="size-3 text-ink-400" aria-hidden />
              Assignee
            </>
          )}
        </PickerTrigger>
      }
    />
  );
}

const swatch: Record<Label["color"], string> = {
  citron: "bg-accent-500",
  amber: "bg-amber-400",
  rose: "bg-rose-400",
  sky: "bg-sky-400",
  slate: "bg-ink-400",
};

export function LabelSwatch({ color, className }: { color: Label["color"]; className?: string }) {
  return <span className={cn("size-2 shrink-0 rounded-[3px]", swatch[color], className)} aria-hidden />;
}

export function LabelPicker({
  conversationId,
  labelIds,
  labels,
  variant = "pill",
  className,
}: {
  conversationId: string;
  labelIds: string[];
  labels: Label[];
  variant?: Variant;
  className?: string;
}) {
  const [, start] = useTransition();
  const applied = labels.filter((label) => labelIds.includes(label.id));
  return (
    <CommandPopover
      placeholder="Search or create labels..."
      heading="Labels"
      emptyText="No labels yet. Create your first label below."
      stayOpen
      items={labels.map((label) => ({
        id: label.id,
        label: label.name,
        icon: <LabelSwatch color={label.color} />,
        selected: labelIds.includes(label.id),
      }))}
      onSelect={(id) => start(() => toggleLabelAction(conversationId, id))}
      footer={(query, close) => {
        const name = query.trim();
        const exists = labels.some((label) => label.name.toLowerCase() === name.toLowerCase());
        return (
          <button
            type="button"
            disabled={exists}
            onClick={() => {
              if (!name) return;
              start(async () => {
                await createLabelAction(name, conversationId);
              });
              close();
            }}
            className="flex h-8 w-full items-center gap-2 rounded-md px-2 text-[13px] text-ink-800 transition-colors hover:bg-ink-100 disabled:opacity-50"
          >
            <Plus className="size-3.5 text-ink-500" aria-hidden />
            {name ? `Create "${name}"` : "Create new label"}
          </button>
        );
      }}
      trigger={
        <PickerTrigger variant={variant} label="Add label" className={className}>
          {variant === "icon" ? (
            <Tag />
          ) : applied.length > 0 ? (
            <>
              {applied.slice(0, 2).map((label) => (
                <span key={label.id} className="inline-flex items-center gap-1">
                  <LabelSwatch color={label.color} />
                  {label.name}
                </span>
              ))}
              {applied.length > 2 && <span className="text-ink-400">+{applied.length - 2}</span>}
            </>
          ) : (
            <>
              <Plus className="size-3 text-ink-400" aria-hidden />
              Label
            </>
          )}
        </PickerTrigger>
      }
    />
  );
}
