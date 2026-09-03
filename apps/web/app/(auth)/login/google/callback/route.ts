import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { apiFetch } from "@/lib/api/client";
import { googleRedirectUri } from "@/lib/google-oauth";
import { setSessionCookie } from "@/lib/session";

function redirectTo(path: string): NextResponse {
  return new NextResponse(null, { status: 307, headers: { Location: path } });
}

export async function GET(request: NextRequest) {
  const googleError = request.nextUrl.searchParams.get("error");
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");

  const store = await cookies();
  const expected = store.get("rd_oauth_state")?.value;
  store.delete("rd_oauth_state");

  if (googleError) {
    // The user declined consent, or Google reports some other
    // authorization-time failure (e.g. "access_denied"). Logged server-side
    // only -- nothing here reaches the client -- so a genuinely unexpected
    // value is still visible somewhere.
    console.error(`Google OAuth callback returned an error: ${googleError}`);
    return redirectTo("/login?error=google");
  }

  // A missing or mismatched state means this callback did not originate
  // from our own redirect, so it is a CSRF attempt and gets no session.
  if (!code || !state || !expected || state !== expected) {
    return redirectTo("/login?error=google");
  }

  // Must be byte-identical to the redirect_uri sent in the authorization
  // request, or Google rejects the exchange. Both call sites share this
  // helper so they cannot drift apart.
  const redirectUri = googleRedirectUri();
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
  } catch (error) {
    // Server-side only -- leaks nothing to the client -- so a genuine
    // programming error is not silently discarded alongside the expected
    // "Unauthorized" case (bad/expired code, unknown member, and so on).
    console.error("Google OAuth exchange failed", error);
    return redirectTo("/login?error=google");
  }

  return redirectTo("/conversations?status=open");
}
