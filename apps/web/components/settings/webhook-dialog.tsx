"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Textarea } from "@/components/ui/textarea";

interface DraftParam {
  name: string;
  type: string;
  description: string;
  required: boolean;
}

const emptyParam: DraftParam = {
  name: "",
  type: "string",
  description: "",
  required: true,
};

export function WebhookDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [params, setParams] = useState<DraftParam[]>([emptyParam]);

  function updateParam(index: number, patch: Partial<DraftParam>) {
    setParams((current) =>
      current.map((param, i) => (i === index ? { ...param, ...patch } : param)),
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Plus />
          New webhook
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New webhook</DialogTitle>
          <DialogDescription>
            The agent calls this endpoint as a tool. Every request is signed with
            your webhook secret so you can verify it came from us.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="space-y-1.5">
            <Label htmlFor="wh-name">Name</Label>
            <Input
              id="wh-name"
              placeholder="refund_order"
              className="font-mono"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="wh-description">Description</Label>
            <Textarea
              id="wh-description"
              placeholder="Refunds an order by its order_id."
              className="min-h-16"
            />
            <p className="text-[12px] text-ink-500">
              The agent reads this to decide when to call the tool. Be specific.
            </p>
          </div>

          <div className="flex gap-2">
            <div className="w-28 space-y-1.5">
              <Label htmlFor="wh-method">Method</Label>
              <Select defaultValue="POST">
                <SelectTrigger id="wh-method">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["GET", "POST", "PUT", "PATCH", "DELETE"].map((method) => (
                    <SelectItem key={method} value={method}>
                      {method}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="wh-url">Endpoint URL</Label>
              <Input
                id="wh-url"
                placeholder="https://api.example.com/relaydesk/refund"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Parameters</Label>
            {params.map((param, index) => (
              <div
                key={index}
                className="space-y-2 rounded-md border border-ink-200 p-2.5"
              >
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="Name"
                    className="font-mono"
                    value={param.name}
                    onChange={(event) =>
                      updateParam(index, { name: event.target.value })
                    }
                  />
                  <Select
                    value={param.type}
                    onValueChange={(type) => updateParam(index, { type })}
                  >
                    <SelectTrigger className="w-28" aria-label="Parameter type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="string">string</SelectItem>
                      <SelectItem value="number">number</SelectItem>
                      <SelectItem value="boolean">boolean</SelectItem>
                    </SelectContent>
                  </Select>
                  <label className="flex shrink-0 items-center gap-1.5 text-[12px] text-ink-600">
                    <Checkbox
                      checked={param.required}
                      onCheckedChange={(checked) =>
                        updateParam(index, { required: checked === true })
                      }
                    />
                    required
                  </label>
                  <button
                    type="button"
                    aria-label="Remove parameter"
                    onClick={() =>
                      setParams((current) =>
                        current.filter((_, i) => i !== index),
                      )
                    }
                    className="rounded p-1 text-ink-400 transition-colors hover:text-danger-600"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
                <Input
                  placeholder="Description"
                  value={param.description}
                  onChange={(event) =>
                    updateParam(index, { description: event.target.value })
                  }
                />
              </div>
            ))}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setParams((current) => [...current, emptyParam])}
            >
              <Plus />
              Add parameter
            </Button>
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
            Create webhook
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
