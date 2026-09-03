import type { Priority } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

const levels: Record<Priority, number> = { low: 1, medium: 2, high: 3, urgent: 4 };

const tone: Record<Priority, string> = {
  low: "bg-ink-300",
  medium: "bg-ink-400",
  high: "bg-accent-700",
  urgent: "bg-danger-600",
};

/** Four ascending bars; filled bars encode the priority level. */
export function PriorityPip({ priority }: { priority: Priority }) {
  const level = levels[priority];
  return (
    <span
      className="flex h-3.5 items-end gap-px"
      title={`Priority: ${priority}`}
      aria-label={`Priority ${priority}`}
    >
      {[1, 2, 3, 4].map((bar) => (
        <span
          key={bar}
          className={cn(
            "w-[3px] rounded-[1px]",
            bar <= level ? tone[priority] : "bg-ink-200",
          )}
          style={{ height: `${bar * 25}%` }}
        />
      ))}
    </span>
  );
}
