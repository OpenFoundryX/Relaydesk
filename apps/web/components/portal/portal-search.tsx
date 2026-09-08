"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";

import {
  buildSearchIndex,
  searchArticles,
  type SearchEntry,
  type SearchIndex,
  type SearchResult,
} from "@/components/portal/search-index";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/**
 * The help centre's search box, in the portal's hero so it is on every
 * portal page.
 *
 * Underneath it is still a plain GET form pointed at /help/search. That is
 * deliberate and load-bearing: it is the only search a visitor with no
 * JavaScript has, and it is the *thorough* one either way -- the server
 * searches article bodies, which the browser index cannot (see
 * `search-index.ts`). Pressing Enter on nothing in particular still goes
 * there.
 *
 * On top of it, suggestions: the index is fetched once, on first focus, and
 * every keystroke after that is scored in memory with no network at all.
 *
 * Client-side also to prefill the box from `?q=` on the results page. A
 * native form GET is a full page navigation, so the prefill is normally the
 * browser's own doing; the `key` covers the other direction -- a
 * client-side Link away from a results page, where this element would
 * otherwise survive reconciliation with the old query still typed in it.
 */

/** Long enough to stop the list flickering under a fast typer, short
 *  enough that nobody reads it as lag. */
const DEBOUNCE_MS = 100;

export function PortalSearch({
  className,
  tone = "light",
}: {
  className?: string;
  /** "dark" for the hero band, where the field sits on near-black. */
  tone?: "light" | "dark";
}) {
  const query = useSearchParams().get("q") ?? "";
  const router = useRouter();
  const dark = tone === "dark";
  const listId = useId();

  const [typed, setTyped] = useState(query);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);

  // The prepared index, kept across renders. A ref rather than state: it
  // never changes after it arrives, so storing it in state would only add
  // a render.
  const index = useRef<SearchIndex | null>(null);
  const loading = useRef(false);

  const load = useCallback(async () => {
    if (index.current || loading.current) return;
    loading.current = true;
    try {
      const response = await fetch("/help/search/index");
      if (!response.ok) return;
      const entries = (await response.json()) as SearchEntry[];
      index.current = buildSearchIndex(entries);
    } catch {
      // Search degrades to the form underneath, which needs nothing from
      // here. Better than an error message over a box someone is typing in.
    } finally {
      loading.current = false;
    }
  }, []);

  // Everything happens inside the timeout, including clearing the list when
  // the box is emptied: a synchronous setState in an effect body is a
  // cascading render, and a hundred milliseconds is not a perceptible delay
  // on a list disappearing.
  useEffect(() => {
    const timer = setTimeout(async () => {
      const term = typed.trim();
      if (!term) {
        setResults(null);
        return;
      }
      await load();
      if (!index.current) return;
      setResults(searchArticles(index.current, term));
      setActive(-1);
      setOpen(true);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [typed, load]);

  const go = (path: string) => {
    setOpen(false);
    router.push(`/help/${path}`);
  };

  const showing = open && results !== null;

  return (
    <form
      key={query}
      action="/help/search"
      role="search"
      className={cn("relative", className)}
      onSubmit={() => setOpen(false)}
    >
      <Search
        aria-hidden
        className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-ink-400"
      />
      <Input
        type="search"
        name="q"
        role="combobox"
        aria-expanded={showing}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          active >= 0 && results?.[active] ? `${listId}-${active}` : undefined
        }
        value={typed}
        onChange={(event) => setTyped(event.target.value)}
        // Fetching here rather than on mount is what keeps a visitor who
        // never searches from paying for the index at all.
        onFocus={() => void load()}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(event) => {
          if (!results?.length) return;
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
            setActive((i) => (i + 1) % results.length);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((i) => (i <= 0 ? results.length - 1 : i - 1));
          } else if (event.key === "Escape") {
            setOpen(false);
          } else if (event.key === "Enter" && active >= 0) {
            // Only when something is highlighted. Otherwise the form
            // submits and the reader gets the full results page, which
            // searches article bodies too.
            event.preventDefault();
            go(results[active].path);
          }
        }}
        placeholder="Search for articles…"
        aria-label="Search articles"
        className={cn(
          "pl-11",
          dark
            ? "h-12 rounded-xl border-ink-700 bg-ink-800 text-[15px] text-white placeholder:text-ink-400 focus-visible:border-ink-500"
            : "h-9",
        )}
      />

      {showing && (
        <div className="absolute left-0 right-0 top-full z-20 mt-2 overflow-hidden rounded-xl border border-ink-200 bg-white shadow-lg">
          {results.length === 0 ? (
            <p className="px-4 py-3 text-[13px] text-ink-500">
              No articles match “{typed.trim()}”. Press Enter to search their
              contents.
            </p>
          ) : (
            <ul id={listId} role="listbox" aria-label="Article suggestions">
              {results.map((result, i) => (
                <li
                  key={result.id}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  className={cn(
                    "border-t border-ink-100 first:border-t-0",
                    i === active && "bg-ink-50",
                  )}
                >
                  <Link
                    href={`/help/${result.path}`}
                    className="block px-4 py-3"
                    // The blur that a click causes would close the list
                    // before the navigation started.
                    onMouseDown={(event) => event.preventDefault()}
                    onMouseEnter={() => setActive(i)}
                  >
                    <span className="block text-[14px] text-ink-900">
                      {result.title}
                    </span>
                    {result.collections.length > 0 && (
                      <span className="mt-0.5 block text-[12px] text-ink-400">
                        {result.collections.join(" › ")}
                      </span>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </form>
  );
}
