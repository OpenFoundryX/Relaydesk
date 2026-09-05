import { NextResponse } from "next/server";

import { apiUrl } from "@/lib/api/client";

/**
 * Proxies an image embedded in a published, external article on the public
 * help site.
 *
 * An `<img src>` is a request the browser makes on its own, straight to
 * whatever origin the page names -- and the only origin an anonymous
 * visitor's browser can reach is this Next server, on the workspace's own
 * subdomain. So, exactly as `app/api/kb/images/[id]/route.ts` does for the
 * console (but with no session to attach, because there is none here), this
 * route forwards the request to the API's public image route and streams
 * the bytes straight back. That upstream route is the one that actually
 * enforces visibility -- it 404s unless the image's own article is
 * published, external, and in this workspace -- so this proxy adds no
 * authorization logic of its own; it only relays.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string; id: string }> },
) {
  const { slug, id } = await params;

  const upstream = await fetch(
    `${apiUrl}/api/public/${encodeURIComponent(slug)}/kb/images/${encodeURIComponent(id)}`,
    { cache: "no-store" },
  );

  if (!upstream.ok || !upstream.body) {
    return new NextResponse(null, { status: upstream.status });
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/octet-stream",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "public, max-age=300",
    },
  });
}
