"use client";

import { Check, Search } from "lucide-react";
import { useMemo, useRef, useState, type ReactNode } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface CommandItem {
  id: string;
  label: string;
  hint?: string;
  icon?: ReactNode;
  /** Single key that selects the item while the search box is empty. */
  shortcut?: string;
  selected?: boolean;
}

interface CommandPopoverProps {
  trigger: ReactNode;
  placeholder: string;
  heading: string;
  items: CommandItem[];
  onSelect: (id: string) => void;
  emptyText?: string;
  /** Rendered under the list; receives the current query, e.g. for a create action. */
  footer?: (query: string, close: () => void) => ReactNode;
  /** Keep the popover open after selecting, for multi-select lists. */
  stayOpen?: boolean;
  align?: "start" | "center" | "end";
  className?: string;
}

/**
 * Searchable picker in the style of a command palette: a search field, a
 * headed list with number shortcuts, arrow-key navigation and a check on the
 * current value.
 */
export function CommandPopover({
  trigger,
  placeholder,
  heading,
  items,
  onSelect,
  emptyText = "No matches.",
  footer,
  stayOpen = false,
  align = "start",
  className,
}: CommandPopoverProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (item) =>
        item.label.toLowerCase().includes(needle) ||
        item.hint?.toLowerCase().includes(needle),
    );
  }, [items, query]);

  const setOpenAndReset = (value: boolean) => {
    setOpen(value);
    if (!value) {
      setQuery("");
      setActive(0);
    }
  };
  const close = () => setOpenAndReset(false);

  const choose = (id: string) => {
    onSelect(id);
    if (!stayOpen) close();
    else inputRef.current?.focus();
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      const item = filtered[active];
      if (item) {
        event.preventDefault();
        choose(item.id);
      }
    } else if (query === "" && /^[1-9]$/.test(event.key)) {
      const item = items.find((entry) => entry.shortcut === event.key);
      if (item) {
        event.preventDefault();
        choose(item.id);
      }
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpenAndReset}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent
        align={align}
        className={cn("w-80 p-2", className)}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          inputRef.current?.focus();
        }}
      >
        <div className="flex h-9 items-center gap-2 rounded-md border border-ink-200 bg-ink-50 px-2.5">
          <Search className="size-3.5 shrink-0 text-ink-400" aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            aria-label={placeholder}
            className="h-full w-full bg-transparent text-[13px] text-ink-900 outline-none placeholder:text-ink-400"
          />
        </div>

        <p className="px-2 pb-1 pt-3 text-[11px] font-medium text-ink-500">{heading}</p>

        <ul role="listbox" aria-label={heading} className="max-h-72 overflow-y-auto">
          {filtered.length === 0 && (
            <li className="px-2 py-3 text-center text-[13px] text-ink-500">{emptyText}</li>
          )}
          {filtered.map((item, index) => (
            <li
              key={item.id}
              role="option"
              aria-selected={item.selected}
              onMouseEnter={() => setActive(index)}
              onClick={() => choose(item.id)}
              className={cn(
                "flex h-8 cursor-default items-center gap-2.5 rounded-md px-2 text-[13px] text-ink-800",
                index === active && "bg-ink-100 text-ink-900",
              )}
            >
              {item.icon && (
                <span className="flex size-4 shrink-0 items-center justify-center [&_svg]:size-3.5">
                  {item.icon}
                </span>
              )}
              <span className="truncate">{item.label}</span>
              {item.hint && (
                <span className="ml-auto truncate text-[12px] text-ink-400">{item.hint}</span>
              )}
              {item.shortcut && (
                <kbd
                  className={cn(
                    "shrink-0 font-mono text-[10px] text-ink-400",
                    !item.hint && "ml-auto",
                  )}
                >
                  {item.shortcut}
                </kbd>
              )}
              <span className="flex w-4 shrink-0 justify-end">
                {item.selected && <Check className="size-3.5 text-ink-900" aria-hidden />}
              </span>
            </li>
          ))}
        </ul>

        {footer && <div className="mt-1 border-t border-ink-200 pt-1">{footer(query, close)}</div>}
      </PopoverContent>
    </Popover>
  );
}
