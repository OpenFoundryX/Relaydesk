"use client";

import { useState, useTransition } from "react";
import { FilePlus } from "lucide-react";

import { createArticleAction } from "@/app/(console)/knowledge-base/actions";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { KbCategory } from "@/lib/types";

/**
 * An article always belongs to a category, so this asks for one up front
 * rather than creating something homeless. On success the action redirects
 * into the new article and this dialog never sees a result -- an empty body
 * is where you start writing, not something to confirm.
 */
export function NewArticleDialog({ categories }: { categories: KbCategory[] }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [categoryId, setCategoryId] = useState(categories[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      setTitle("");
      setError(null);
    }
  }

  function submit() {
    setError(null);
    startTransition(async () => {
      // A successful create redirects, and resolves with nothing.
      const result = await createArticleAction(categoryId, title.trim());
      if (result) setError(result.message);
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <FilePlus />
          New article
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New article</DialogTitle>
          <DialogDescription>
            It starts as a draft. Nobody outside your workspace sees it until you
            publish it.
          </DialogDescription>
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
          <div className="space-y-1.5">
            <Label htmlFor="article-title-new">Title</Label>
            <Input
              id="article-title-new"
              placeholder="e.g. Handling a refund request"
              value={title}
              maxLength={200}
              onChange={(event) => setTitle(event.target.value)}
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="article-category">Category</Label>
            <Select value={categoryId} onValueChange={setCategoryId}>
              <SelectTrigger id="article-category">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {categories.map((category) => (
                  <SelectItem key={category.id} value={category.id}>
                    {category.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={pending || title.trim().length === 0 || categoryId === ""}
            onClick={submit}
          >
            {pending ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
