import { afterEach, describe, expect, it } from "vitest";
import { readFileSync, statSync } from "node:fs";

describe("loader", () => {
  it("stays under the 3 KB budget", () => {
    // Spec D6: this is the argument for choosing the widget over a heavier
    // messenger, so a regression here is a regression in the pitch.
    expect(statSync("public/widget.js").size).toBeLessThan(3072);
  });

  it("injects no iframe until the launcher is clicked", () => {
    const source = readFileSync("public/widget.js", "utf8");
    const launcher = source.indexOf("createElement(\"button\")");
    const frame = source.indexOf("createElement(\"iframe\")");
    expect(launcher).toBeGreaterThan(-1);
    expect(frame).toBeGreaterThan(launcher);
  });
});

/**
 * The source-order check above would still pass for a file that was
 * textually ordered correctly but behaviourally wrong. This block actually
 * runs the loader in jsdom and drives it, because its <script> contract is
 * frozen the moment a customer pastes it -- there is no second chance to
 * add coverage for a behaviour that ships broken.
 */
describe("loader behaviour", () => {
  const source = readFileSync("public/widget.js", "utf8");
  const SCRIPT_ORIGIN = "https://relay.example.com";

  // Every `window.addEventListener` call the loader makes while it runs is
  // recorded here, so afterEach can remove it -- without this, a `message`
  // listener from one test would still be registered (and firing) during
  // the next one, since the loader itself never calls removeEventListener
  // and jsdom's `window` is shared across tests in this file.
  let registered: Array<[string, EventListener]> = [];

  /**
   * Runs the loader exactly as a browser would for a
   * `<script async src=".../widget.js" data-key="...">` tag, with
   * `document.currentScript` pointed at a detached <script> element carrying
   * the given attributes -- detached so setting its `src` triggers no
   * jsdom resource fetch, which the loader never needs since it only reads
   * `tag.src` and `tag.getAttribute(...)`.
   */
  function loadWidget(attrs: Record<string, string>) {
    const tag = document.createElement("script");
    tag.src = `${SCRIPT_ORIGIN}/widget.js`;
    for (const [name, value] of Object.entries(attrs)) {
      tag.setAttribute(name, value);
    }
    Object.defineProperty(document, "currentScript", {
      value: tag,
      configurable: true,
    });

    const originalAdd = window.addEventListener.bind(window);
    window.addEventListener = ((type: string, listener: EventListener, options?: unknown) => {
      registered.push([type, listener]);
      return originalAdd(type, listener, options as AddEventListenerOptions);
    }) as typeof window.addEventListener;

    try {
      // Exercising the static asset exactly as a browser would eval it
      // from a <script> tag -- it is not imported as a module, so this is
      // the only way to run it under test at all.
      (0, eval)(source);
    } finally {
      window.addEventListener = originalAdd;
    }
  }

  afterEach(() => {
    for (const [type, listener] of registered) {
      window.removeEventListener(type, listener);
    }
    registered = [];
    document.body.innerHTML = "";
    // Each load appends its own <style> tag to <head> (the mobile-takeover
    // breakpoint) -- clear it too, or later tests see every earlier test's
    // copy as well as their own.
    document.head.innerHTML = "";
    Object.defineProperty(document, "currentScript", { value: null, configurable: true });
    // The re-entry guard is deliberately global (window.__relaydeskWidget)
    // so a real duplicate <script> tag is a no-op; reset it between tests
    // so each test gets a fresh load rather than being silently skipped by
    // the previous test's guard.
    delete (window as unknown as { __relaydeskWidget?: boolean }).__relaydeskWidget;
  });

  function dispatchClose(origin: string) {
    window.dispatchEvent(
      new MessageEvent("message", { data: "relaydesk:close", origin }),
    );
  }

  it("keeps the iframe out of the DOM until the launcher is clicked, then adds it", () => {
    loadWidget({ "data-key": "rdw_test" });

    expect(document.querySelector("iframe")).toBeNull();

    document.querySelector<HTMLButtonElement>("button")!.click();

    const frame = document.querySelector("iframe");
    expect(frame).not.toBeNull();
    expect(frame!.style.display).not.toBe("none");
  });

  it("does not close the panel for a relaydesk:close message from a different origin", () => {
    loadWidget({ "data-key": "rdw_test" });
    document.querySelector<HTMLButtonElement>("button")!.click();
    const frame = document.querySelector<HTMLIFrameElement>("iframe")!;

    dispatchClose("https://evil.example.com");

    expect(frame.style.display).not.toBe("none");
  });

  it("closes the panel for a relaydesk:close message from the script's own origin", () => {
    loadWidget({ "data-key": "rdw_test" });
    document.querySelector<HTMLButtonElement>("button")!.click();
    const frame = document.querySelector<HTMLIFrameElement>("iframe")!;

    dispatchClose(SCRIPT_ORIGIN);

    expect(frame.style.display).toBe("none");
  });

  it("returns focus to the launcher when the panel closes via postMessage", () => {
    // Stands in for both real close paths that reach the loader this way
    // (Esc and the close button) -- both call the same
    // window.parent.postMessage("relaydesk:close", "*") in panel.tsx, so
    // the loader cannot and does not distinguish them.
    loadWidget({ "data-key": "rdw_test" });
    const launcher = document.querySelector<HTMLButtonElement>("button")!;
    launcher.click();

    // Move focus off the launcher first, so the assertion proves hide()
    // actively refocuses it rather than focus having simply never left.
    document.body.focus();
    expect(document.activeElement).not.toBe(launcher);

    dispatchClose(SCRIPT_ORIGIN);

    expect(document.activeElement).toBe(launcher);
  });

  it("returns focus to the launcher when clicked again to close", () => {
    loadWidget({ "data-key": "rdw_test" });
    const launcher = document.querySelector<HTMLButtonElement>("button")!;
    launcher.click();
    document.body.focus();

    launcher.click();

    expect(document.querySelector<HTMLIFrameElement>("iframe")!.style.display).toBe("none");
    expect(document.activeElement).toBe(launcher);
  });

  it("draws only one launcher when the script tag is included twice", () => {
    // A duplicate paste, a tag-manager duplicate, or an SPA re-injecting
    // the tag on navigation must not draw a second overlapping launcher.
    loadWidget({ "data-key": "rdw_test" });
    loadWidget({ "data-key": "rdw_test" });

    expect(document.querySelectorAll("button").length).toBe(1);
  });

  it("does nothing when data-key is missing", () => {
    loadWidget({});

    expect(document.querySelector("button")).toBeNull();
  });

  it("waits for DOMContentLoaded to mount if <body> doesn't exist yet", () => {
    // <script async> can execute before <body> exists (e.g. placed in
    // <head>); appendChild on a null <body> throws and no launcher is ever
    // drawn. Simulated here by nulling document.body for the load itself.
    const realBody = document.body;
    Object.defineProperty(document, "body", { value: null, configurable: true });

    expect(() => loadWidget({ "data-key": "rdw_test" })).not.toThrow();
    expect(realBody.querySelector("button")).toBeNull();

    Object.defineProperty(document, "body", { value: realBody, configurable: true });
    document.dispatchEvent(new Event("DOMContentLoaded"));

    expect(realBody.querySelector("button")).not.toBeNull();
  });

  it("ships a <style> tag carrying the mobile full-screen takeover breakpoint", () => {
    // Spec 7: below ~480px the panel is a full-screen takeover, not a
    // floating 380x600 card. An inline style can't hold a media query, so
    // this is what carries it -- and it is what makes resize and
    // orientation change correct with nothing for the loader to recompute.
    loadWidget({ "data-key": "rdw_test" });

    const style = document.head.querySelector("style");
    expect(style).not.toBeNull();
    expect(style!.textContent).toContain("@media(max-width:480px)");
    expect(style!.textContent).toContain("width:100%");
    expect(style!.textContent).toContain("height:100%");
  });

  it("does not let a keyless tag block a later, correctly configured one", () => {
    // Regression: the re-entry guard must be claimed only once a key is
    // confirmed. A customer's mistyped or missing data-key on a first tag
    // must not silently block a second, valid tag on the same page --
    // that would be a confusing failure with no widget and no error.
    loadWidget({});
    expect(document.querySelector("button")).toBeNull();

    loadWidget({ "data-key": "rdw_test" });
    expect(document.querySelector("button")).not.toBeNull();
  });
});
