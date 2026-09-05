"use client";

import { useState } from "react";
import { Link2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
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

/**
 * Importing articles from an existing help centre is not built.
 *
 * Rather than offer a Continue button that quietly does nothing, the dialog
 * says so and its primary action is disabled -- the same shape the
 * one-click import sources on settings/channels use for the providers that
 * have not shipped. Articles are written in the console today; that is the
 * only source there is.
 */
export function SourceDialog() {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          <Link2 />
          Source: Written here
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Article source
            <Badge variant="outline">Coming soon</Badge>
          </DialogTitle>
          <DialogDescription>
            Every article in this knowledge base is written here, in the console.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="space-y-1.5">
            <Label htmlFor="root-url">Sync from a URL</Label>
            <Input
              id="root-url"
              placeholder="https://example.com/help-center"
              defaultValue=""
              disabled
            />
            <p className="text-[12px] text-ink-500">
              Crawling an existing help centre and re-syncing it nightly is coming in
              a later release. Until then, write your articles here.
            </p>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Close
          </Button>
          <Button variant="primary" disabled>
            Sync
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
