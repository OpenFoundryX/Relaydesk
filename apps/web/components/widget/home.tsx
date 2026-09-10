"use client";

import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";

import { WidgetButton } from "@/components/widget/button";

/**
 * The panel's front page. Search is offered first and "Send a message" is
 * a secondary, outlined control -- the visitor has not tried to self-serve
 * yet, so escalation is not yet the recommended action (design §7).
 *
 * Never rendered when the knowledge base is empty -- see the `empty` guard
 * in panel.tsx, which opens straight into Compose instead.
 */
export function Home({
  onSearch,
  onCompose,
  greeting,
}: {
  onSearch: (query: string) => void;
  onCompose: () => void;
  /**
   * The embed's configured `settings.greeting` (spec D10, un-deferred).
   * Absent whenever the admin never set one -- falls back to exactly the
   * copy this screen has always shown.
   */
  greeting?: string;
}) {
  const [typed, setTyped] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = typed.trim();
    if (query) onSearch(query);
  }

  return (
    <div className="flex flex-1 flex-col gap-6 px-4 py-6">
      <h1 className="text-[17px] font-semibold tracking-tight text-ink-900 dark:text-white">
        {greeting || "Hi there. How can we help?"}
      </h1>

      <form role="search" onSubmit={submit} className="relative">
        <label htmlFor="widget-search" className="sr-only">
          Search for an answer
        </label>
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400"
        />
        <input
          id="widget-search"
          type="search"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          placeholder="Search for an answer"
          className="h-9 w-full rounded-md border border-ink-200 bg-white pl-9 pr-3 text-[13px] text-ink-900 placeholder:text-ink-400 transition-colors hover:border-ink-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:text-white dark:placeholder:text-ink-400"
        />
      </form>

      <div className="mt-auto flex flex-col gap-2">
        <p className="text-[12px] text-ink-500 dark:text-ink-400">
          Can&apos;t find what you need?
        </p>
        <WidgetButton type="button" variant="secondary" onClick={onCompose}>
          Send a message
        </WidgetButton>
      </div>
    </div>
  );
}
