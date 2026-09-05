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

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const signedIn = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  if (!signedIn && PROTECTED.some((prefix) => pathname.startsWith(prefix))) {
    const login = new URL("/login", request.url);
    return NextResponse.redirect(login);
  }

  if (signedIn && pathname === "/login") {
    return NextResponse.redirect(new URL("/conversations?status=open", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/conversations/:path*", "/analytics/:path*", "/knowledge-base/:path*",
            "/notifications/:path*", "/settings/:path*", "/user-portal/:path*", "/login"],
};
