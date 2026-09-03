"use client";

import { useState } from "react";
import { Link2 } from "lucide-react";

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
import { sourceModes } from "@/lib/mock/knowledge-base";

export function SourceDialog() {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("manual");
  const [url, setUrl] = useState("");

  const needsUrl = mode === "url";
  const canContinue = !needsUrl || url.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          <Link2 />
          Source: {sourceModes.find((entry) => entry.id === mode)?.label}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Article source</DialogTitle>
          <DialogDescription>
            Choose where the articles in this knowledge base come from.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="space-y-1.5">
            <Label htmlFor="source-mode">Source</Label>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger id="source-mode">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {sourceModes.map((entry) => (
                  <SelectItem key={entry.id} value={entry.id}>
                    {entry.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {needsUrl && (
            <div className="space-y-1.5">
              <Label htmlFor="root-url">Root URL</Label>
              <Input
                id="root-url"
                placeholder="https://example.com/help-center"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
              />
              <p className="text-[12px] text-ink-500">
                We crawl every page under this path and re-sync it nightly.
              </p>
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={!canContinue}
            onClick={() => setOpen(false)}
          >
            Continue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
