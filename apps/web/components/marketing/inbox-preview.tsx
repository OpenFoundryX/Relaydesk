import { Bot, Inbox, Mail, Sparkles } from "lucide-react";

import { BrandIcon } from "@/components/marketing/brand-icons";

import { PriorityPip } from "@/components/inbox/priority-pip";
import type { Priority } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

interface PreviewRow {
  subject: string;
  customer: string;
  preview: string;
  priority: Priority;
  age: string;
  channel: "email" | "discord" | "portal";
  status: "AI resolved" | "Drafted" | "Assigned" | "Needs you";
  unread?: boolean;
}

const rows: PreviewRow[] = [
  {
    subject: "Checkout is down for all our users",
    customer: "Priya N.",
    preview: "Getting a 502 on /checkout since 9:40. Paying customers can't complete orders.",
    priority: "urgent",
    age: "4m",
    channel: "email",
    status: "Assigned",
    unread: true,
  },
  {
    subject: "Refund for duplicate charge",
    customer: "Marcus L.",
    preview: "I was charged twice for order #48213 yesterday. Can you sort it out?",
    priority: "high",
    age: "12m",
    channel: "email",
    status: "AI resolved",
  },
  {
    subject: "When does my plan renew?",
    customer: "Aiko T.",
    preview: "Just want to know the renewal date before I add two more seats.",
    priority: "medium",
    age: "31m",
    channel: "discord",
    status: "AI resolved",
  },
  {
    subject: "Export to CSV missing columns",
    customer: "Devon R.",
    preview: "The export doesn't include the tags column that shows in the table view.",
    priority: "medium",
    age: "1h",
    channel: "portal",
    status: "Drafted",
  },
  {
    subject: "Feature request: dark mode",
    customer: "Sofia B.",
    preview: "Would love a dark theme for the dashboard. Happy to beta test.",
    priority: "low",
    age: "3h",
    channel: "discord",
    status: "Needs you",
  },
];

const statusStyles: Record<PreviewRow["status"], string> = {
  "AI resolved": "bg-accent-100 text-accent-950",
  Drafted: "bg-ink-100 text-ink-600",
  Assigned: "bg-ink-900 text-white",
  "Needs you": "border border-ink-200 text-ink-600",
};

const sidebar = [
  { label: "Open", count: 5, active: true },
  { label: "Pending", count: 12 },
  { label: "On hold", count: 2 },
  { label: "Resolved", count: 418 },
];

/**
 * A static rendering of the console inbox for the marketing hero. Kept as
 * plain markup so the page stays a server component and ships no JS.
 */
export function InboxPreview({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-ink-200 bg-white shadow-overlay",
        className,
      )}
      aria-label="Preview of the Relaydesk inbox"
      role="img"
    >
      <div className="flex h-10 items-center gap-2 border-b border-ink-200 px-4">
        <span className="size-2.5 rounded-full bg-ink-200" />
        <span className="size-2.5 rounded-full bg-ink-200" />
        <span className="size-2.5 rounded-full bg-ink-200" />
        <span className="ml-3 text-[12px] font-medium text-ink-500">Chronon · Inbox</span>
        <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-accent-100 px-2 py-0.5 text-[11px] font-medium text-accent-950">
          <Sparkles className="size-3" />
          AI triage on
        </span>
      </div>
      <div className="grid grid-cols-[150px_1fr]">
        <aside className="hidden border-r border-ink-200 bg-ink-50 p-3 sm:block">
          <p className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-400">
            Conversations
          </p>
          <ul className="space-y-0.5">
            {sidebar.map((item) => (
              <li
                key={item.label}
                className={cn(
                  "flex items-center justify-between rounded-md px-2 py-1.5 text-[12px]",
                  item.active
                    ? "bg-white font-medium text-ink-900 shadow-sm"
                    : "text-ink-600",
                )}
              >
                {item.label}
                <span className="tabular text-[11px] text-ink-400">{item.count}</span>
              </li>
            ))}
          </ul>
          <p className="mt-5 px-2 pb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-400">
            Views
          </p>
          <ul className="space-y-0.5 text-[12px] text-ink-600">
            <li className="px-2 py-1.5">Assigned to me</li>
            <li className="px-2 py-1.5">Enterprise</li>
            <li className="px-2 py-1.5">Billing</li>
          </ul>
        </aside>
        <ul className="col-span-2 divide-y divide-ink-100 sm:col-span-1">
          {rows.map((row) => (
            <li key={row.subject} className="flex items-center gap-3 px-4 py-3">
              <PriorityPip priority={row.priority} />
              <span className="shrink-0" title={row.channel}>
                {row.channel === "discord" ? (
                  <BrandIcon brand="discord" className="size-3.5" />
                ) : row.channel === "email" ? (
                  <Mail className="size-3.5 text-ink-400" aria-hidden />
                ) : (
                  <Inbox className="size-3.5 text-ink-400" aria-hidden />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "truncate text-[13px]",
                      row.unread ? "font-semibold text-ink-900" : "font-medium text-ink-800",
                    )}
                  >
                    {row.subject}
                  </span>
                  <span className="hidden shrink-0 text-[12px] text-ink-400 md:inline">
                    {row.customer}
                  </span>
                </div>
                <p className="truncate text-[12px] text-ink-500">{row.preview}</p>
              </div>
              <span
                className={cn(
                  "hidden shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium sm:inline-flex",
                  statusStyles[row.status],
                )}
              >
                {row.status === "AI resolved" && <Bot className="size-3" />}
                {row.status}
              </span>
              <span className="tabular w-7 shrink-0 text-right text-[11px] text-ink-400">
                {row.age}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
