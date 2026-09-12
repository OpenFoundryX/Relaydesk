/**
 * @vitest-environment node
 */
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

// `lib/api/client` is `server-only`, which throws the moment it is loaded
// in a client-ish test environment. Route handlers are server code, so the
// environment is the thing that is wrong here, not the import.
vi.mock("server-only", () => ({}));

class FakeApiError extends Error {
  constructor(public status: number) {
    super(`api ${status}`);
  }
}

vi.mock("@/lib/api/client", () => ({
  apiFetch: vi.fn(),
  ApiError: FakeApiError,
}));

const { GET } = await import("@/app/(widget)/widget/kb/collections/route");
const { apiFetch } = await import("@/lib/api/client");
const mocked = vi.mocked(apiFetch);

function get(query: string) {
  return GET(new NextRequest(`http://localhost/widget/kb/collections?${query}`));
}

const ARTICLE = (id: string) => ({
  id,
  title: id,
  slug: id,
  excerpt: "",
  path: `billing/${id}`,
});

afterEach(() => {
  mocked.mockReset();
});

describe("the Help tab's collections route", () => {
  it("lists a collection's own articles and its sections' together", async () => {
    // `article_count` counts both, so a collection whose articles all live
    // in sections would otherwise show a count and then an empty list --
    // the bug this flattening exists to prevent. Nothing exercised the
    // route itself until this test, and removing the flattening passed the
    // whole component suite.
    mocked.mockResolvedValue({
      kind: "category",
      category: { id: "c", name: "Billing", slug: "billing", description: "", icon: "", articleCount: 3 },
      articles: [ARTICLE("direct")],
      sections: [{ articles: [ARTICLE("nested-one")] }, { articles: [ARTICLE("nested-two")] }],
    });

    const body = await (await get("key=rdw_x&path=billing")).json();

    expect(body.articles.map((article: { id: string }) => article.id)).toEqual([
      "direct",
      "nested-one",
      "nested-two",
    ]);
  });

  it("returns the root collections when no path is given", async () => {
    mocked.mockResolvedValue([
      { id: "c", name: "Billing", slug: "billing", description: "", icon: "", articleCount: 3 },
    ]);

    const body = await (await get("key=rdw_x")).json();

    expect(body).toHaveLength(1);
    expect(mocked).toHaveBeenCalledWith("/widget/rdw_x/kb", { auth: false });
  });

  it("treats an unknown key as nothing here, not as an error", async () => {
    // A frame's session outlives a key that is deactivated mid-visit. The
    // visitor gets an empty shelf, never a stack trace.
    mocked.mockRejectedValue(new FakeApiError(404));

    expect(await (await get("key=rdw_x")).json()).toEqual([]);
    expect(await (await get("key=rdw_x&path=billing")).json()).toBeNull();
  });

  it("asks for nothing at all without a key", async () => {
    expect(await (await get("")).json()).toEqual([]);
    expect(mocked).not.toHaveBeenCalled();
  });

  it("encodes a path one segment at a time", async () => {
    // Encoding the whole path as one string would turn its slashes into
    // %2F and resolve nothing.
    mocked.mockResolvedValue({
      kind: "category",
      category: { id: "c", name: "B", slug: "b", description: "", icon: "", articleCount: 0 },
      articles: [],
      sections: [],
    });

    await get("key=rdw_x&path=billing/plans%20and%20pricing");

    expect(mocked).toHaveBeenCalledWith(
      "/widget/rdw_x/kb/billing/plans%20and%20pricing",
      { auth: false },
    );
  });
});
