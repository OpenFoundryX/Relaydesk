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
    expect(screen.getByLabelText("Default")).toBeTruthy();
    expect(screen.getByLabelText("Indigo")).toBeTruthy();
    expect(screen.getByLabelText("Right (default)")).toBeTruthy();
    expect(screen.getByLabelText("Left")).toBeTruthy();
  });

  it("does not still tell an admin to re-paste the snippet", () => {
    // It used to, and correctly: the loader drew from its data-* attributes
    // and nothing corrected them. `/widget/launcher` was built to fix that
    // and the copy was never updated -- so the moment the route started
    // working, this paragraph became a lie that sends a customer round
    // every site they own re-pasting a snippet they need not touch.
    render(<WidgetKeyDialog open onOpenChange={() => {}} />);
    expect(screen.queryByText(/re-paste/i)).toBeNull();
    expect(screen.getByText(/corrects itself/i)).toBeTruthy();
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
    expect((screen.getByLabelText("Indigo") as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText("Left") as HTMLInputElement).checked).toBe(true);
  });

  it("sends the branding fields as settings on create", () => {
    createWidgetKeyAction.mockResolvedValue({ ok: true });
    render(<WidgetKeyDialog open onOpenChange={() => {}} />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Site" } });
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Acme Support" },
    });
    fireEvent.click(screen.getByLabelText("Indigo"));
    fireEvent.click(screen.getByLabelText("Left"));
    fireEvent.click(screen.getByRole("button", { name: "Create embed" }));

    expect(createWidgetKeyAction).toHaveBeenCalledWith(
      expect.objectContaining({
        settings: { name: "Acme Support", accentColour: "#4F46E5", position: "left" },
      }),
    );
  });

  it("keeps a colour saved outside the palette", () => {
    // Narrowing the choices must not silently restyle an embed already
    // live on someone's site, so whatever it was saved with stays
    // selectable and selected.
    render(
      <WidgetKeyDialog
        widgetKey={{ ...baseKey, settings: { accentColour: "#123456" } }}
        open
        onOpenChange={() => {}}
      />,
    );

    const current = screen.getByLabelText(/Current \(#123456\)/) as HTMLInputElement;
    expect(current.checked).toBe(true);
  });

  it("cannot produce an invalid colour at all", () => {
    // The old free-text field let someone type #FFFDF5 and ship an
    // invisible launcher. Every swatch is a known-good value, so the
    // failure mode is gone rather than guarded.
    render(<WidgetKeyDialog open onOpenChange={() => {}} />);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Site" } });
    fireEvent.click(screen.getByLabelText("Amber"));

    expect(
      (screen.getByRole("button", { name: "Create embed" }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });
});
