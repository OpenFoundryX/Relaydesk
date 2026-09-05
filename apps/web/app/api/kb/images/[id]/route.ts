import { NextResponse } from "next/server";

import { apiUrl } from "@/lib/api/client";
import { getSessionToken } from "@/lib/session";

/**
 * Proxies an image embedded in a knowledge base article.
 *
 * An `<img src>` cannot carry an `Authorization` header, and the API scopes
 * every image to a workspace behind one -- so, exactly as
 * `app/api/attachments/[id]/route.ts` does for downloads, this route reads
 * the session cookie server-side, forwards the request with the bearer
 * header, and streams the bytes back without the token ever reaching
 * browser JS. Both the editor and the console preview point their image
 * nodes here.
 *
 * The difference from the attachment route is `Content-Disposition`: these
 * are meant to render in place, so nothing here asks the browser to
 * download them. `X-Content-Type-Options: nosniff` is what keeps that safe
 * -- with the API's upload allowlist (PNG, JPEG, GIF, WebP; never SVG,
 * which executes script) it means the browser renders the file as the image
 * type the API vouched for or not at all.
 *
 * Redirects use a relative Location for the reason the attachment route
 * gives: `request.url` in a route handler carries the server's bind
 * address, not the host the browser used.
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

  const upstream = await fetch(`${apiUrl}/api/kb/images/${encodeURIComponent(id)}`, {
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
      "X-Content-Type-Options": "nosniff",
      // Private, because the bytes are workspace-scoped and this response
      // is only ever authorised by the caller's own session cookie.
      "Cache-Control": "private, max-age=300",
    },
  });
}
