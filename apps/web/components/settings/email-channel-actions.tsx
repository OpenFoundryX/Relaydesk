"use client";

import { useState, useTransition } from "react";
import { Check, Copy, Trash2 } from "lucide-react";

import { deleteEmailChannelAction } from "@/app/(console)/settings/channels/actions";
import { Button } from "@/components/ui/button";
import type { ChannelAccount } from "@/lib/types";

/** Copy-to-clipboard and remove controls on a Settings → Channels row. */
export function EmailChannelActions({ channel }: { channel: ChannelAccount }) {
  const [copied, setCopied] = useState(false);
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

  return (
    <div className="ml-auto flex shrink-0 items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Copy ${channel.address}`}
        onClick={copy}
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Remove ${channel.address}`}
        disabled={pending}
        onClick={() => startTransition(async () => deleteEmailChannelAction(channel.id))}
      >
        <Trash2 className="size-3.5" />
      </Button>
    </div>
  );
}
