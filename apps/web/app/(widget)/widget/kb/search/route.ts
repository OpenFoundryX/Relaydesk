import { NextRequest, NextResponse } from "next/server";

import { searchWidgetKb } from "@/lib/api/widget";

/**
 * The panel's own search, proxied server-side.
 *
 * `Results` (components/widget/results.tsx) is a client component and the
 * frame has no path to the API directly -- there is no CORS story for it
 * (see `services/widget_origins.py`'s docstring) and no rewrite from this
 * app to the API container, so every client-side read goes through a route
 * like this one, same as the portal's `/help/search/index/route.ts`.
 *
 * Addressed by `key` in the query string rather than by a resolved
 * workspace header: the widget has no subdomain to resolve one from (spec
 * D3), so the key travels explicitly on every call instead.
 */
export async function GET(request: NextRequest) {
  const key = request.nextUrl.searchParams.get("key");
  const q = (request.nextUrl.searchParams.get("q") ?? "").trim();
  if (!key || !q) return NextResponse.json([]);

  const results = await searchWidgetKb(key, q);
  return NextResponse.json(results);
}
