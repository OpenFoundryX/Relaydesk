import * as React from "react";

import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea">
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "flex min-h-20 w-full rounded-md border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 transition-colors",
      "placeholder:text-ink-400 hover:border-ink-300",
      "disabled:cursor-not-allowed disabled:bg-ink-50",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export { Textarea };
