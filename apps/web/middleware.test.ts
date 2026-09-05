import { NextRequest } from "next/server";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import type { middleware as MiddlewareFn } from "./middleware";

// `workspaceSlug` reads its root domain from NEXT_PUBLIC_PORTAL_DOMAIN at
// module load time. Stub the env var and load the module fresh so these
// tests are deterministic regardless of what the ambient environment has
// set (or not set) for that variable.
let workspaceSlug: (host: string | null) => string | null;
let middleware: typeof MiddlewareFn;

beforeAll(async () => {
  // Vitest isolates each test file's module registry, and this is the
  // first (and only) import of "./middleware" in this file, so stubbing
  // the env var here -- before that import -- is enough to pin the value
  // PORTAL_DOMAIN captures at module load. (Deliberately not pairing this
  // with vi.resetModules(): that would also force a second, distinct
  // "next/server" module instance for middleware.ts's internal import,
  // diverging from the one this file imports statically below.)
  vi.stubEnv("NEXT_PUBLIC_PORTAL_DOMAIN", "localhost:3000");
  ({ workspaceSlug, middleware } = await import("./middleware"));
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
});
