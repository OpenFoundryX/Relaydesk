import { NextRequest, NextResponse } from "next/server";

import { recordWidgetSessionEvent, type WidgetSessionEventKind } from "@/lib/api/widget";

const KINDS: readonly WidgetSessionEventKind[] = ["searched", "read", "submitted"];

function isKnownKind(value: unknown): value is WidgetSessionEventKind {
  return typeof value === "string" && (KINDS as readonly string[]).includes(value);
}

/**
 * The deflection baseline's write side, proxied server-side. See
 * `widget/kb/search/route.ts` for why this is a route rather than a direct
 * client fetch: the frame is cross-origin from the API, so `panel.tsx`
 * (a Client Component) has no other path to it.
 *
 * Always answers 204, even on a bad body or an unreachable API: a counter
 * must never be able to surface as a failure the visitor can see, and
 * `panel.tsx` does not inspect the response anyway. The API-side validation
 * and commit are what make the count real; this route's only job is to not
 * let a rejected or failed write become visible.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const key = typeof body?.key === "string" ? body.key : null;
  const sessionId = typeof body?.sessionId === "string" ? body.sessionId : null;
  const kind = isKnownKind(body?.kind) ? body.kind : null;

  if (key && sessionId && kind) {
    await recordWidgetSessionEvent(key, sessionId, kind).catch(() => {});
  }

  return new NextResponse(null, { status: 204 });
}
