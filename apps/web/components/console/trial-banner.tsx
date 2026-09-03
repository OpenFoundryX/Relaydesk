import Link from "next/link";
import { Clock } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Full-width strip above the console chrome while a workspace is on trial. */
export function TrialBanner({ daysLeft }: { daysLeft: number }) {
  return (
    <div className="flex h-11 shrink-0 items-center gap-2 border-b border-accent-200 bg-accent-50 px-4">
      <Clock className="size-4 text-accent-800" aria-hidden />
      <p className="text-[13px] text-ink-800">
        <span className="font-medium">{daysLeft} days left</span> in your free trial.
      </p>
      <Button asChild size="sm" variant="primary" className="ml-auto">
        <Link href="/settings/billing">Buy now</Link>
      </Button>
    </div>
  );
}
