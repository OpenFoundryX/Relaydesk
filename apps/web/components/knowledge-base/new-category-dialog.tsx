"use client";

import { useState, useTransition } from "react";
import { FolderPlus } from "lucide-react";

import { createCategoryAction } from "@/app/(console)/knowledge-base/actions";
import {
  CategoryFields,
  EMPTY_FACE,
  type CategoryFace,
} from "@/components/knowledge-base/category-fields";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { KbScope } from "@/lib/types";

/**
 * Creating a category is admin-only in the API, so the page hides this
 * trigger for an agent entirely -- see KnowledgeBasePage. The error line
 * still handles a 403, along with the two reserved names ("images" and
 * "search", which collide with routes on the public help site) the API
 * refuses whoever asks.
 */
export function NewCategoryDialog({
  scope,
  triggerLabel,
  variant = "primary",
  parentId = null,
}: {
  scope: KbScope;
  triggerLabel: string;
  variant?: "primary" | "secondary";
  /** Set to create this one *inside* an existing collection. */
  parentId?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [face, setFace] = useState<CategoryFace>(EMPTY_FACE);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      setFace(EMPTY_FACE);
      setError(null);
    }
  }

  function submit() {
    setError(null);
    startTransition(async () => {
      const result = await createCategoryAction(face.name.trim(), scope, {
        parentId,
        description: face.description.trim(),
        icon: face.icon,
      });
      if (result.ok) {
        handleOpenChange(false);
      } else {
        setError(result.message);
      }
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant={variant} size="sm">
          <FolderPlus />
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{triggerLabel}</DialogTitle>
        </DialogHeader>
        <DialogBody>
          {error && (
            <p
              role="alert"
              className="rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
            >
              {error}
            </p>
          )}
          <CategoryFields value={face} onChange={setFace} idPrefix="new-category" />
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={pending || face.name.trim().length === 0}
            onClick={submit}
          >
            {pending ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
