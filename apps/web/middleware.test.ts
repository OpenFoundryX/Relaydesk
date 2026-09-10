import { NextRequest } from "next/server";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import type { middleware as MiddlewareFn } from "./middleware";

// `workspaceSlug` reads its root domain from NEXT_PUBLIC_PORTAL_DOMAIN at
// module load time. Stub the env var and load the module fresh so these
// tests are deterministic regardless of what the ambient environment has
// set (or not set) for that variable.
let workspaceSlug: (host: string | null) => string | null;
let middleware: typeof MiddlewareFn;
let config: { matcher: string[] };

beforeAll(async () => {
  // Vitest isolates each test file's module registry, and this is the
  // first (and only) import of "./middleware" in this file, so stubbing
  // the env var here -- before that import -- is enough to pin the value
  // PORTAL_DOMAIN captures at module load. (Deliberately not pairing this
  // with vi.resetModules(): that would also force a second, distinct
  // "next/server" module instance for middleware.ts's internal import,
  // diverging from the one this file imports statically below.)
  vi.stubEnv("NEXT_PUBLIC_PORTAL_DOMAIN", "localhost:3000");
  ({ workspaceSlug, middleware, config } = await import("./middleware"));
});

afterAll(() => {
  vi.unstubAllEnvs();
});

describe("workspaceSlug", () => {
  it("resolves an ordinary subdomain to its slug", () => {
    expect(workspaceSlug("acme.localhost:3000")).toBe("acme");
  });

  it("resolves the same host without a port", () => {
    expect(workspaceSlug("acme.localhost")).toBe("acme");
  });

  it("resolves nothing for the bare portal domain with a port", () => {
    expect(workspaceSlug("localhost:3000")).toBeNull();
  });

  it("resolves nothing for the bare portal domain without a port", () => {
    expect(workspaceSlug("localhost")).toBeNull();
  });

  it("resolves an uppercase host the same as its lowercase equivalent", () => {
    // Regression pin: an earlier version of this function compared the
    // lowercased host label against the *unlowercased* root, so a
    // mixed-case Host header failed to resolve at all.
    expect(workspaceSlug("ACME.localhost:3000")).toBe("acme");
  });

  it("resolves a mixed-case host the same way", () => {
    expect(workspaceSlug("Acme.LocalHost:3000")).toBe("acme");
  });

  it("does not treat a multi-label subdomain as a workspace slug", () => {
    expect(workspaceSlug("a.acme.localhost:3000")).toBeNull();
  });

  it.each(["www", "app", "api", "admin", "mail", "inbound"])(
    "resolves nothing for the reserved label %s",
    (label) => {
      expect(workspaceSlug(`${label}.localhost:3000`)).toBeNull();
    },
  );

  it("does not resolve a lookalike host with no dot before the root", () => {
    // "evil-localhost" ends with the literal string "localhost" but is not
    // a subdomain of it -- the match must be anchored on a dot.
    expect(workspaceSlug("evil-localhost:3000")).toBeNull();
  });

  it("does not resolve a host where the root domain appears as a non-suffix", () => {
    // The portal domain shows up mid-host here, not as the actual root --
    // an unanchored suffix check would wrongly treat "foo" as a slug.
    expect(workspaceSlug("foo.localhost.attacker.com")).toBeNull();
  });

  it("returns null for a missing Host header", () => {
    expect(workspaceSlug(null)).toBeNull();
  });

  it("returns null for an empty Host header", () => {
    expect(workspaceSlug("")).toBeNull();
  });

  // Current, possibly-unintended behaviour: a trailing dot on the host
  // (legal in DNS -- it denotes an absolute/FQDN name) is not stripped
  // before the suffix check, so it breaks the match entirely instead of
  // being treated the same as the dot-less host. This test documents what
  // the code does today; see the report for the flag raised about it.
  it("does NOT resolve a slug when the host has a trailing dot", () => {
    expect(workspaceSlug("acme.localhost.:3000")).toBeNull();
  });
});

