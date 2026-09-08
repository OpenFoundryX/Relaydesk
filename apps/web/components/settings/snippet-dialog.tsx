"use client";

import { useState, useTransition } from "react";
import { ChevronDown, Plus } from "lucide-react";

import {
  createSnippetAction,
  updateSnippetAction,
} from "@/app/(console)/settings/templates/actions";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { SNIPPET_VARIABLES } from "@/lib/snippets/render";
import type { Snippet } from "@/lib/types";

/**
 * Write a snippet, or edit one.
 *
 * Controlled by whoever opens it: `NewSnippetButton` below for a new one,
 * `SnippetActions` for an existing one. The two modes differ only in which
 * action they submit to, so the form is written once.
 */
export function SnippetDialog({
  snippet,
  open,
  onOpenChange,
}: {
  snippet?: Snippet;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{snippet ? "Edit snippet" : "Create snippet"}</DialogTitle>
          <DialogDescription>
            Type / in the message editor to drop a snippet into a reply.
          </DialogDescription>
        </DialogHeader>
        {/* The form's state lives below this line, and Radix unmounts the
            content when the dialog closes -- so reopening is a fresh start
            with no effect to reset anything. A create dialog dismissed
            halfway does not come back holding the last attempt, and an edit
            dialog shows what the row says now. */}
        <SnippetForm snippet={snippet} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function SnippetForm({
  snippet,
  onClose,
}: {
  snippet?: Snippet;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(snippet?.title ?? "");
  const [content, setContent] = useState(snippet?.content ?? "");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function save() {
    setError(null);
    start(async () => {
      const result = snippet
        ? await updateSnippetAction(snippet.id, title.trim(), content)
        : await createSnippetAction(title.trim(), content);
      // A refusal keeps the dialog open with what was typed still in it --
      // a duplicate title is a 409, and it is the failure an author is
      // most likely to hit.
      if (result.ok) onClose();
      else setError(result.message);
    });
  }

  return (
    <>
      <DialogBody>
        <div className="space-y-1.5">
          <Label htmlFor="snippet-title">Title</Label>
          <Input
            id="snippet-title"
            placeholder="Generic reply"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            autoFocus
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="snippet-content">Content</Label>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" size="sm">
                  Variables
                  <ChevronDown />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {SNIPPET_VARIABLES.map((variable) => (
                  <DropdownMenuItem
                    key={variable}
                    onSelect={() => setContent((current) => `${current}${variable}`)}
                    className="font-mono"
                  >
                    {variable}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <Textarea
            id="snippet-content"
            placeholder="Hi, thanks for your message. We'll come back to you shortly."
            className="min-h-32"
            value={content}
            onChange={(event) => setContent(event.target.value)}
          />
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
        <Button
          variant="primary"
          disabled={pending || title.trim() === "" || content.trim() === ""}
          onClick={save}
        >
          Save snippet
        </Button>
      </DialogFooter>
    </>
  );
}

/** The Settings → Templates section action. */
export function NewSnippetButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="primary" size="sm" onClick={() => setOpen(true)}>
        <Plus />
        Create snippet
      </Button>
      <SnippetDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
