import { cn } from "@/lib/utils";

/**
 * The marketing wordmark.
 *
 * Same two-chevron relay hand-off as the console mark in
 * `components/console/logo`, recut for Steep: the tile is ink-black, the
 * chevrons are paper-white, and the name is set in the display serif. Kept
 * separate from the console mark so the product chrome does not inherit it.
 */
export function SiteLogoMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-7 items-center justify-center rounded-[8px] bg-ink-black",
        className,
      )}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" fill="none" className="size-[17px]">
        <path
          d="M5 7l5 5-5 5"
          stroke="#ffffff"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.55"
        />
        <path
          d="M13 7l5 5-5 5"
          stroke="#ffffff"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export function SiteLogo({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <SiteLogoMark />
      <span className="font-display text-[20px] font-normal leading-none tracking-[-0.3px] text-ink-black">
        Relaydesk
      </span>
    </span>
  );
}