describe("middleware header sanitisation", () => {
  // The workspace header must only ever be set from a resolved Host, never
  // trusted from the incoming request. `NextResponse.next({ request:
  // { headers } })` communicates the modified downstream request headers
  // to Next.js via `x-middleware-request-<name>` response headers plus an
  // `x-middleware-override-headers` manifest -- that's what these
  // assertions read.
  const OVERRIDE_HEADER = "x-middleware-override-headers";
  const REQUEST_HEADER_PREFIX = "x-middleware-request-";
  const WORKSPACE_HEADER = "x-relaydesk-workspace";

  it("replaces a client-supplied workspace header with the one resolved from Host", () => {
    const request = new NextRequest("http://acme.localhost:3000/help", {
      headers: { host: "acme.localhost:3000", [WORKSPACE_HEADER]: "evil" },
    });

    const response = middleware(request);

    expect(response.headers.get(OVERRIDE_HEADER)?.split(",")).toContain(WORKSPACE_HEADER);
    expect(response.headers.get(REQUEST_HEADER_PREFIX + WORKSPACE_HEADER)).toBe("acme");
  });

  it("strips a client-supplied workspace header entirely when the Host does not resolve", () => {
    const request = new NextRequest("http://example.com/random-page", {
      headers: { host: "example.com", [WORKSPACE_HEADER]: "evil" },
    });

    const response = middleware(request);

    // Not merely "not evil" -- absent altogether. A host with no matching
    // subdomain must not carry the header downstream at all.
    expect(response.headers.get(OVERRIDE_HEADER)?.split(",") ?? []).not.toContain(
      WORKSPACE_HEADER,
    );
    expect(response.headers.get(REQUEST_HEADER_PREFIX + WORKSPACE_HEADER)).toBeNull();
  });

  // The contract changed with the reverse proxy. Behind one, the socket
  // address Next would fall back to is the *proxy's*, so stripping this
  // header collapses every visitor in the world into a single rate-limit
  // bucket and TICKET_IP_HOURLY_CAP then throttles all of them to five an
  // hour -- silently, and failing closed.
  //
  // What replaces "strip everything" as the guarantee is that nothing but
  // the proxy can reach this container: the web service publishes no port,
  // and the proxy itself accepts X-Forwarded-For only from its own
  // upstream edge. Both halves are required; see middleware.ts.
  it("preserves a proxy-supplied X-Forwarded-For", () => {
    const request = new NextRequest("http://acme.localhost:3000/submit-ticket", {
      headers: { host: "acme.localhost:3000", "x-forwarded-for": "203.0.113.7" },
    });

    const response = middleware(request);

    expect(response.headers.get(OVERRIDE_HEADER)?.split(",")).toContain(
      "x-forwarded-for",
    );
    expect(response.headers.get(REQUEST_HEADER_PREFIX + "x-forwarded-for")).toBe(
      "203.0.113.7",
    );
  });

  it("preserves it on every other matched route too", () => {
    const request = new NextRequest("http://localhost:3000/forgot-password", {
      headers: { host: "localhost:3000", "x-forwarded-for": "203.0.113.9" },
    });

    const response = middleware(request);

    expect(response.headers.get(REQUEST_HEADER_PREFIX + "x-forwarded-for")).toBe(
      "203.0.113.9",
    );
  });
});

describe("root path resolution", () => {
  const WORKSPACE_HEADER = "x-relaydesk-workspace";

  it("redirects a resolved subdomain's root to the help centre", () => {
    const request = new NextRequest("http://acme.localhost:3000/", {
      headers: { host: "acme.localhost:3000" },
    });

    const response = middleware(request);

    expect(response.status).toBe(307);
    const location = response.headers.get("location");
    expect(location).not.toBeNull();
    expect(new URL(location!).pathname).toBe("/help");
  });

  it("leaves the apex root alone -- no redirect, so the marketing site still renders", () => {
    const request = new NextRequest("http://localhost:3000/", {
      headers: { host: "localhost:3000" },
    });

    const response = middleware(request);

    expect(response.status).not.toBe(307);
    expect(response.headers.get("location")).toBeNull();
  });

  it("does not redirect a reserved label's root -- it never resolves to a workspace", () => {
    const request = new NextRequest("http://www.localhost:3000/", {
      headers: { host: "www.localhost:3000" },
    });

    const response = middleware(request);

    expect(response.status).not.toBe(307);
    expect(response.headers.get("location")).toBeNull();
  });

  it("still strips a client-supplied workspace header on the apex root", () => {
    const request = new NextRequest("http://localhost:3000/", {
      headers: { host: "localhost:3000", [WORKSPACE_HEADER]: "evil" },
    });

    const response = middleware(request);

    const OVERRIDE_HEADER = "x-middleware-override-headers";
    expect(response.headers.get(OVERRIDE_HEADER)?.split(",") ?? []).not.toContain(
      WORKSPACE_HEADER,
    );
  });
});

/**
 * The console's article preview, `/knowledge-base/{id}/preview`, is the one
 * route in the console that deliberately renders *unpublished* content: a
 * signed-in member reads a draft there through the authenticated API, which
 * is the whole point of it. Nothing about /help changes, but that makes the
 * gate in front of it worth pinning rather than re-deriving from "it starts
 * with /knowledge-base, and /knowledge-base is in PROTECTED".
 *
 * These call the real exported `middleware` and read the real exported
 * `config` -- nothing about the session check or the matcher is stubbed --
 * so they fail if the PROTECTED list loses its entry, if the matcher is
 * narrowed to /knowledge-base alone, or if the subdomain branch above starts
 * swallowing console paths.
 *
 * They cover the *middleware* layer only. The second gate -- `apiFetch`
 * sending a bearer and turning the API's 401 into a redirect to
 * /signed-out -- cannot be reached from here, because it lives in a server
 * component's data layer rather than in this function; see the report.
 */
