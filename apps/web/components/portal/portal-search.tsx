"use client";

import { Search } from "lucide-react";
import { useSearchParams } from "next/navigation";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/**
 * The help centre's search box, in the portal's shared header so it is on
 * every portal page rather than only the two under /help that used to carry
 * a copy of it each.
 *
 * A plain GET form pointed at /help/search -- the same markup the two pages
 * had, moved rather than rewritten. Nothing here submits with JavaScript, so
 * search keeps working with none, and the endpoint and the `q` parameter are
 * untouched.
 *
 * Client-side only to prefill the box from `?q=` on the results page. A
 * native form GET is a full page navigation, so the prefill is normally the
 * browser's own doing; the `key` covers the other direction -- a client-side
 * Link away from a results page, where this element would otherwise survive
 * reconciliation with the old query still typed in it.
 */
export function PortalSearch({ className }: { className?: string }) {
  const query = useSearchParams().get("q") ?? "";

  return (
    <form
      key={query}
      action="/help/search"
      role="search"
      className={cn("relative", className)}
    >
      <Search
        aria-hidden
        className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-400"
      />
      <Input
        type="search"
        name="q"
        defaultValue={query}
        placeholder="Search articles…"
        aria-label="Search articles"
        className="h-9 pl-8"
      />
    </form>
  );
}
