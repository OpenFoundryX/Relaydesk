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

  it("omits data-accent and data-position from the snippet when no branding is configured", () => {
    render(<WidgetKeys keys={[{ ...key, allowedOrigins: ["https://acme.com"] }]} />);
    expect(screen.queryByText(/data-accent/)).toBeNull();
    expect(screen.queryByText(/data-position/)).toBeNull();
  });

  it("includes data-accent in the snippet when an accent colour is configured", () => {
    render(
      <WidgetKeys
        keys={[
          {
            ...key,
            allowedOrigins: ["https://acme.com"],
            settings: { accentColour: "#4F46E5" },
          },
        ]}
      />,
    );
    expect(screen.getByText(/data-accent="#4F46E5"/)).toBeTruthy();
  });

  it("includes data-position in the snippet only when the position is left", () => {
    render(
      <WidgetKeys
        keys={[
          {
            ...key,
            allowedOrigins: ["https://acme.com"],
            settings: { position: "left" },
          },
        ]}
      />,
    );
    expect(screen.getByText(/data-position="left"/)).toBeTruthy();
  });

  it("says plainly that a colour or position change needs a re-paste", () => {
    // A real cost to the admin, and must not be a surprise.
    render(<WidgetKeys keys={[{ ...key, allowedOrigins: ["https://acme.com"] }]} />);
    expect(screen.getByText(/re-paste/i)).toBeTruthy();
  });
});
