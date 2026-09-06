import { describe, expect, it } from "vitest";

import { STATUS_CONTROL, TRANSITIONS } from "./article-status";
import type { ArticleStatus } from "@/lib/types";

const statuses: ArticleStatus[] = ["draft", "ready", "published"];

/**
 * `TRANSITIONS` is a hand-kept copy of `ALLOWED_TRANSITIONS` in the API's
 * `services/kb_articles.py`. These assertions are the copy checked back
 * against the original, spelled out rather than derived, so that changing
 * one table without the other fails here instead of at a user's click.
 */
describe("the review workflow", () => {
  it("is exactly the API's four edges", () => {
    expect(TRANSITIONS).toEqual({
      draft: ["ready"],
      ready: ["draft", "published"],
      published: ["draft"],
    });
  });

  it("has no published -> ready edge", () => {
    expect(TRANSITIONS.published).not.toContain("ready");
  });
});

describe("the status control", () => {
  it("never names a target the API would refuse", () => {
    for (const status of statuses) {
      const control = STATUS_CONTROL[status];
      const offered = [
        control.toggleTo,
        // A disabled Publish button names no destination at all, so there is
        // nothing here to check -- and nothing for it to get wrong.
        ...(control.publish?.enabled ? [control.publish.to] : []),
      ];
      for (const target of offered) {
        expect(
          TRANSITIONS[status],
          `${status} must not offer ${target}`,
        ).toContain(target);
      }
    }
  });

  it("maps each state to the toggle and Publish button the console shows", () => {
    expect(STATUS_CONTROL.draft).toMatchObject({
      toggleOn: false,
      toggleTo: "ready",
      // Shown, disabled, and pointed nowhere.
      publish: { enabled: false },
    });
    expect(STATUS_CONTROL.draft.publish).not.toHaveProperty("to");
    expect(STATUS_CONTROL.ready).toMatchObject({
      toggleOn: true,
      toggleTo: "draft",
      publish: { enabled: true, to: "published" },
    });
    // Live: the toggle is the unpublish, and there is no Publish button to
    // press. It goes to draft, because published -> ready does not exist.
    expect(STATUS_CONTROL.published).toMatchObject({
      toggleLabel: "Published",
      toggleOn: true,
      toggleTo: "draft",
      publish: null,
    });
  });
});