describe("the console article preview is behind the session", () => {
  const PREVIEW = "/knowledge-base/c71ef494-3264-4fe8-b79d-427d94b5fd6f/preview";

  it("redirects an anonymous request to the sign-in page", () => {
    const request = new NextRequest(`http://localhost:3000${PREVIEW}`, {
      headers: { host: "localhost:3000" },
    });

    const response = middleware(request);

    expect(response.status).toBe(307);
    const location = response.headers.get("location");
    expect(location).not.toBeNull();
    expect(new URL(location!).pathname).toBe("/login");
  });

  // The control for the test above: without this, a middleware that
  // redirected *everything* would pass it and prove nothing about the
  // session being what makes the difference.
  it("lets a request carrying a session cookie through", () => {
    const request = new NextRequest(`http://localhost:3000${PREVIEW}`, {
      headers: { host: "localhost:3000", cookie: "rd_session=a-real-token" },
    });

    const response = middleware(request);

    expect(response.status).not.toBe(307);
    expect(response.headers.get("location")).toBeNull();
  });

  // A portal subdomain never resolves console routes to anything a reader
  // can use -- the request falls through to `apiFetch` with no bearer and
  // comes back as a redirect to /signed-out. This asserts the one thing
  // *this* function is responsible for on that host: it does not hand the
  // route a workspace it could serve content for by itself.
  it("does not render console content on a portal subdomain either", () => {
    const request = new NextRequest(`http://acme.localhost:3000${PREVIEW}`, {
      headers: { host: "acme.localhost:3000" },
    });

    const response = middleware(request);

    // No session, no redirect to /login on this host -- see the report's
    // note about the subdomain branch returning early. What stops it is the
    // API refusing an unauthenticated read, one layer down.
    expect(response.headers.get("location")).toBeNull();
  });
});

describe("matcher coverage", () => {
  // Every other test in this file calls `middleware()` directly, which
  // bypasses `config.matcher` entirely -- so all of them would still pass
  // if the /submit-ticket entry were deleted and the middleware simply
  // stopped running on that route. It is the route the public ticket form
  // posts from, and the middleware still has to run there to resolve the
  // workspace slug from Host and set it on the request; with no matcher
  // entry, that resolution never happens and the form has no workspace to
  // submit its ticket against.
  //
  // Next compiles these patterns with path-to-regexp, which is not a
  // dependency here. These two forms are the only ones this file uses, so
  // they are converted directly rather than approximated: a literal path,
  // and a literal path followed by `/:param*` (zero or more trailing
  // segments -- which is why `/submit-ticket` itself matches
  // `/submit-ticket/:path*`).
  function matches(pattern: string, pathname: string): boolean {
    const suffix = "/:path*";
    if (pattern.endsWith(suffix)) {
      const base = pattern.slice(0, -suffix.length);
      return pathname === base || pathname.startsWith(`${base}/`);
    }
    return pathname === pattern;
  }

  function covered(pathname: string): boolean {
    return config.matcher.some((pattern) => matches(pattern, pathname));
  }

  it("runs the middleware on the public ticket form's route", () => {
    expect(covered("/submit-ticket")).toBe(true);
  });

  it("runs it on paths beneath that route too", () => {
    expect(covered("/submit-ticket/anything")).toBe(true);
  });

  it("still runs it on the help centre and the app's protected routes", () => {
    expect(covered("/help/billing/refunds")).toBe(true);
    expect(covered("/conversations")).toBe(true);
    expect(covered("/settings/channels")).toBe(true);
  });

  // The other half of the guarantee in "the console article preview is
  // behind the session" above. That block calls `middleware()` directly, so
  // it would keep passing if the /knowledge-base entry were narrowed to the
  // bare path and the middleware simply stopped running on routes beneath
  // it -- at which point the one console route that renders drafts would be
  // reachable with no session check at all.
  it("runs it on the console's article preview route", () => {
    expect(covered("/knowledge-base/an-article-id/preview")).toBe(true);
  });

  // The forgot-password form's server action forwards X-Forwarded-For to
  // the API's per-IP password-reset rate limiter the same way the ticket
  // form does. A Server Action POSTs to its own page URL, so without this
  // matcher entry the middleware never runs on that route at all -- and it
  // is what sets the workspace header for the request, the same job it does
  // on every other matched route -- see lib/api/password-reset.ts and the
  // final-branch report.
  it("runs it on the forgot-password route", () => {
    expect(covered("/forgot-password")).toBe(true);
  });

  it("does not claim to cover a route that is deliberately unmatched", () => {
    // /invites is excluded on purpose -- see the comment at the top of
    // middleware.ts. If this ever starts passing, the helper above has
    // become too generous to be proving anything.
    expect(covered("/invites")).toBe(false);
  });
});
