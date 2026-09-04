"use client";

import { Check } from "lucide-react";

import { BrandIcon, type BrandSlug } from "@/components/brand-icons";
import { cn } from "@/lib/utils";

/**
 * Picker tile. Options carrying a `brand` show its mark; the rest fall back to
 * a monogram square. Selected tiles render the mark in `currentColor` so it
 * reads against the dark chip rather than fighting it.
 */
export function SelectTile({
  label,
  brand,
  monogram,
  selected,
  onSelect,
}: {
  label: string;
  brand?: BrandSlug;
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
        {brand ? (
          <BrandIcon brand={brand} mono={selected} className="size-3.5" />
        ) : (
          monogram
        )}
      </span>
      <span className="truncate font-medium">{label}</span>
      {selected && <Check className="ml-auto size-3.5 shrink-0 text-accent-800" />}
    </button>
  );
}
