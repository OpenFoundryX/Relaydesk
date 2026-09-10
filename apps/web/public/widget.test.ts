import { describe, expect, it } from "vitest";
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
