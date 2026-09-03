import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  suggestions?: string[];
  suggestionsLabel?: string;
  actions?: ReactNode;
}

/**
 * Left-aligned rather than centred: the eye stays on the same column as the
 * page header, and the suggestions read as a list instead of a chip cloud.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  suggestions,
  suggestionsLabel = "Suggested sections",
  actions,
}: EmptyStateProps) {
  return (
    <div className="max-w-xl rounded-lg border border-dashed border-ink-300 bg-white p-6">
      <span className="inline-flex size-9 items-center justify-center rounded-md bg-accent-100 text-accent-950">
        <Icon className="size-4.5" />
      </span>
      <h2 className="mt-3 text-[15px] font-semibold tracking-tight text-ink-900">
        {title}
      </h2>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-500">{description}</p>

      {suggestions && suggestions.length > 0 && (
        <div className="mt-4 border-t border-ink-200 pt-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">
            {suggestionsLabel}
          </p>
          <ul className="mt-2 space-y-1.5">
            {suggestions.map((suggestion) => (
              <li
                key={suggestion}
                className="flex items-center gap-2 text-[13px] text-ink-600"
              >
                <span className="size-1 rounded-full bg-accent-600" />
                {suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}

      {actions && <div className="mt-5 flex items-center gap-2">{actions}</div>}
    </div>
  );
}
