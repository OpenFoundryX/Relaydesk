import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Standard content padding, with an optional max width for reading-width pages. */
export function PageShell({
  children,
  width = "wide",
  className,
}: {
  children: ReactNode;
  width?: "wide" | "narrow";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "px-6 py-5",
        width === "narrow" ? "max-w-3xl" : "max-w-6xl",
        className,
      )}
    >
      {children}
    </div>
  );
}
