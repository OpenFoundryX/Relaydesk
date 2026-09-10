import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WidgetKeys } from "@/components/settings/widget-keys";

const key = {
  id: "1",
  name: "Marketing site",
  key: "rdw_abc",
  allowedOrigins: [],
  settings: {},
  active: true,
  lastSeenAt: null,
  createdAt: "2026-09-10T00:00:00Z",
};

describe("WidgetKeys", () => {
  it("says an embed with no origins will not load", () => {
    // An empty allowlist refuses. Without this the admin sees a snippet
    // that looks finished and a widget that silently never appears.
    render(<WidgetKeys keys={[key]} />);
    expect(screen.getByText(/add the sites/i)).toBeTruthy();
  });

  it("shows the snippet with the key in it", () => {
    render(<WidgetKeys keys={[{ ...key, allowedOrigins: ["https://acme.com"] }]} />);
    expect(screen.getByText(/data-key="rdw_abc"/)).toBeTruthy();
  });
});
