/**
 * @vitest-environment node
 */
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/api/widget", () => ({ getWidgetBootstrap: vi.fn() }));

const { GET } = await import("@/app/(widget)/widget/launcher/route");
const { getWidgetBootstrap } = await import("@/lib/api/widget");
const mocked = vi.mocked(getWidgetBootstrap);

function get(query: string) {
  return GET(new Request(`http://localhost/widget/launcher?${query}`));
}

function bootstrap(settings: Record<string, unknown>) {
  return { settings } as Awaited<ReturnType<typeof getWidgetBootstrap>>;
}

afterEach(() => {
  mocked.mockReset();
});

describe("the launcher's branding route", () => {
  it("answers a cross-origin caller, because that is the only kind it has", async () => {
    // The loader runs on the CUSTOMER'S page and fetches this from
    // Relaydesk's origin, so every real call is cross-origin. Without
    // this header the browser rejects the response before the loader
    // sees it and the loader's own `.catch` swallows the failure in
    // silence -- the launcher keeps whatever the pasted snippet said and
    // a console change never arrives. `*` gives away nothing: the key is
    // public by construction and the answer is a colour and a corner.
    mocked.mockResolvedValue(bootstrap({ accentColour: "#0D9488", position: "left" }));

    const response = await get("key=rdw_x");

    expect(response.headers.get("access-control-allow-origin")).toBe("*");
    expect(await response.json()).toEqual({ accent: "#0D9488", position: "left" });
  });

  it("says so when a key has no colour of its own", async () => {
    // `null`, not an omitted field: the loader has to be able to tell
    // "this key has no colour" from "this route did not mention colour",
    // because only the first should clear an accent a snippet carries.
    mocked.mockResolvedValue(bootstrap({}));

    expect(await (await get("key=rdw_x")).json()).toEqual({ accent: null, position: "right" });
  });

  it("narrows position to the two corners that exist", async () => {
    mocked.mockResolvedValue(bootstrap({ position: "somewhere else" }));

    expect((await (await get("key=rdw_x")).json()).position).toBe("right");
  });

  it("is a 404 with no key and with an unknown one", async () => {
    expect((await get("")).status).toBe(404);
    expect(mocked).not.toHaveBeenCalled();

    mocked.mockResolvedValue(null);
    expect((await get("key=rdw_gone")).status).toBe(404);
  });
});
