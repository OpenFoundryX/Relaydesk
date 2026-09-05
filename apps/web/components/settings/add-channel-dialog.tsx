"use client";

import { useState, useTransition } from "react";
import { Mail } from "lucide-react";

import { createEmailChannelAction } from "@/app/(console)/settings/channels/actions";
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

/** The "Add address" trigger on Settings → Channels. */
export function AddChannelDialog() {
  const [open, setOpen] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [pending, startTransition] = useTransition();

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) setDisplayName("");
  }

  function submit() {
    startTransition(async () => {
      await createEmailChannelAction(displayName);
      handleOpenChange(false);
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Mail />
          Add address
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add an email address</DialogTitle>
          <DialogDescription>
            Relaydesk mints a dedicated inbound address. Give it a name so your team can tell
            addresses apart.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="space-y-1.5">
            <Label htmlFor="channel-name">Name</Label>
            <Input
              id="channel-name"
              placeholder="Support"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoFocus
            />
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending} onClick={submit}>
            {pending ? "Adding…" : "Add address"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
