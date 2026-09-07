"use client";

import { useState, useTransition } from "react";
import { Check, Copy, Plus } from "lucide-react";

import { createApiKeyAction } from "@/app/(console)/settings/api-keys/actions";
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
import type { ApiKeyScope } from "@/lib/types";

/**
 * Presets, not a checkbox grid, as the default path.
 *
 * "Ticket bot" deliberately stops short of messages:write. Creating and
 * triaging tickets is a different blast radius from mailing a customer
 * under the workspace's name, and a preset that quietly bundled the two
 * would undo the reason the scopes are separate at all.
 */
const PRESETS: { id: string; label: string; hint: string; scopes: ApiKeyScope[] }[] = [
  {
    id: "read-only",
    label: "Read-only",
    hint: "Reporting and sync. Cannot change anything.",
    scopes: ["conversations:read", "contacts:read", "labels:read"],
  },
  {
    id: "ticket-bot",
    label: "Ticket bot",
    hint: "Creates and triages tickets. Cannot reply to customers.",
    scopes: [
      "conversations:read",
      "conversations:write",
      "contacts:read",
      "labels:read",
      "labels:write",
    ],
  },
  {
    id: "full",
    label: "Full access",
    hint: "Everything, including replying to customers by email.",
    scopes: [
      "conversations:read",
      "conversations:write",
      "messages:write",
      "contacts:read",
      "labels:read",
      "labels:write",
    ],
  },
];

export function ApiKeyDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [preset, setPreset] = useState(PRESETS[1].id);
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, startTransition] = useTransition();

  function reset() {
    setName("");
    setPreset(PRESETS[1].id);
    setToken(null);
    setError(null);
    setCopied(false);
  }

  function create() {
    setError(null);
    const scopes = PRESETS.find((entry) => entry.id === preset)!.scopes;
    startTransition(async () => {
      const result = await createApiKeyAction(name.trim(), scopes);
      if (result.ok) setToken(result.token);
      else setError(result.message);
    });
  }

  async function copy() {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked; the token is still selectable below.
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Plus />
          Create API key
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{token ? "Copy your key" : "Create API key"}</DialogTitle>
          <DialogDescription>
            {token
              ? "This is the only time it is shown. Store it somewhere safe before closing."
              : "The key is shown once, immediately after it is created."}
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          {token ? (
            <div className="space-y-2">
              <pre className="overflow-x-auto rounded-md border border-ink-200 bg-ink-950 p-3 font-mono text-[12px] text-ink-100">
                <code>{token}</code>
              </pre>
              <button
                type="button"
                onClick={copy}
                className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
              >
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="key-name">Name</Label>
                <Input
                  id="key-name"
                  placeholder="Production ingest"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoFocus
                />
              </div>
              <fieldset className="space-y-1.5">
                <legend className="text-[13px] font-medium text-ink-900">
                  Access
                </legend>
                {PRESETS.map((entry) => (
                  <label
                    key={entry.id}
                    className="flex cursor-pointer items-start gap-2 rounded-md border border-ink-200 p-2.5"
                  >
                    <input
                      type="radio"
                      name="preset"
                      className="mt-0.5"
                      value={entry.id}
                      checked={preset === entry.id}
                      onChange={() => setPreset(entry.id)}
                    />
                    <span className="min-w-0">
                      <span className="block text-[13px] font-medium text-ink-900">
                        {entry.label}
                      </span>
                      <span className="block text-[12px] text-ink-500">
                        {entry.hint}
                      </span>
                    </span>
                  </label>
                ))}
              </fieldset>
              {error && (
                <p role="alert" className="text-[12px] text-danger-700">
                  {error}
                </p>
              )}
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          {token ? (
            <Button variant="primary" onClick={() => setOpen(false)}>
              Done
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={name.trim() === "" || pending}
                onClick={create}
              >
                Create key
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
