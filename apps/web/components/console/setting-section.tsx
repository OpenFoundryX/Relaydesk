import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SettingSectionProps {
  title: string;
  description?: string;
  action?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/**
 * The workhorse of every settings page: a titled block with an optional
 * top-right action and a body. Left-aligned, full content width -- no centred
 * narrow column.
 */
export function SettingSection({
  title,
  description,
  action,
  children,
  footer,
  className,
}: SettingSectionProps) {
  return (
    <section
      className={cn("rounded-lg border border-ink-200 bg-white", className)}
    >
      <div className="flex items-start justify-between gap-4 p-5">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold tracking-tight text-ink-900">
            {title}
          </h2>
          {description && (
            <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-500">
              {description}
            </p>
          )}
        </div>
        {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
      </div>

      {children && <div className="px-5 pb-5">{children}</div>}

      {footer && (
        <div className="flex items-center justify-end gap-2 border-t border-ink-200 bg-ink-50/60 px-5 py-3">
          {footer}
        </div>
      )}
    </section>
  );
}

/** A bordered placeholder used when a section has nothing in it yet. */
export function SectionEmpty({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-center rounded-md border border-dashed border-ink-300 bg-ink-50/60 px-4 py-8 text-[13px] text-ink-500">
      {children}
    </div>
  );
}
