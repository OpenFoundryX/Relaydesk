import Link from "next/link";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Plan } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

export function Pricing({ plans }: { plans: Plan[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {plans.map((plan) => (
        <div
          key={plan.id}
          className={cn(
            "flex flex-col rounded-xl border bg-white p-6",
            plan.featured
              ? "border-ink-900 shadow-overlay ring-1 ring-ink-900"
              : "border-ink-200",
          )}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-[15px] font-semibold text-ink-900">{plan.name}</h3>
            {plan.featured && (
              <span className="rounded-full bg-accent-500 px-2 py-0.5 text-[11px] font-medium text-ink-950">
                Most popular
              </span>
            )}
          </div>
          <p className="mt-1 text-[13px] text-ink-500">{plan.blurb}</p>
          <div className="mt-5 flex items-baseline gap-1.5">
            <span className="text-3xl font-semibold tracking-tight text-ink-900">
              {plan.price}
            </span>
            {plan.cadence && (
              <span className="text-[13px] text-ink-500">
                {plan.cadence.replace(/ for$/, "")}
              </span>
            )}
          </div>
          <ul className="mt-6 space-y-2.5">
            {plan.features.map((feature) => (
              <li key={feature} className="flex items-start gap-2 text-[13px] text-ink-700">
                <Check className="mt-0.5 size-3.5 shrink-0 text-accent-700" aria-hidden />
                {feature}
              </li>
            ))}
          </ul>
          <Button
            asChild
            variant={plan.featured ? "primary" : "secondary"}
            size="lg"
            className="mt-8"
          >
            <Link href="/contact">
              {plan.cta}
            </Link>
          </Button>
        </div>
      ))}
    </div>
  );
}
