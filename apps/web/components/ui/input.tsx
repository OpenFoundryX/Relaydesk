import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        "flex h-9 w-full rounded-md border border-ink-200 bg-white px-3 py-1 text-sm text-ink-900 transition-colors",
        "placeholder:text-ink-400 hover:border-ink-300",
        "disabled:cursor-not-allowed disabled:bg-ink-50 disabled:text-ink-400",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
