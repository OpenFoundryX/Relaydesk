import { cn } from "@/lib/utils";

/**
 * A placeholder block for content that has not arrived.
 *
 * `ink-100` is deliberately low contrast. Every loading screen shows a dozen
 * of these at once, and a placeholder that pulses hard reads as activity
 * rather than as absence -- it competes with the content that replaces it.
 *
 * Purely decorative: the `role="status"` and the accessible name belong on
 * the screen as a whole (see the `loading.tsx` files), not on each block, or
 * a screen reader announces the same nothing a dozen times.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded bg-ink-100", className)} />;
}

/**
 * Wraps a set of skeletons as one announced region. Screen readers get a
 * single "Loading ..." rather than the shape of a page that is not there.
 */
export function SkeletonScreen({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div role="status" aria-busy="true" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
