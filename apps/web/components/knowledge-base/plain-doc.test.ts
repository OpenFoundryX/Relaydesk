import { describe, expect, it } from "vitest";

import { plainDoc } from "./plain-doc";

/** An attrs object exactly as prosemirror-model builds one. */
function pmAttrs(values: Record<string, unknown>) {
  return Object.assign(Object.create(null), values);
}

describe("plainDoc", () => {
  it("keeps the attributes a ProseMirror document carries", () => {
    const doc = {
      type: "doc",
      content: [
        { type: "heading", attrs: pmAttrs({ level: 2 }), content: [] },
        { type: "image", attrs: pmAttrs({ id: "abc-123", alt: "shot.png" }) },
      ],
    };

    expect(plainDoc(doc)).toEqual({
      type: "doc",
      content: [
        { type: "heading", attrs: { level: 2 }, content: [] },
        { type: "image", attrs: { id: "abc-123", alt: "shot.png" } },
      ],
    });
  });

  it("gives every nested object an ordinary prototype", () => {
    // The whole point. `attrs` reaches here with a null prototype, which is
    // what a Server Action's encoder drops -- silently, so the article saves
    // and only the published page shows the loss.
    const doc = {
      type: "doc",
      content: [{ type: "image", attrs: pmAttrs({ id: "abc-123" }) }],
    };

    const out = plainDoc(doc) as {
      content: { attrs: Record<string, unknown> }[];
    };

    expect(Object.getPrototypeOf(out.content[0].attrs)).toBe(Object.prototype);
  });

  it("leaves a document that is already plain untouched", () => {
    const doc = { type: "doc", content: [{ type: "paragraph" }] };

    expect(plainDoc(doc)).toEqual(doc);
  });
});
