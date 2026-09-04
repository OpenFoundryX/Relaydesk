import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

// `/invite/<token>` is absent from both this list and the matcher below
// because the route no longer exists: invites are disabled pending an
// email-verified acceptance flow (see components/settings/invite-dialog.tsx
// and the API's relaydesk.api.team). There is nothing left to gate.
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
