"use client";

import { useEffect, useState } from "react";

import { WidgetButton } from "@/components/widget/button";
import type { WidgetArticleSummary } from "@/lib/api/widget";

/**
 * What a search turned up. "Send a message" is primary here -- the visitor
 * has already tried to self-serve, so escalation is now the recommended
 * action (design §7), the opposite of its weight on Home.
 */
export function Results({
  widgetKey,
  query,
  onOpen,
  onCompose,
}: {
  widgetKey: string | undefined;
  query: string;
  onOpen: (path: string) => void;
  onCompose: () => void;
}) {
  // Reset by remounting rather than by clearing state at the top of the
  // effect: `panel.tsx` keys this component on `query`, so a new search
  // always starts from a fresh `null` here instead of a synchronous
  // `setState` call inside the effect body.
  const [results, setResults] = useState<WidgetArticleSummary[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const request = widgetKey
      ? fetch(
          `/widget/kb/search?key=${encodeURIComponent(widgetKey)}&q=${encodeURIComponent(query)}`,
        ).then((response) => (response.ok ? response.json() : []))
      : Promise.resolve([]);
    request
      .then((entries: WidgetArticleSummary[]) => {
        if (!cancelled) setResults(entries);
      })
      .catch(() => {
        if (!cancelled) setResults([]);
      });
    return () => {
      cancelled = true;
    };
  }, [widgetKey, query]);

  const loading = results === null;

  return (
    <div className="flex flex-1 flex-col gap-4 px-4 py-6">
      <h1 className="text-[13px] text-ink-500 dark:text-ink-400">
        Results for &ldquo;{query}&rdquo;
      </h1>

      {/* Announces the count once it is known, not the loading state --
          "Loading" read out on every keystroke-triggered search is noise a
          screen-reader user does not need for a fetch this fast. */}
      <div aria-live="polite" className="sr-only">
        {!loading &&
          `${results.length} ${results.length === 1 ? "result" : "results"} for ${query}`}
      </div>

      {loading ? (
        <p className="text-[13px] text-ink-400">Searching…</p>
      ) : results.length === 0 ? (
        <p className="text-[13px] text-ink-500 dark:text-ink-400">
          Nothing matched. Send us a message instead.
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {results.map((result) => (
            <li key={result.id}>
              <button
                type="button"
                onClick={() => onOpen(result.path)}
                className="block w-full rounded-lg border border-ink-200 bg-white p-3 text-left transition-colors hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:border-ink-700 dark:bg-ink-800 dark:hover:bg-ink-700"
              >
                <span className="block text-[13px] font-medium text-ink-900 dark:text-white">
                  {result.title}
                </span>
                {result.excerpt && (
                  <span className="mt-0.5 line-clamp-2 block text-[12px] text-ink-500 dark:text-ink-400">
                    {result.excerpt}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto pt-2">
        <WidgetButton type="button" variant="primary" onClick={onCompose}>
          Send a message
        </WidgetButton>
      </div>
    </div>
  );
}
