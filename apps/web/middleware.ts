import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

// `/invites` is absent from both this list and the matcher below on
// purpose: whoever follows an emailed invite link has no session yet, so
// the route has to stay reachable unauthenticated. See
// components/settings/invite-dialog.tsx and app/invites/page.tsx.
const PROTECTED = [
  "/conversations",
  "/analytics",
  "/knowledge-base",
  "/notifications",
  "/settings",
  "/user-portal",
];

const PORTAL_DOMAIN = process.env.NEXT_PUBLIC_PORTAL_DOMAIN ?? "localhost:3000";
const RESERVED = new Set(["www", "app", "api", "admin", "mail", "inbound"]);

/**
 * A workspace is reached at <slug>.<portal domain>. The slug travels to the
 * portal layout as a request header rather than a rewritten path, so
 * /help/billing/refunds stays exactly that in the address bar and in the
 * route tree.
 */
export function workspaceSlug(host: string | null): string | null {
  if (!host) return null;
  const bare = host.split(":")[0].toLowerCase();
  const root = PORTAL_DOMAIN.split(":")[0].toLowerCase();
  if (bare === root || !bare.endsWith(`.${root}`)) return null;
  const label = bare.slice(0, -(root.length + 1));
  if (!label || label.includes(".") || RESERVED.has(label)) return null;
  return label;
}

const WORKSPACE_HEADER = "x-relaydesk-workspace";

const API_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * The frame's `frame-ancestors` value, fetched from the key's own
 * `allowed_origins` (spec D2). One API call per panel open -- a lookup,
 * unlike the workspace resolution above, which is pure string maths on
 * `Host` and costs nothing.
 *
 * Fails closed: a network error reaching the API, same as an unknown key,
 * answers `'none'` rather than leaving the header unset. An unset CSP
 * header does not refuse embedding -- it is silence, which a browser reads
 * as "no policy", the opposite of what a lookup failure should mean here.
 */
async function embedPolicy(key: string): Promise<string> {
  try {
    const response = await fetch(
      `${API_URL}/api/widget/${encodeURIComponent(key)}/embed-policy`,
    );
    if (!response.ok) return "frame-ancestors 'none'";
    return await response.text();
  } catch {
    return "frame-ancestors 'none'";
  }
}

// Not declared `async`: every other branch below stays synchronous, and
// every existing test in middleware.test.ts calls `middleware(request)`
// without awaiting it -- an `async` signature would wrap every one of those
// returns in a Promise and break them all. Only the /widget/frame branch
// needs to await anything, so only it returns a Promise; TypeScript infers
// the union return type from the two `return` shapes below.
export function middleware(request: NextRequest): NextResponse | Promise<NextResponse> {
  const { pathname } = request.nextUrl;

  // Strip whatever the caller sent for this header outright -- it must only
  // ever come from Host, resolved server-side, never from the request
  // itself. Without this, a client could set the header directly and pick
  // any workspace on a request that has no matching subdomain at all.
  const headers = new Headers(request.headers);
  headers.delete(WORKSPACE_HEADER);
  // `x-forwarded-for` is deliberately NOT stripped here, and that is only
  // safe because of how this container is reached. Next fills the header in
  // from `socket.remoteAddress` when it is absent -- which is the visitor's
  // address only when Next itself faces the internet. Behind the reverse
  // proxy every real deployment needs, that socket belongs to the proxy, so
  // stripping the header buckets every visitor in the world together and
  // `TICKET_IP_HOURLY_CAP` then throttles all of them to five an hour.
  // Silently, and failing closed.
  //
  // What makes the incoming value trustworthy instead is that nothing can
  // reach this container except the proxy: the web service publishes no
  // port (see docker-compose.yml) and the proxy itself accepts
  // `X-Forwarded-For` only from its own upstream edge. Break either of
  // those and a caller can pick its own rate-limit bucket again -- so the
  // guarantee moved, it did not disappear.

  // The frame's own CSP, and the only per-key header in the app. Unlike the
  // workspace resolution below -- pure string maths on Host -- this needs a
  // lookup, so it costs one API call per panel open. That is the price of
  // per-key origins; it is not on the portal's path and does not slow it.
  if (pathname === "/widget/frame") {
    const key = request.nextUrl.searchParams.get("key");
    if (!key) {
      const response = NextResponse.next({ request: { headers } });
      response.headers.set("Content-Security-Policy", "frame-ancestors 'none'");
      return response;
    }
    return embedPolicy(key).then((policy) => {
      const response = NextResponse.next({ request: { headers } });
      response.headers.set("Content-Security-Policy", policy);
      return response;
    });
  }

  const slug = workspaceSlug(request.headers.get("host"));
  if (slug) {
    headers.set(WORKSPACE_HEADER, slug);
    // The bare root of a resolved workspace subdomain is the help centre,
    // not a page of its own -- redirect rather than rewrite so the address
    // bar always shows the real route. Every other portal link already
    // points at /help explicitly (see the "← Help center" back-links and
    // the portal nav), so a rewrite here would leave "/" and "/help"
    // serving identical content at two different URLs. The follow-up
    // request this redirect produces re-enters this same middleware and
    // gets the workspace header set on it normally.
    if (pathname === "/") {
      return NextResponse.redirect(new URL("/help", request.url));
    }
    return NextResponse.next({ request: { headers } });
  }

  const signedIn = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  if (!signedIn && PROTECTED.some((prefix) => pathname.startsWith(prefix))) {
    const login = new URL("/login", request.url);
    return NextResponse.redirect(login);
  }

  if (signedIn && pathname === "/login") {
    return NextResponse.redirect(new URL("/conversations?status=open", request.url));
  }

  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/", "/conversations/:path*", "/analytics/:path*", "/knowledge-base/:path*",
            "/notifications/:path*", "/settings/:path*", "/user-portal/:path*", "/login",
            "/submit-ticket/:path*", "/help/:path*", "/forgot-password", "/widget/frame"],
};
