import { cn } from "@/lib/utils";

/**
 * Relaydesk mark: two offset chevrons reading as a relay hand-off, cut out of
 * an ink tile with a citron leading edge.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-6 items-center justify-center rounded-md bg-ink-900",
        className,
      )}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" fill="none" className="size-4">
        <path
          d="M5 7l5 5-5 5"
          stroke="#C4E538"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M13 7l5 5-5 5"
          stroke="#FAFAFA"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-tight text-ink-900">
        Relaydesk
      </span>
    </span>
  );
}
