"use client";

import { useState, useTransition } from "react";
import { Plus } from "lucide-react";

import {
  createWidgetKeyAction,
  updateWidgetKeyAction,
} from "@/app/(console)/settings/widget/actions";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { WidgetKey, WidgetKeySettings } from "@/lib/api/widget-keys";

export function parseOrigins(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "");
}

const HEX_COLOUR_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

/** Accepts blank -- accent colour is optional -- and any 3- or 6-digit hex
 * colour. Mirrors `_HEX_COLOUR_RE` in `services/widget_keys.py`, which is
 * the check that actually matters: this one only saves the admin a round
 * trip to find out. */
export function isValidAccentColour(value: string): boolean {
  return value.trim() === "" || HEX_COLOUR_RE.test(value.trim());
}

type BrandingFields = {
  name: string;
  greeting: string;
  accentColour: string;
  position: "left" | "right";
};

/**
 * Builds the `settings` object a save sends, from the branding form's raw
 * field state. Every field left blank is omitted rather than sent as an
 * empty string, so an untouched form round-trips to exactly `{}` -- absent
 * means today's unbranded behaviour, unchanged (spec D10). `position` is
 * included only as `"left"`: `"right"` is the loader's own fallback
 * (`public/widget.js`), so storing it explicitly would say nothing an
 * absent setting doesn't already say.
 */
export function buildSettingsInput(fields: BrandingFields): WidgetKeySettings {
  const settings: WidgetKeySettings = {};
  if (fields.name.trim()) settings.name = fields.name.trim();
  if (fields.greeting.trim()) settings.greeting = fields.greeting.trim();
  if (fields.accentColour.trim()) settings.accentColour = fields.accentColour.trim();
  if (fields.position === "left") settings.position = "left";
  return settings;
}

/**
 * Create an embed, or edit one's name and allowlist.
 *
 * There is no secret-reveal step here: unlike an API key's token or a
 * webhook's signing secret, the widget key is meant to live in public page
 * source, so the API hands it back in full on every read -- see `key` on
 * `WidgetKey`. The list row already shows it; this dialog only ever asks for
 * the two fields the admin can change.
 */
export function WidgetKeyDialog({
  widgetKey,
  open,
  onOpenChange,
}: {
  widgetKey?: WidgetKey;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{widgetKey ? "Edit embed" : "New embed"}</DialogTitle>
          <DialogDescription>
            {widgetKey
              ? "Changes to the allowlist take effect immediately -- a site removed here stops loading the widget on its next page view."
              : "Paste the snippet this creates into every page that should show the widget."}
          </DialogDescription>
        </DialogHeader>
        {/* Radix unmounts the content on close, so a form left half-filled
            never survives to the next open -- compare `snippet-dialog.tsx`. */}
        <WidgetKeyForm widgetKey={widgetKey} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function WidgetKeyForm({
  widgetKey,
  onClose,
}: {
  widgetKey?: WidgetKey;
  onClose: () => void;
}) {
  const [name, setName] = useState(widgetKey?.name ?? "");
  const [origins, setOrigins] = useState(widgetKey?.allowedOrigins.join("\n") ?? "");
  const [brandName, setBrandName] = useState(widgetKey?.settings.name ?? "");
  const [greeting, setGreeting] = useState(widgetKey?.settings.greeting ?? "");
  const [accentColour, setAccentColour] = useState(widgetKey?.settings.accentColour ?? "");
  const [position, setPosition] = useState<"left" | "right">(
    widgetKey?.settings.position ?? "right",
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const accentValid = isValidAccentColour(accentColour);

  function save() {
    setError(null);
    start(async () => {
      const input = {
        name: name.trim(),
        allowedOrigins: parseOrigins(origins),
        settings: buildSettingsInput({ name: brandName, greeting, accentColour, position }),
      };
      const result = widgetKey
        ? await updateWidgetKeyAction(widgetKey.id, input)
        : await createWidgetKeyAction(input);
      // A 422 (a value that isn't a URL, or an invalid colour) is the
      // failure an admin is most likely to hit here, so it keeps the
      // dialog open with what was typed.
      if (result.ok) onClose();
      else setError(result.message);
    });
  }

  return (
    <>
      <DialogBody>
        <div className="space-y-1.5">
          <Label htmlFor="widget-key-name">Name</Label>
          <Input
            id="widget-key-name"
            placeholder="Marketing site"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="widget-key-origins">Allowed origins</Label>
          <Textarea
            id="widget-key-origins"
            placeholder={"https://example.com\nhttps://app.example.com"}
            className="min-h-24 font-mono"
            value={origins}
            onChange={(event) => setOrigins(event.target.value)}
          />
          <p className="text-[12px] text-ink-500">
            One per line. The widget refuses to load on any site not listed here
            -- leave this empty and it will not appear anywhere.
          </p>
        </div>

        <fieldset className="space-y-3 rounded-md border border-ink-200 p-3">
          <legend className="px-1 text-[13px] font-medium text-ink-900">Branding</legend>

          <div className="space-y-1.5">
            <Label htmlFor="widget-key-brand-name">Display name</Label>
            <Input
              id="widget-key-brand-name"
              placeholder="Acme Support"
              value={brandName}
              onChange={(event) => setBrandName(event.target.value)}
            />
            <p className="text-[12px] text-ink-500">
              Shown in the widget&apos;s header instead of your workspace name.
              Leave blank to keep showing your workspace name.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="widget-key-greeting">Greeting</Label>
            <Input
              id="widget-key-greeting"
              placeholder="Hi there. How can we help?"
              value={greeting}
              onChange={(event) => setGreeting(event.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="widget-key-accent">Accent colour</Label>
            <Input
              id="widget-key-accent"
              placeholder="#18181B"
              value={accentColour}
              onChange={(event) => setAccentColour(event.target.value)}
            />
            {!accentValid && (
              <p className="text-[12px] text-danger-700">
                Enter a hex colour, like #4F46E5.
              </p>
            )}
          </div>

          <fieldset className="space-y-1.5">
            <legend className="text-[13px] text-ink-700">Launcher position</legend>
            <label className="flex items-center gap-2 text-[13px] text-ink-700">
              <input
                type="radio"
                name="widget-key-position"
                checked={position === "right"}
                onChange={() => setPosition("right")}
              />
              Right (default)
            </label>
            <label className="flex items-center gap-2 text-[13px] text-ink-700">
              <input
                type="radio"
                name="widget-key-position"
                checked={position === "left"}
                onChange={() => setPosition("left")}
              />
              Left
            </label>
          </fieldset>

          <p className="text-[12px] text-ink-500">
            Colour and position are drawn by the script tag itself, before the
            panel ever opens -- changing either here takes effect only once
            you re-paste the updated snippet wherever this embed is installed.
          </p>
        </fieldset>

        {error && (
          <p role="alert" className="text-[13px] text-danger-700">
            {error}
          </p>
        )}
      </DialogBody>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={pending || name.trim() === "" || !accentValid}
          onClick={save}
        >
          {widgetKey ? "Save changes" : "Create embed"}
        </Button>
      </DialogFooter>
    </>
  );
}

/** The Settings → Widget section action. */
export function NewWidgetKeyButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="primary" size="sm" onClick={() => setOpen(true)}>
        <Plus />
        New embed
      </Button>
      <WidgetKeyDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
