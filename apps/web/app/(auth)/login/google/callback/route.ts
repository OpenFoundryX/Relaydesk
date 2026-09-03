import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { apiFetch } from "@/lib/api/client";
import { setSessionCookie } from "@/lib/session";

/**
 * `request.url` in a route handler carries the server's bind address, not
 * the client's host (Task 4 proved this with a forged `Host` header,
 * getting `http://0.0.0.0:3000/...` back regardless). Here that would be
 * worse than a bad redirect: Google requires the `redirect_uri` sent to the
 * token exchange to match the one used in the authorization request
 * exactly, so a bind-address value would fail the exchange and break
 * sign-in outright. Both derive from NEXT_PUBLIC_WEB_URL instead.
 */
function webUrl(): string {
  return process.env.NEXT_PUBLIC_WEB_URL ?? "http://localhost:3000";
}

function redirectTo(path: string): NextResponse {
  return new NextResponse(null, { status: 307, headers: { Location: path } });
}

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");

  const store = await cookies();
  const expected = store.get("rd_oauth_state")?.value;
  store.delete("rd_oauth_state");

  // A missing or mismatched state means this callback did not originate
  // from our own redirect, so it is a CSRF attempt and gets no session.
  if (!code || !state || !expected || state !== expected) {
    return redirectTo("/login?error=1");
  }

  // Must be byte-identical to the redirect_uri sent in the authorization
  // request, or Google rejects the exchange. Both derive from WEB_URL.
  const redirectUri = `${webUrl()}/login/google/callback`;
  try {
    const token = await apiFetch<{ token: string; expiresAt: string }>(
      "/auth/google/exchange",
      {
        method: "POST",
        auth: false,
        body: JSON.stringify({ code, redirectUri }),
      },
    );
    await setSessionCookie(token.token, token.expiresAt);
  } catch {
    return redirectTo("/login?error=1");
  }

  return redirectTo("/conversations?status=open");
}
