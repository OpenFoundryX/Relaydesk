/**
 * @vitest-environment node
 */
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

const { POST } = await import("@/app/(widget)/widget/ask/route");

function ask(body: unknown, headers: Record<string, string> = {}) {
  return POST(
    new NextRequest("http://localhost/widget/ask", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "content-type": "application/json", ...headers },
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch() {
  const calls: RequestInit[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init: RequestInit) => {
      calls.push(init);
      return new Response("event: done\ndata: {}\n\n", { status: 200 });
    }),
  );
  return calls;
}

describe("the panel's ask proxy", () => {
  it("tells the API who is asking, not just that someone is", async () => {
    // The API buckets its per-IP cap on `client_ip.resolve`, which falls
    // through to the immediate peer when no forwarded address arrives.
    // This route IS that peer, so without the header every visitor of
    // every workspace shares one bucket of `widget_ask_ip_hourly_cap`
    // (8/hour) across the whole deployment -- the ninth question anyone
    // anywhere asks in an hour is refused. The ticket route next door
    // has always forwarded it.
    const calls = stubFetch();

    await ask({ key: "rdw_x", question: "hi" }, { "x-forwarded-for": "203.0.113.7" });

    expect(calls).toHaveLength(1);
    expect(new Headers(calls[0].headers).get("x-forwarded-for")).toBe("203.0.113.7");
  });

  it("sends no address rather than a made-up one", async () => {
    // An absent header must stay absent: inventing a value here would be
    // claiming to the API that a request came from somewhere it did not.
    const calls = stubFetch();

    await ask({ key: "rdw_x", question: "hi" });

    expect(new Headers(calls[0].headers).has("x-forwarded-for")).toBe(false);
  });

  it("forwards the conversation, which is the seam that broke once", async () => {
    // The API accepted `history` for a while before anything sent it, and
    // every answer looked right in isolation because each side's own
    // tests passed. This hop is where it was dropped, and it had no test
    // of its own at all.
    const calls = stubFetch();

    await ask({
      key: "rdw_x",
      question: "and annually?",
      history: [{ role: "visitor", text: "how do refunds work?" }],
    });

    expect(JSON.parse(String(calls[0].body))).toEqual({
      question: "and annually?",
      history: [{ role: "visitor", text: "how do refunds work?" }],
    });
  });

  it("sends an empty conversation rather than none at all", async () => {
    const calls = stubFetch();

    await ask({ key: "rdw_x", question: "hi" });

    expect(JSON.parse(String(calls[0].body)).history).toEqual([]);
  });

  it("asks for nothing at all without a key or a question", async () => {
    const calls = stubFetch();

    expect((await ask({ question: "hi" })).status).toBe(404);
    expect((await ask({ key: "rdw_x" })).status).toBe(404);
    expect(calls).toHaveLength(0);
  });
});
