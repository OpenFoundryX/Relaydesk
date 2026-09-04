"use client";

import { Button } from "@/components/ui/button";

/**
 * Route-segment error boundary for the console.
 *
 * Server actions under this segment now perform real writes (Task 9), so a
 * rejected action is a real possibility — a conflict, a revoked session, a
 * network fault — not just a bug. Without this boundary, Next.js would show
 * a raw error screen. Keep this small: it is a safety net, not a design
 * exercise, and it must never leak the error's message or stack trace.
 */
export default function ConsoleError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="text-sm font-medium text-ink-900">Something went wrong.</p>
      <p className="text-[13px] text-ink-500">
        The change may not have been saved. Please try again.
      </p>
      <Button size="sm" variant="secondary" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
