import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

/**
 * Clears a session cookie the API has already rejected, then sends the user
 * to sign in. This is a route handler because Server Components may not
 * mutate cookies and `apiFetch` runs during render.
 *
 * The Location is deliberately relative: `request.url` in a route handler
 * carries the server's bind address rather than the client's host, so
 * `new URL(path, request.url)` would redirect to an unreachable origin
 * behind any proxy or non-default host.
 */
export async function GET() {
  const response = new NextResponse(null, {
    status: 307,
    headers: { Location: "/login?expired=1" },
  });
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
