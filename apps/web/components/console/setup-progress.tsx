"use client";

import { ArrowRight } from "lucide-react";

import { useOnboarding } from "@/components/onboarding/onboarding-provider";
import type { SetupTask } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

export function SetupProgress({ tasks }: { tasks: SetupTask[] }) {
  const onboarding = useOnboarding();
  const done = tasks.filter((task) => task.done).length;
  const next = tasks.find((task) => !task.done);

  if (!next) return null;

  return (
    <div className="border-t border-ink-200 p-3">
      <button
        type="button"
        onClick={onboarding.open}
        className="w-full rounded-md border border-ink-200 bg-ink-50 p-3 text-left transition-colors hover:border-ink-300 hover:bg-white"
      >
        <div className="flex items-baseline justify-between">
          <span className="text-[13px] font-medium text-ink-900">Finish setup</span>
          <span className="tabular text-[11px] text-ink-500">
            {done} / {tasks.length}
          </span>
        </div>

        <div
          className="mt-2 flex gap-1"
          role="progressbar"
          aria-valuenow={done}
          aria-valuemin={0}
          aria-valuemax={tasks.length}
          aria-label="Setup progress"
        >
          {tasks.map((task) => (
            <span
              key={task.id}
              className={cn(
                "h-1 flex-1 rounded-full",
                task.done ? "bg-accent-500" : "bg-ink-200",
              )}
            />
          ))}
        </div>

        <span className="mt-2.5 flex items-center gap-1.5 text-[12px] text-ink-500">
          <span className="truncate">{next.label}</span>
          <ArrowRight className="ml-auto size-3 shrink-0" />
        </span>
      </button>
    </div>
  );
}
