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
  const { key, question, history } = await request.json();
  if (!key || !question) return new Response(null, { status: 404 });

  // Forwarded so the API's per-IP cap buckets the visitor rather than
  // this container. `client_ip.resolve` falls through to the immediate
  // peer when nothing arrives, and the peer is always this route -- so
  // without the header every visitor of every workspace shares one
  // bucket of `widget_ask_ip_hourly_cap` across the whole deployment.
  // Absent stays absent: inventing a value would tell the API a request
  // came from somewhere it did not. Same as `submitWidgetTicket`.
  const forwardedFor = request.headers.get("x-forwarded-for");

  const upstream = await fetch(
    `${process.env.API_URL ?? "http://api:8000"}/api/widget/${encodeURIComponent(key)}/ask`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
      },
      // `history` is forwarded, not rebuilt: the API caps and
      // truncates it, and a proxy that quietly dropped it left the
      // model answering every follow-up with no idea what it followed.
      body: JSON.stringify({ question, history: history ?? [] }),
    },
  );

  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": "text/event-stream" },
  });
}
