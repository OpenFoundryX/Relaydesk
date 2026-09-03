import {
  Ban,
  Circle,
  CircleCheck,
  CircleDashed,
  CircleMinus,
  Trash2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { ConversationStatus } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

export const statusMeta: Record<
  ConversationStatus,
  { label: string; icon: LucideIcon; tone: string }
> = {
  open: { label: "Open", icon: Circle, tone: "text-sky-600" },
  pending: { label: "Pending", icon: CircleDashed, tone: "text-amber-600" },
  on_hold: { label: "On hold", icon: CircleMinus, tone: "text-orange-600" },
  resolved: { label: "Resolved", icon: CircleCheck, tone: "text-positive-600" },
  ignored: { label: "Ignored", icon: Ban, tone: "text-ink-400" },
  trash: { label: "Trash", icon: Trash2, tone: "text-ink-400" },
};

export function StatusIcon({
  status,
  className,
}: {
  status: ConversationStatus;
  className?: string;
}) {
  const meta = statusMeta[status];
  return <meta.icon className={cn("size-3.5 shrink-0", meta.tone, className)} aria-hidden />;
}

/** Inline status pill, e.g. in the timeline or details panel. */
export function StatusPill({ status }: { status: ConversationStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-ink-200 bg-ink-50 px-2 py-0.5 text-[12px] font-medium text-ink-800">
      <StatusIcon status={status} className="size-3" />
      {statusMeta[status].label}
    </span>
  );
}
