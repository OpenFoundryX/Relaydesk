import { NextRequest } from "next/server";

/**
 * The panel's question, proxied server-side and streamed straight through.
 *
 * `Ask` is a client component and this app's API client is `server-only`,
 * so every client-side call goes through a route like this one -- same as
 * `widget/kb/search/route.ts`. The body is passed on unchanged and the
 * upstream stream is returned as-is: nothing here interprets the events,
 * so a new event type needs no change on this hop.
 */
export async function POST(request: NextRequest) {
  const { key, question } = await request.json();
  if (!key || !question) return new Response(null, { status: 404 });

  const upstream = await fetch(
    `${process.env.API_URL ?? "http://api:8000"}/api/widget/${encodeURIComponent(key)}/ask`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
    },
  );

  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": "text/event-stream" },
  });
}
