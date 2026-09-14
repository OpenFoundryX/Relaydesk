import { PillLink } from "@/components/marketing/pill";
import type { Plan } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

/**
 * Three neutral cards at the 24px content radius.
 *
 * The featured plan is raised onto the elevated white surface rather than
 * tinted: peach is spent once per page already, and the system has no second
 * chromatic surface to promote with.
 */
export function Pricing({ plans }: { plans: Plan[] }) {
  return (
    <div className="grid gap-5 md:grid-cols-3">
      {plans.map((plan) => (
        <div
          key={plan.id}
          className={cn(
            "flex flex-col rounded-card p-8",
            plan.featured
              ? "bg-paper-white shadow-artifact"
              : "bg-mist-gray",
          )}
        >
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-[14px] font-normal text-ash-gray">
              {plan.name}
            </h3>
            {plan.featured && (
              <span className="text-[14px] font-normal text-slate-gray">
                Most picked
              </span>
            )}
          </div>

          <p className="mt-4 font-display text-[44px] font-normal leading-none tracking-[-0.66px] text-ink-black">
            {plan.price}
          </p>
          {plan.cadence && (
            <p className="mt-2 text-[14px] text-slate-gray">
              {plan.cadence.replace(/ for$/, "")}
            </p>
          )}

          <p className="mt-5 text-[16px] leading-[1.5] text-ink-black">
            {plan.blurb}
          </p>

          {/* `flex-1` so the CTA sits on the floor of every column whatever the
              blurb wraps to, and the three line up across the row. */}
          <ul className="mt-6 flex-1">
            {plan.features.map((feature) => (
              <li
                key={feature}
                className={cn(
                  "border-t py-3 text-caption text-slate-gray",
                  plan.featured ? "border-hairline" : "border-[#e3e3e5]",
                )}
              >
                {feature}
              </li>
            ))}
          </ul>

          <PillLink
            href="/contact"
            variant={plan.featured ? "filled" : "ghost"}
            className="mt-8 w-full"
          >
            {plan.cta}
          </PillLink>
        </div>
      ))}
    </div>
  );
}
