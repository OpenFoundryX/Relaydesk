import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// See widget-key-dialog.test.ts for why this is mocked: the dialog imports
// the console's server actions module, whose "use server" exports mean
// nothing to plain Vitest.
const { createWidgetKeyAction, updateWidgetKeyAction } = vi.hoisted(() => ({
  createWidgetKeyAction: vi.fn(),
  updateWidgetKeyAction: vi.fn(),
}));
vi.mock("@/app/(console)/settings/widget/actions", () => ({
  createWidgetKeyAction,
  updateWidgetKeyAction,
}));

import { WidgetKeyDialog } from "@/components/settings/widget-key-dialog";
import type { WidgetKey } from "@/lib/api/widget-keys";

const baseKey: WidgetKey = {
  id: "1",
  name: "Marketing site",
  key: "rdw_abc",
  allowedOrigins: ["https://acme.com"],
  settings: {},
  active: true,
  lastSeenAt: null,
  createdAt: "2026-09-10T00:00:00Z",
};

beforeEach(() => {
  createWidgetKeyAction.mockReset();
  updateWidgetKeyAction.mockReset();
});

describe("WidgetKeyDialog branding section", () => {
  it("offers display name, greeting, accent colour and launcher position fields", () => {
    render(<WidgetKeyDialog open onOpenChange={() => {}} />);

    expect(screen.getByLabelText("Display name")).toBeTruthy();
    expect(screen.getByLabelText("Greeting")).toBeTruthy();
    expect(screen.getByLabelText("Accent colour")).toBeTruthy();
    expect(screen.getByLabelText("Right (default)")).toBeTruthy();
    expect(screen.getByLabelText("Left")).toBeTruthy();
  });

  it("says plainly that a colour or position change needs a re-paste", () => {
    render(<WidgetKeyDialog open onOpenChange={() => {}} />);
    expect(screen.getByText(/re-paste/i)).toBeTruthy();
  });

  it("opens pre-filled from an existing embed's settings", () => {
    render(
      <WidgetKeyDialog
        widgetKey={{
          ...baseKey,
          settings: {
            name: "Acme Support",
            greeting: "Hi! Need a hand?",
            accentColour: "#4F46E5",
            position: "left",
          },
        }}
        open
        onOpenChange={() => {}}
      />,
    );

    expect((screen.getByLabelText("Display name") as HTMLInputElement).value).toBe(
      "Acme Support",
    );
    expect((screen.getByLabelText("Greeting") as HTMLInputElement).value).toBe(
      "Hi! Need a hand?",
    );
    expect((screen.getByLabelText("Accent colour") as HTMLInputElement).value).toBe(
      "#4F46E5",
    );
    expect((screen.getByLabelText("Left") as HTMLInputElement).checked).toBe(true);
  });

  it("sends the branding fields as settings on create", () => {
    createWidgetKeyAction.mockResolvedValue({ ok: true });
    render(<WidgetKeyDialog open onOpenChange={() => {}} />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Site" } });
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Acme Support" },
    });
    fireEvent.change(screen.getByLabelText("Accent colour"), {
      target: { value: "#4F46E5" },
    });
    fireEvent.click(screen.getByLabelText("Left"));
    fireEvent.click(screen.getByRole("button", { name: "Create embed" }));

    expect(createWidgetKeyAction).toHaveBeenCalledWith(
      expect.objectContaining({
        settings: { name: "Acme Support", accentColour: "#4F46E5", position: "left" },
      }),
    );
  });

  it("disables saving when the accent colour is not a valid hex colour", () => {
    render(<WidgetKeyDialog open onOpenChange={() => {}} />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Site" } });
    fireEvent.change(screen.getByLabelText("Accent colour"), {
      target: { value: "not-a-colour" },
    });

    expect(
      (screen.getByRole("button", { name: "Create embed" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(screen.getByText(/hex colour/i)).toBeTruthy();
  });
});
