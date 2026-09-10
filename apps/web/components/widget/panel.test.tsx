import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Panel } from "@/components/widget/panel";

const workspace = { workspaceName: "Beacon", monogram: "BE", settings: {} };

describe("Panel", () => {
  it("offers search when the knowledge base has articles", () => {
    render(<Panel {...workspace} articleCount={12} />);
    expect(screen.getByPlaceholderText("Search for an answer")).toBeTruthy();
  });

  it("skips search entirely when there are no articles", () => {
    // The day-one state for every new customer: a search box over nothing
    // makes the product look broken on the day it is being judged.
    render(<Panel {...workspace} articleCount={0} />);
    expect(screen.queryByPlaceholderText("Search for an answer")).toBeNull();
    expect(screen.getByLabelText("Your message")).toBeTruthy();
  });
});
