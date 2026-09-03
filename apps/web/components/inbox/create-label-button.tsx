"use client";

import { Plus } from "lucide-react";
import { useState, useTransition } from "react";

import { createLabelAction } from "@/app/(console)/conversations/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/** The "+" beside the sidebar's Labels heading. */
export function CreateLabelButton() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [pending, start] = useTransition();

  const submit = () => {
    if (!name.trim()) return;
    start(async () => {
      await createLabelAction(name);
      setName("");
      setOpen(false);
    });
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Create label"
          title="Create label"
          className="rounded text-ink-400 transition-colors hover:text-ink-900"
        >
          <Plus className="size-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-3">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
          className="space-y-2"
        >
          <p className="text-[12px] font-medium text-ink-700">New label</p>
          <Input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Enterprise"
            aria-label="Label name"
          />
          <Button type="submit" size="sm" variant="primary" className="w-full" disabled={pending || !name.trim()}>
            Create label
          </Button>
        </form>
      </PopoverContent>
    </Popover>
  );
}
