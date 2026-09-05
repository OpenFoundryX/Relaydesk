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
function workspaceSlug(host: string | null): string | null {
  if (!host) return null;
  const bare = host.split(":")[0].toLowerCase();
  const root = PORTAL_DOMAIN.split(":")[0].toLowerCase();
  if (bare === root || !bare.endsWith(`.${root}`)) return null;
  const label = bare.slice(0, -(root.length + 1));
  if (!label || label.includes(".") || RESERVED.has(label)) return null;
  return label;
}

const WORKSPACE_HEADER = "x-relaydesk-workspace";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Strip whatever the caller sent for this header outright -- it must only
  // ever come from Host, resolved server-side, never from the request
  // itself. Without this, a client could set the header directly and pick
  // any workspace on a request that has no matching subdomain at all.
  const headers = new Headers(request.headers);
  headers.delete(WORKSPACE_HEADER);
  const slug = workspaceSlug(request.headers.get("host"));
  if (slug) {
    headers.set(WORKSPACE_HEADER, slug);
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
  matcher: ["/conversations/:path*", "/analytics/:path*", "/knowledge-base/:path*",
            "/notifications/:path*", "/settings/:path*", "/user-portal/:path*", "/login",
            "/submit-ticket/:path*", "/help/:path*"],
};
