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
import type { WidgetKey } from "@/lib/api/widget-keys";

function parseOrigins(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "");
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
      <DialogContent className="max-w-lg">
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
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function save() {
    setError(null);
    start(async () => {
      const input = { name: name.trim(), allowedOrigins: parseOrigins(origins) };
      const result = widgetKey
        ? await updateWidgetKeyAction(widgetKey.id, input)
        : await createWidgetKeyAction(input);
      // A 422 (a value that isn't a URL) is the failure an admin is most
      // likely to hit here, so it keeps the dialog open with what was typed.
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
        <Button variant="primary" disabled={pending || name.trim() === ""} onClick={save}>
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
