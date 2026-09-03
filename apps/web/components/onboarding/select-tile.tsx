"use client";

import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Vendor-neutral picker tile. We ship no third-party logos, so each option is
 * identified by a monogram square plus its name.
 */
export function SelectTile({
  label,
  monogram,
  selected,
  onSelect,
}: {
  label: string;
  monogram: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "flex h-11 items-center gap-2.5 rounded-md border px-3 text-left text-[13px] transition-colors",
        selected
          ? "border-accent-600 bg-accent-50 text-ink-950"
          : "border-ink-200 bg-white text-ink-700 hover:border-ink-300 hover:bg-ink-50",
      )}
    >
      <span
        className={cn(
          "inline-flex size-6 shrink-0 items-center justify-center rounded font-mono text-[10px] font-semibold",
          selected ? "bg-ink-900 text-accent-400" : "bg-ink-100 text-ink-500",
        )}
      >
        {monogram}
      </span>
      <span className="truncate font-medium">{label}</span>
      {selected && <Check className="ml-auto size-3.5 shrink-0 text-accent-800" />}
    </button>
  );
}
