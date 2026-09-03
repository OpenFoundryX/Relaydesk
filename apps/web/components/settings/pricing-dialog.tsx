"use client";

import { useState } from "react";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Plan } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

export function PricingDialog({
  plans,
  usage,
}: {
  plans: Plan[];
  usage: { tickets: number; projected: number; seats: number };
}) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          Choose a plan
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[88vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Pricing</DialogTitle>
          <DialogDescription>
            Priced on ticket volume, so it tracks how much support you actually do.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <p className="rounded-md border border-ink-200 bg-ink-50 px-3 py-2.5 text-[13px] text-ink-600">
            This period you have handled{" "}
            <span className="font-medium text-ink-900">{usage.tickets} tickets</span>,
            tracking to{" "}
            <span className="font-medium text-ink-900">
              {usage.projected} a month
            </span>{" "}
            across <span className="font-medium text-ink-900">{usage.seats} seats</span>.
          </p>

          <div className="grid gap-3 md:grid-cols-3">
            {plans.map((plan) => {
              const dark = plan.id === "enterprise";
              return (
                <section
                  key={plan.id}
                  className={cn(
                    "flex flex-col rounded-lg border p-5",
                    dark
                      ? "border-ink-950 bg-ink-950 text-white"
                      : plan.featured
                        ? "border-accent-600 bg-white"
                        : "border-ink-200 bg-white",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <h3
                      className={cn(
                        "text-[13px] font-semibold",
                        dark ? "text-white" : "text-ink-900",
                      )}
                    >
                      {plan.name}
                    </h3>
                    {plan.featured && (
                      <span className="rounded-full bg-accent-500 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-950">
                        Popular
                      </span>
                    )}
                  </div>

                  <p
                    className={cn(
                      "mt-3 text-2xl font-semibold tracking-tight",
                      dark ? "text-white" : "text-ink-900",
                    )}
                  >
                    {plan.price}
                  </p>
                  {plan.cadence && (
                    <p
                      className={cn(
                        "text-[12px]",
                        dark ? "text-ink-400" : "text-ink-500",
                      )}
                    >
                      {plan.cadence}
                    </p>
                  )}

                  {plan.meteredOptions && (
                    <Select defaultValue={plan.meteredOptions[0]}>
                      <SelectTrigger
                        className="mt-2"
                        aria-label={`${plan.name} ticket volume`}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {plan.meteredOptions.map((option) => (
                          <SelectItem key={option} value={option}>
                            {option}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}

                  <p
                    className={cn(
                      "mt-4 text-[13px] leading-relaxed",
                      dark ? "text-ink-300" : "text-ink-500",
                    )}
                  >
                    {plan.blurb}
                  </p>

                  <div className="mt-4">
                    <Button
                      variant={
                        dark ? "secondary" : plan.featured ? "primary" : "secondary"
                      }
                      className="w-full"
                      size="sm"
                    >
                      {plan.cta}
                    </Button>
                  </div>

                  <ul className="mt-4 space-y-2 border-t pt-4 text-[13px]">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2">
                        <Check
                          className={cn(
                            "mt-0.5 size-3.5 shrink-0",
                            dark ? "text-accent-400" : "text-accent-800",
                          )}
                        />
                        <span className={dark ? "text-ink-200" : "text-ink-600"}>
                          {feature}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}
