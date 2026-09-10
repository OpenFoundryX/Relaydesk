import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * The panel's two buttons, and only two. Which variant "Send a message"
 * gets on a given screen is the deflection hierarchy made visible (design
 * §7): secondary on Home, primary on Results and at the foot of an
 * Article, because trying to self-serve first is what makes escalation the
 * right next action.
 *
 * `console`/`portal` button variants are not reused here -- they hard-code
 * light-surface colours with no `dark:` pair, and this is the one surface
 * in the app that has to answer to `prefers-color-scheme` on its own.
 */
export const WidgetButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }
>(({ variant = "secondary", className, ...props }, ref) => (
  <button
    ref={ref}
    className={cn(
      "inline-flex h-9 w-full items-center justify-center gap-2 rounded-md px-3.5 text-[13px] font-medium transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-ink-900",
      "disabled:pointer-events-none disabled:opacity-50",
      variant === "primary"
        ? "bg-ink-900 text-white hover:bg-ink-800 dark:bg-accent-500 dark:text-ink-950 dark:hover:bg-accent-400"
        : "border border-ink-200 bg-white text-ink-900 hover:border-ink-300 hover:bg-ink-50 dark:border-ink-700 dark:bg-ink-900 dark:text-ink-100 dark:hover:bg-ink-800",
      className,
    )}
    {...props}
  />
));
WidgetButton.displayName = "WidgetButton";
