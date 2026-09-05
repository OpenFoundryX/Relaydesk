"use client";

import { useState, useTransition } from "react";
import { Check, Copy, Trash2 } from "lucide-react";

import { deleteEmailChannelAction } from "@/app/(console)/settings/channels/actions";
import { Button } from "@/components/ui/button";
import type { ChannelAccount } from "@/lib/types";

/** Copy-to-clipboard and remove controls on a Settings → Channels row. The
 * remove control is hidden for a non-admin -- see ChannelsPage -- but a 403
 * from a stale client still surfaces as a message rather than an error
 * boundary. */
export function EmailChannelActions({
  channel,
  canRemove,
}: {
  channel: ChannelAccount;
  canRemove: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  async function copy() {
    try {
      await navigator.clipboard.writeText(channel.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked; the address is still selectable in the row.
    }
  }

  function remove() {
    setError(null);
    startTransition(async () => {
      const result = await deleteEmailChannelAction(channel.id);
      if (!result.ok) setError(result.message);
    });
  }

  return (
    <div className="ml-auto flex shrink-0 flex-col items-end gap-1">
      <div className="flex items-center gap-1">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Copy ${channel.address}`}
          onClick={copy}
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        </Button>
        {canRemove && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Remove ${channel.address}`}
            disabled={pending}
            onClick={remove}
          >
            <Trash2 className="size-3.5" />
          </Button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-[11px] text-danger-700">
          {error}
        </p>
      )}
    </div>
  );
}
