"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { BrandIcon } from "@/components/brand-icons";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import type { Integration, IntegrationCategory } from "@/lib/mock/types";

const order: IntegrationCategory[] = [
  "Notifications",
  "Payments",
  "Data",
  "Development",
];

export function IntegrationGrid({ integrations }: { integrations: Integration[] }) {
  const [query, setQuery] = useState("");

  const grouped = useMemo(() => {
    const term = query.trim().toLowerCase();
    const matches = term
      ? integrations.filter((entry) => entry.name.toLowerCase().includes(term))
      : integrations;

    return order
      .map((category) => ({
        category,
        entries: matches.filter((entry) => entry.category === category),
      }))
      .filter((group) => group.entries.length > 0);
  }, [integrations, query]);

  return (
    <div>
      <div className="relative mb-5 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-ink-400" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search integrations"
          className="pl-8"
          aria-label="Search integrations"
        />
      </div>

      {grouped.length === 0 ? (
        <p className="text-[13px] text-ink-500">
          Nothing matches “{query}”.
        </p>
      ) : (
        <div className="space-y-6">
          {grouped.map((group) => (
            <section key={group.category}>
              <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                {group.category}
              </h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {group.entries.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    className="flex items-center gap-3 rounded-md border border-ink-200 bg-white px-3 py-2.5 text-left transition-colors hover:border-ink-300 hover:bg-ink-50"
                  >
                    <span className="inline-flex size-7 shrink-0 items-center justify-center rounded bg-ink-100 font-mono text-[10px] font-semibold text-ink-500">
                      {entry.brand ? (
                        <BrandIcon brand={entry.brand} className="size-4" />
                      ) : (
                        entry.monogram
                      )}
                    </span>
                    <span className="truncate text-[13px] font-medium text-ink-900">
                      {entry.name}
                    </span>
                    {entry.connected && (
                      <Badge variant="positive" className="ml-auto shrink-0">
                        Connected
                      </Badge>
                    )}
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
