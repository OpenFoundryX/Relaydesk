"use client";

import { useState, useTransition } from "react";
import { Trash2 } from "lucide-react";

import { revokeApiKeyAction } from "@/app/(console)/settings/api-keys/actions";
import { Button } from "@/components/ui/button";
import type { ApiKey } from "@/lib/types";

/** Revoke control on a Settings → API keys row. Revoking is immediate and
 * cannot be undone: the key's row survives so its past actions still have a
 * name, but the secret stops resolving on the next request. */
export function ApiKeyActions({ apiKey }: { apiKey: ApiKey }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function revoke() {
    setError(null);
    startTransition(async () => {
      const result = await revokeApiKeyAction(apiKey.id);
      if (!result.ok) setError(result.message);
    });
  }

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Revoke ${apiKey.name}`}
        disabled={pending}
        onClick={revoke}
      >
        <Trash2 className="size-3.5" />
      </Button>
      {error && (
        <p role="alert" className="text-[11px] text-danger-700">
          {error}
        </p>
      )}
    </div>
  );
}
