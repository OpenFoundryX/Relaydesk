"use client";

import { useState, useTransition } from "react";
import { Check, Copy, Plus, Trash2 } from "lucide-react";

import { createWebhookAction } from "@/app/(console)/settings/custom-webhooks/actions";
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
import type { HttpMethod, WebhookParam } from "@/lib/types";

const METHODS: HttpMethod[] = ["GET", "POST", "PUT", "PATCH", "DELETE"];

function newParam(): WebhookParam {
  return { name: "", type: "string", description: "", required: true };
}

export function WebhookDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [method, setMethod] = useState<HttpMethod>("POST");
  const [url, setUrl] = useState("");
  const [params, setParams] = useState<WebhookParam[]>([newParam()]);
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, startTransition] = useTransition();

  function updateParam(index: number, patch: Partial<WebhookParam>) {
    setParams((current) =>
      current.map((param, i) => (i === index ? { ...param, ...patch } : param)),
    );
  }

  /**
   * The one place that knows what closing means.
   *
   * This component never unmounts, so a bare `setOpen(false)` would leave the
   * secret sitting in state until the next open. Route every close through
   * here. Compare `api-key-dialog.tsx`, which does the same for its token.
   */
  function close() {
    setOpen(false);
    setName("");
    setDescription("");
    setMethod("POST");
    setUrl("");
    setParams([newParam()]);
    setSecret(null);
    setError(null);
    setCopied(false);
  }

  function create() {
    setError(null);
    startTransition(async () => {
      const result = await createWebhookAction({
        name: name.trim(),
        description: description.trim(),
        method,
        url: url.trim(),
        // A row the admin added and never filled in is not a parameter.
        params: params.filter((param) => param.name.trim() !== ""),
      });
      if (result.ok) setSecret(result.secret);
      else setError(result.message);
    });
  }

  async function copy() {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked; the secret is still selectable below.
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) close();
        else setOpen(next);
      }}
    >
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Plus />
          New webhook
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{secret ? "Copy your signing secret" : "New webhook"}</DialogTitle>
          <DialogDescription>
            {secret
              ? "Verify every request against this secret. You can rotate it later if it leaks."
              : "The agent calls this endpoint as a tool. Every request is signed with your webhook secret so you can verify it came from us."}
          </DialogDescription>
        </DialogHeader>

        {secret ? (
          <DialogBody>
            <div className="space-y-2">
              <pre className="overflow-x-auto rounded-md border border-ink-200 bg-ink-950 p-3 font-mono text-[12px] text-ink-100">
                <code>{secret}</code>
              </pre>
              <button
                type="button"
                onClick={copy}
                className="flex items-center gap-1.5 text-[12px] text-ink-600 transition-colors hover:text-ink-900"
              >
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                {copied ? "Copied" : "Copy secret"}
              </button>
              <p className="text-[12px] text-ink-500">
                We sign{" "}
                <code className="font-mono text-[11px]">
                  {"{timestamp}.{method}.{url}.{body}"}
                </code>{" "}
                with HMAC-SHA256 and send it as the{" "}
                <code className="font-mono text-[11px]">Relaydesk-Signature</code>{" "}
                header. Reject requests whose timestamp is far from your clock —
                that is what stops a captured request being replayed.
              </p>
            </div>
          </DialogBody>
        ) : (
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
              <p className="text-[12px] text-ink-500">
                Lowercase letters, digits and underscores. This is how the tool is
                named when it is called.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="wh-description">Description</Label>
              <Textarea
                id="wh-description"
                placeholder="Refunds an order by its order_id."
                className="min-h-16"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
              <p className="text-[12px] text-ink-500">
                The agent reads this to decide when to call the tool. Be specific.
              </p>
            </div>

            <div className="flex gap-2">
              <div className="w-28 space-y-1.5">
                <Label htmlFor="wh-method">Method</Label>
                <Select
                  value={method}
                  onValueChange={(next) => setMethod(next as HttpMethod)}
                >
                  <SelectTrigger id="wh-method">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {METHODS.map((entry) => (
                      <SelectItem key={entry} value={entry}>
                        {entry}
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
                      onValueChange={(type) =>
                        updateParam(index, { type: type as WebhookParam["type"] })
                      }
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
                        setParams((current) => current.filter((_, i) => i !== index))
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
                onClick={() => setParams((current) => [...current, newParam()])}
              >
                <Plus />
                Add parameter
              </Button>
            </div>

            {error && (
              <p role="alert" className="text-[12px] text-danger-700">
                {error}
              </p>
            )}
          </DialogBody>
        )}

        <DialogFooter>
          {secret ? (
            <Button variant="primary" onClick={close}>
              Done
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={close}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={
                  pending ||
                  name.trim() === "" ||
                  url.trim() === "" ||
                  description.trim() === ""
                }
                onClick={create}
              >
                {pending ? "Creating…" : "Create webhook"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
