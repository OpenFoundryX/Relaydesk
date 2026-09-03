import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

/**
 * Clears a session cookie the API has already rejected, then sends the user
 * to sign in. This exists as a route handler because Server Components may
 * not mutate cookies, and `apiFetch` runs during render.
 */
export async function GET(request: NextRequest) {
  const response = NextResponse.redirect(new URL("/login?expired=1", request.url));
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
