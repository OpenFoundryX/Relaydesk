"use client";

import { useState, useTransition } from "react";
import { Pencil, Trash2 } from "lucide-react";

import { deleteSnippetAction } from "@/app/(console)/settings/templates/actions";
import { SnippetDialog } from "@/components/settings/snippet-dialog";
import { Button } from "@/components/ui/button";
import type { Snippet } from "@/lib/types";

/**
 * Edit and delete controls on a Settings → Templates row.
 *
 * Deleting is not confirmed: a snippet is a convenience, not a record —
 * nothing already sent changes, and rewriting it costs a moment. Compare
 * `ApiKeyActions`, which is equally immediate for the opposite reason.
 */
export function SnippetActions({ snippet }: { snippet: Snippet }) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function remove() {
    setError(null);
    start(async () => {
      const result = await deleteSnippetAction(snippet.id);
      if (!result.ok) setError(result.message);
    });
  }

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <div className="flex items-center">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Edit ${snippet.title}`}
          onClick={() => setEditing(true)}
        >
          <Pencil className="size-3.5" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Delete ${snippet.title}`}
          disabled={pending}
          onClick={remove}
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-[11px] text-danger-700">
          {error}
        </p>
      )}
      <SnippetDialog snippet={snippet} open={editing} onOpenChange={setEditing} />
    </div>
  );
}
