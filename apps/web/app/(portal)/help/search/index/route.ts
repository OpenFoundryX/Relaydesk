import { headers } from "next/headers";
import { NextResponse } from "next/server";

import { getPublicSearchIndex } from "@/lib/api/public";

/**
 * The searchable surface of this workspace's help centre, for the browser
 * to score locally. See `components/portal/search-index.ts`.
 *
 * A route rather than data passed down from a page, because it is fetched
 * lazily -- a visitor who never touches the search box never pays for it.
 *
 * It lives under `/help/search/`, which the API already refuses as a
 * category slug, so it needs no new reserved word and cannot be shadowed by
 * the `/help/[...path]` catch-all. The workspace comes from the header the
 * middleware sets from the request's Host, exactly as every portal page
 * resolves it; no slug in the header is Next's 404, the same answer an
 * unknown workspace gets.
 */
export async function GET() {
  const slug = (await headers()).get("x-relaydesk-workspace");
  if (!slug) return new NextResponse(null, { status: 404 });

  const entries = await getPublicSearchIndex(slug);

  return NextResponse.json(entries, {
    headers: {
      // Public, because every entry in it is already published. Five
      // minutes is long enough to cover a visit and short enough that a
      // newly published article turns up while someone is still reading.
      "Cache-Control": "public, max-age=300",
    },
  });
}
