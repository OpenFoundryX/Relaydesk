"use client";

import { CircleHelp, House, MessageCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export type PanelTab = "home" | "messages" | "help";

/**
 * The panel's persistent bottom navigation, modelled on Intercom's
 * Messenger: Home, Messages, Help. Hidden by the caller (not by this
 * component) whenever the visitor is inside a full-height screen with its
 * own back control -- a conversation or an open article -- see panel.tsx.
 *
 * Messages has no tab content at all (deliberately -- see the disabled
 * button below) and is never reachable, so `tab` in practice only ever
 * carries "home" or "help"; the type keeps "messages" anyway so the button
 * below and panel.tsx agree on one union rather than each inventing its own
 * shape for a state that can't occur.
 */
export function TabBar({
  tab,
  onChange,
}: {
  tab: PanelTab;
  onChange: (tab: PanelTab) => void;
}) {
  return (
    <nav
      aria-label="Panel sections"
      className="flex shrink-0 border-t border-ink-200 bg-white dark:border-ink-800 dark:bg-ink-900"
    >
      <TabButton
        icon={House}
        label="Home"
        active={tab === "home"}
        onClick={() => onChange("home")}
      />

      {/* Disabled, not merely quiet: a visitor's past conversation cannot
          be read back safely until there is some way to verify who is
          asking -- an unsigned `data-email` would let anyone type in a
          different customer's address and read their history. A real,
          disabled button says "not yet" honestly; a list with nothing in
          it would say "you have never written in", which for a returning
          visitor is a lie. */}
      <button
        type="button"
        disabled
        aria-disabled="true"
        title="Conversations aren't available here yet"
        className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] text-ink-300 dark:text-ink-600"
      >
        <MessageCircle className="size-5" aria-hidden />
        <span className="flex items-center gap-1">
          Messages
          <span className="rounded-full bg-ink-100 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-ink-400 dark:bg-ink-800 dark:text-ink-500">
            Soon
          </span>
        </span>
      </button>

      <TabButton
        icon={CircleHelp}
        label="Help"
        active={tab === "help"}
        onClick={() => onChange("help")}
      />
    </nav>
  );
}

function TabButton({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: typeof House;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500",
        active
          ? "font-semibold text-ink-900 dark:text-white"
          : "text-ink-400 hover:text-ink-600 dark:text-ink-500 dark:hover:text-ink-300",
      )}
    >
      {/* `fill` rather than a second icon set for "filled" -- lucide ships
          one outline path per icon, and setting the fill to the current
          text colour reads as filled-when-active without a swap that could
          desync from `active`. */}
      <Icon className="size-5" aria-hidden fill={active ? "currentColor" : "none"} />
      {label}
    </button>
  );
}
