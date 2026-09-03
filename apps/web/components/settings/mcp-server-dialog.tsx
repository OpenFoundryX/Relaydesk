"use client";

import { useState } from "react";
import { ChevronDown, Plus } from "lucide-react";

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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export function McpServerDialog() {
  const [open, setOpen] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [active, setActive] = useState(true);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Plus />
          New server
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New MCP server</DialogTitle>
          <DialogDescription>
            Every tool the server exposes becomes available to your agent.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="space-y-1.5">
            <Label htmlFor="mcp-name">Name</Label>
            <Input
              id="mcp-name"
              placeholder="Support MCP server"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="mcp-description">Description</Label>
            <Input
              id="mcp-description"
              placeholder="Customer lookup and account tools"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="mcp-url">URL</Label>
            <Input
              id="mcp-url"
              placeholder="https://mcp.example.com/mcp"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
            />
          </div>

          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced((current) => !current)}
              className="flex items-center gap-1 rounded text-[13px] font-medium text-ink-600 transition-colors hover:text-ink-900"
            >
              Advanced
              <ChevronDown
                className={cn(
                  "size-3.5 transition-transform",
                  showAdvanced && "rotate-180",
                )}
              />
            </button>
            {showAdvanced && (
              <div className="mt-2 space-y-1.5">
                <Label htmlFor="mcp-headers">Request headers</Label>
                <Textarea
                  id="mcp-headers"
                  placeholder={'{\n  "Authorization": "Bearer …"\n}'}
                  className="min-h-20 font-mono text-[12px]"
                />
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 border-t border-ink-200 pt-4">
            <Switch
              checked={active}
              onCheckedChange={setActive}
              id="mcp-active"
              aria-label="Server active"
            />
            <Label htmlFor="mcp-active">Active</Label>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={name.trim() === "" || url.trim() === ""}
            onClick={() => setOpen(false)}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
