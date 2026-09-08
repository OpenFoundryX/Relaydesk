"use client";

import { useState, useTransition } from "react";
import { Check, Copy, KeyRound, Play, Trash2 } from "lucide-react";

import {
  deleteWebhookAction,
  rotateWebhookSecretAction,
  testWebhookAction,
} from "@/app/(console)/settings/custom-webhooks/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Webhook, WebhookTestResult } from "@/lib/types";

type Panel = "test" | "secret" | "delete" | null;

/**
 * Test, rotate and delete on a Settings → Custom webhooks row.
 *
 * Deleting confirms in place rather than through `window.confirm`, which
 * blocks the page and cannot be styled.
 */
export function WebhookActions({ webhook }: { webhook: Webhook }) {
  const [panel, setPanel] = useState<Panel>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<WebhookTestResult | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function show(next: Panel) {
    setPanel((current) => (current === next ? null : next));
    setError(null);
    setResult(null);
    setSecret(null);
  }

  function send() {
    setError(null);
    startTransition(async () => {
      const outcome = await testWebhookAction(webhook.id, values);
      if (outcome.ok) setResult(outcome.result);
      // A 422 (a missing or uncoercible argument) means nothing was sent, so
      // it is shown as our error rather than as a failed call.
      else setError(outcome.message);
    });
  }

  function rotate() {
    setError(null);
    startTransition(async () => {
      const outcome = await rotateWebhookSecretAction(webhook.id);
      if (outcome.ok) {
        setSecret(outcome.secret);
        setPanel("secret");
      } else setError(outcome.message);
    });
  }

  function remove() {
    setError(null);
    startTransition(async () => {
      const outcome = await deleteWebhookAction(webhook.id);
      if (!outcome.ok) setError(outcome.message);
      // On success the row is gone with the next render; nothing to reset.
    });
  }

  async function copy() {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked; the secret is still selectable.
    }
  }

  return (
    <div className="mt-2">
      <div className="flex items-center gap-1">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={pending}
          onClick={() => show("test")}
        >
          <Play className="size-3.5" />
          Test
        </Button>
        <Button type="button" variant="ghost" size="sm" disabled={pending} onClick={rotate}>
          <KeyRound className="size-3.5" />
          Rotate secret
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={pending}
          aria-label={`Delete ${webhook.name}`}
          onClick={() => show("delete")}
        >
          <Trash2 className="size-3.5" />
          Delete
        </Button>
      </div>

      {panel === "test" && (
        <div className="mt-2 space-y-2 rounded-md border border-ink-200 bg-ink-50 p-2.5">
          {webhook.params.map((param) => (
            <div key={param.name} className="space-y-1">
              <Label htmlFor={`${webhook.id}-${param.name}`} className="font-mono">
                {param.name}
                <span className="text-ink-400">:{param.type}</span>
                {param.required && <span className="text-accent-800">*</span>}
              </Label>
              <Input
                id={`${webhook.id}-${param.name}`}
                value={values[param.name] ?? ""}
                onChange={(event) =>
                  setValues((current) => ({
                    ...current,
                    [param.name]: event.target.value,
                  }))
                }
              />
            </div>
          ))}
          <Button variant="primary" size="sm" disabled={pending} onClick={send}>
            {pending ? "Sending…" : "Send test request"}
          </Button>

          {result && (
            <div className="space-y-1 border-t border-ink-200 pt-2">
              <p className="text-[12px] text-ink-600">
                <span
                  className={
                    result.ok
                      ? "font-medium text-positive-600"
                      : "font-medium text-danger-700"
                  }
                >
                  {result.status ?? "No response"}
                </span>{" "}
                in {result.durationMs}ms
              </p>
              {result.error && (
                <p className="text-[12px] text-danger-700">{result.error}</p>
              )}
              {result.responseBody && (
                <pre className="max-h-40 overflow-auto rounded border border-ink-200 bg-ink-950 p-2 font-mono text-[11px] text-ink-100">
                  <code>{result.responseBody}</code>
                </pre>
              )}
            </div>
          )}
        </div>
      )}

      {panel === "secret" && secret && (
        <div className="mt-2 space-y-2 rounded-md border border-ink-200 bg-ink-50 p-2.5">
          <p className="text-[12px] text-ink-600">
            The old secret stopped working the moment this one was made. Update your
            receiver before the next call.
          </p>
          <pre className="overflow-x-auto rounded border border-ink-200 bg-ink-950 p-2 font-mono text-[12px] text-ink-100">
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
        </div>
      )}

      {panel === "delete" && (
        <div className="mt-2 flex items-center gap-2 rounded-md border border-danger-200 bg-danger-50 p-2.5">
          <p className="text-[12px] text-ink-700">
            Delete <span className="font-mono">{webhook.name}</span>? Anything calling
            it stops working.
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => setPanel(null)}
          >
            Cancel
          </Button>
          <Button variant="danger" size="sm" disabled={pending} onClick={remove}>
            Delete
          </Button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-1 text-[12px] text-danger-700">
          {error}
        </p>
      )}
    </div>
  );
}
