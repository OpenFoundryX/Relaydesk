"use client";

import { useState } from "react";
import Link from "next/link";
import { Clock, X } from "lucide-react";

import { Button } from "@/components/ui/button";

export function TrialStrip({ daysLeft, plan }: { daysLeft: number; plan: string }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  return (
    <div className="mb-5 flex items-center gap-3 rounded-lg border border-accent-200 bg-accent-50 px-3 py-2">
      <Clock className="size-4 shrink-0 text-accent-800" />
      <p className="text-[13px] text-ink-700">
        <span className="font-medium text-ink-900">{daysLeft} days left</span> on your{" "}
        {plan} trial. Pick a plan to keep your inbox running.
      </p>
      <div className="ml-auto flex items-center gap-1">
        <Button asChild size="sm" variant="primary">
          <Link href="/settings/billing">Choose a plan</Link>
        </Button>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss trial notice"
          className="rounded p-1 text-ink-400 transition-colors hover:text-ink-900"
        >
          <X className="size-3.5" />
        </button>
      </div>
    </div>
  );
}
