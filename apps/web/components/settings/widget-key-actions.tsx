"use client";

import { useState, useTransition } from "react";
import { Pencil, Trash2 } from "lucide-react";

import {
  deleteWidgetKeyAction,
  updateWidgetKeyAction,
} from "@/app/(console)/settings/widget/actions";
import { WidgetKeyDialog } from "@/components/settings/widget-key-dialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { WidgetKey } from "@/lib/api/widget-keys";

/**
 * Active toggle, edit and delete on a Settings → Widget row.
 *
 * Deleting confirms in place, like `WebhookActions`: an embed backs a
 * `<script>` tag already live on a customer's real site, so removing it is
 * not the low-stakes edit a snippet's delete is.
 */
export function WidgetKeyActions({ widgetKey }: { widgetKey: WidgetKey }) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function toggleActive(next: boolean) {
    setError(null);
    start(async () => {
      const result = await updateWidgetKeyAction(widgetKey.id, { active: next });
      if (!result.ok) setError(result.message);
    });
  }

  function remove() {
    setError(null);
    start(async () => {
      const result = await deleteWidgetKeyAction(widgetKey.id);
      if (!result.ok) setError(result.message);
      // On success the section is gone with the next render; nothing to reset.
    });
  }

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <Switch
          checked={widgetKey.active}
          disabled={pending}
          aria-label={`${widgetKey.active ? "Deactivate" : "Activate"} ${widgetKey.name}`}
          onCheckedChange={toggleActive}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Edit ${widgetKey.name}`}
          onClick={() => setEditing(true)}
        >
          <Pencil className="size-3.5" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Delete ${widgetKey.name}`}
          disabled={pending}
          onClick={() => setConfirming((current) => !current)}
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>

      {confirming && (
        <div className="mt-1 flex items-center gap-2 rounded-md border border-danger-200 bg-danger-50 p-2 text-[12px] text-ink-700">
          <p>
            Delete <span className="font-mono">{widgetKey.name}</span>? Its script
            tag stops working immediately.
          </p>
          <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
          <Button variant="danger" size="sm" disabled={pending} onClick={remove}>
            Delete
          </Button>
        </div>
      )}

      {error && (
        <p role="alert" className="text-[11px] text-danger-700">
          {error}
        </p>
      )}

      <WidgetKeyDialog widgetKey={widgetKey} open={editing} onOpenChange={setEditing} />
    </div>
  );
}
