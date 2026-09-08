"use client";

import { CategoryIcon, ICONS } from "@/components/portal/category-icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/** What a category carries besides its articles. */
export interface CategoryFace {
  name: string;
  description: string;
  icon: string;
}

export const EMPTY_FACE: CategoryFace = { name: "", description: "", icon: "" };

/**
 * The three things a collection shows on the help site.
 *
 * One component for creating and for editing, rather than two forms that
 * agree until one of them gains a field. The icon set is the same table the
 * help site renders from, so the picker cannot offer something that would
 * come back as a hole in a customer's page -- and the API refuses anything
 * outside it regardless.
 */
export function CategoryFields({
  value,
  onChange,
  idPrefix,
  /** Shown under the name where renaming an existing category. */
  slugNote = false,
}: {
  value: CategoryFace;
  onChange: (next: CategoryFace) => void;
  idPrefix: string;
  slugNote?: boolean;
}) {
  const names = Object.keys(ICONS);

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-name`}>Name</Label>
        <Input
          id={`${idPrefix}-name`}
          placeholder="e.g. Getting started"
          value={value.name}
          maxLength={120}
          onChange={(event) => onChange({ ...value, name: event.target.value })}
          autoFocus
        />
        {slugNote && (
          <p className="text-[12px] text-ink-500">
            The address of its published articles does not change.
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-description`}>Description</Label>
        <Textarea
          id={`${idPrefix}-description`}
          placeholder="What a reader finds in here."
          value={value.description}
          maxLength={400}
          className="min-h-16"
          onChange={(event) =>
            onChange({ ...value, description: event.target.value })
          }
        />
        <p className="text-[12px] text-ink-500">
          Printed under the name on your help centre.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label>Icon</Label>
        <div role="radiogroup" aria-label="Icon" className="flex flex-wrap gap-1.5">
          {names.map((name) => {
            const selected = value.icon === name;
            return (
              <button
                key={name}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={name}
                onClick={() =>
                  // Clicking the chosen one again clears it, which is the
                  // only way back to no icon at all.
                  onChange({ ...value, icon: selected ? "" : name })
                }
                className={cn(
                  "flex size-9 items-center justify-center rounded-md border transition-colors",
                  selected
                    ? "border-ink-900 bg-ink-900 text-white"
                    : "border-ink-200 text-ink-500 hover:border-ink-300 hover:bg-ink-50",
                )}
              >
                <CategoryIcon name={name} className="size-4" />
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
