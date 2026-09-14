import { Artifact } from "@/components/marketing/artifacts";
import type { Priority } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

interface PreviewRow {
  subject: string;
  customer: string;
  preview: string;
  priority: Priority;
  age: string;
  channel: "Email" | "Discord" | "Widget" | "API";
  status: "Closed by AI" | "Drafted" | "Assigned" | "Needs you";
  unread?: boolean;
}

const rows: PreviewRow[] = [
  {
    subject: "Checkout is down for all our users",
    customer: "Priya N.",
    preview: "Getting a 502 on /checkout since 9:40. Paying customers can't complete orders.",
    priority: "urgent",
    age: "4m",
    channel: "Email",
    status: "Assigned",
    unread: true,
  },
  {
    subject: "Refund for duplicate charge",
    customer: "Marcus L.",
    preview: "I was charged twice for order #48213 yesterday. Can you sort it out?",
    priority: "high",
    age: "12m",
    channel: "Email",
    status: "Closed by AI",
  },
  {
    subject: "When does my plan renew?",
    customer: "Aiko T.",
    preview: "Just want to know the renewal date before I add two more seats.",
    priority: "medium",
    age: "31m",
    channel: "Widget",
    status: "Closed by AI",
  },
  {
    subject: "Export to CSV missing columns",
    customer: "Devon R.",
    preview: "The export doesn't include the tags column that shows in the table view.",
    priority: "medium",
    age: "1h",
    channel: "API",
    status: "Drafted",
  },
  {
    subject: "Feature request: dark mode",
    customer: "Sofia B.",
    preview: "Would love a dark theme for the dashboard. Happy to beta test.",
    priority: "low",
    age: "3h",
    channel: "Discord",
    status: "Needs you",
  },
];

/**
 * Status is carried typographically, not by a coloured badge: the system is
 * achromatic apart from the one peach card, so weight and grey level do the
 * work a pill would normally do.
 */
const statusStyles: Record<PreviewRow["status"], string> = {
  "Closed by AI": "text-ink-black font-w450",
  Drafted: "text-slate-gray",
  Assigned: "text-ink-black font-w450",
  "Needs you": "text-slate-gray",
};

const priorityLabel: Record<Priority, string> = {
  urgent: "Urgent",
  high: "High",
  medium: "Medium",
  low: "Low",
};

/**
 * The console inbox, cropped, as a floating product artifact. Plain markup, so
 * the page stays a server component and ships no JS.
 */
export function InboxPreview({ className }: { className?: string }) {
  return (
    <Artifact className={cn("overflow-hidden", className)}>
      <div
        aria-label="Preview of the Relaydesk inbox"
        role="img"
        className="px-5 pb-2 pt-4"
      >
        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
          <p className="text-[14px] text-ash-gray">Chronon · Inbox</p>
          <p className="text-[14px] text-smoke-gray">
            Open 5 · Pending 12 · On hold 2 · Resolved 418
          </p>
        </div>

        <ul className="mt-3">
          {rows.map((row) => (
            <li
              key={row.subject}
              className="flex items-center gap-4 border-t border-hairline py-3"
            >
              <span className="hidden w-14 shrink-0 text-[13px] text-ash-gray sm:inline">
                {priorityLabel[row.priority]}
              </span>
              <span className="hidden w-14 shrink-0 text-[13px] text-smoke-gray md:inline">
                {row.channel}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span
                    className={cn(
                      "truncate text-[15px] text-ink-black",
                      row.unread ? "font-w480" : "font-w430",
                    )}
                  >
                    {row.subject}
                  </span>
                  <span className="hidden shrink-0 text-[13px] text-ash-gray lg:inline">
                    {row.customer}
                  </span>
                </div>
                <p className="truncate text-[13.5px] text-slate-gray">
                  {row.preview}
                </p>
              </div>
              <span
                className={cn(
                  "hidden shrink-0 text-[13.5px] sm:inline",
                  statusStyles[row.status],
                )}
              >
                {row.status}
              </span>
              <span className="tabular w-8 shrink-0 text-right text-[13px] text-smoke-gray">
                {row.age}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Artifact>
  );
}
