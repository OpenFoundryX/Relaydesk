import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

// `/invite/<token>` is deliberately absent from both this list and the
// matcher below: the person following an invite link has no session yet,
// and gating it would bounce them to /login with nowhere to go.
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
