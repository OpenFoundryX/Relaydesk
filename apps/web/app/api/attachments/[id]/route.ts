import { NextResponse } from "next/server";

import { apiUrl } from "@/lib/api/client";
import { getSessionToken } from "@/lib/session";

/**
 * Proxies an attachment download.
 *
 * The API scopes the file to a workspace and only accepts the session as an
 * `Authorization: Bearer` header -- something a plain `<a href>` cannot
 * attach. This route reads the session cookie server-side, forwards the
 * request with that header, and streams the response straight through
 * (including its `Content-Disposition: attachment`) without ever handing
 * the token to the browser. It's the one place in the console that talks to
 * the API directly rather than through `lib/api/client`: that helper always
 * calls `.json()`, which does not work on a binary body.
 *
 * Every redirect below uses a relative Location: `request.url` in a route
 * handler carries the server's bind address, not the client's host, so
 * `new URL(path, request.url)` would send the browser somewhere unreachable
 * behind a proxy or a non-default host.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const token = await getSessionToken();
  if (!token) {
    return new NextResponse(null, { status: 307, headers: { Location: "/login" } });
  }

  const upstream = await fetch(`${apiUrl}/api/attachments/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (upstream.status === 401) {
    return new NextResponse(null, { status: 307, headers: { Location: "/signed-out" } });
  }

  if (!upstream.ok || !upstream.body) {
    return new NextResponse(null, { status: upstream.status });
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/octet-stream",
      "Content-Disposition": upstream.headers.get("Content-Disposition") ?? "attachment",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
