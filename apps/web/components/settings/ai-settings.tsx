"use client";

import { useState, useTransition } from "react";

import { SettingSection } from "@/components/console/setting-section";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { AiConfig } from "@/lib/api/ai-config";

/**
 * Settings → AI answers: the only place a workspace can ever turn this on
 * (Task 9). Everything else in the slice -- redaction, retrieval, the
 * provider call, the budget, the public `/widget/{key}/ask` route -- sits
 * behind `enabled`, which starts `false` and an `api_key` which starts
 * unset, so until an admin visits this screen every answer degrades to
 * today's widget.
 *
 * Follows `widget-keys.tsx` for house style (a `SettingSection` per
 * concern), but unlike that component this one owns its own save: there is
 * no console-managed list to render rows for, just one row per workspace.
 *
 * The key field never carries the installed value -- `AiConfig` has no
 * `apiKey`, only `keySuffix` (Task 1's write-only design) -- so the input
 * here always starts blank. Typing into it stages a *replacement*; leaving
 * it blank and saving other fields leaves the installed key untouched,
 * mirroring what `AiConfigIn.api_key` does server-side.
 */
export function AiSettings({ config }: { config: AiConfig }) {
  const [provider, setProvider] = useState(config.provider);
  const [model, setModel] = useState(config.model);
  const [baseUrl, setBaseUrl] = useState(config.baseUrl ?? "");
  const [dailyTokenBudget, setDailyTokenBudget] = useState(
    String(config.dailyTokenBudget),
  );
  const [enabled, setEnabled] = useState(config.enabled);
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startSave] = useTransition();

  const changed =
    provider !== config.provider ||
    model !== config.model ||
    baseUrl !== (config.baseUrl ?? "") ||
    dailyTokenBudget !== String(config.dailyTokenBudget) ||
    enabled !== config.enabled ||
    apiKey !== "";

  function save() {
    setError(null);
    startSave(async () => {
      // Loaded lazily rather than imported at module scope: the actions
      // module is "use server" and pulls in server-only code that plain
      // Vitest cannot resolve, the same reason `widget-key-dialog.tsx`
      // keeps `WidgetKeys` free of it (see that file's docstring). A
      // dynamic import defers evaluation to the moment a save actually
      // happens, so a render-only test never touches it.
      const { updateAiConfigAction } = await import(
        "@/app/(console)/settings/ai/actions"
      );
      const budget = Number(dailyTokenBudget);
      const result = await updateAiConfigAction({
        provider,
        model,
        baseUrl,
        dailyTokenBudget: Number.isFinite(budget) ? budget : config.dailyTokenBudget,
        enabled,
        ...(apiKey !== "" ? { apiKey } : {}),
      });
      if (!result.ok) {
        setError(result.message);
        return;
      }
      setApiKey("");
    });
  }

  function toggleEnabled(next: boolean) {
    setEnabled(next);
    setError(null);
    startSave(async () => {
      const { updateAiConfigAction } = await import(
        "@/app/(console)/settings/ai/actions"
      );
      const result = await updateAiConfigAction({ enabled: next });
      if (!result.ok) {
        setEnabled(!next);
        setError(result.message);
      }
    });
  }

  return (
    <div className="space-y-4">
      <SettingSection
        title="AI answers"
        description="When on, the widget tries to answer a visitor's question itself before a human ever sees it. When off, the widget keeps working exactly as it does today -- visitors still get search and the message form, never an error."
        action={
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-ink-500">{enabled ? "On" : "Off"}</span>
            <Switch
              checked={enabled}
              onCheckedChange={toggleEnabled}
              disabled={pending}
              aria-label="AI answers"
            />
          </div>
        }
      />

      <SettingSection
        title="Model"
        description="Which provider and model answer questions, and where the key for it lives."
        footer={
          <div className="flex items-center gap-3">
            {error && <span className="text-[12px] text-danger-600">{error}</span>}
            <Button
              variant="primary"
              size="sm"
              disabled={!changed || pending}
              onClick={save}
            >
              {pending ? "Saving…" : "Save"}
            </Button>
          </div>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="ai-provider">Provider</Label>
            <Input
              id="ai-provider"
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ai-model">Model</Label>
            <Input
              id="ai-model"
              value={model}
              onChange={(event) => setModel(event.target.value)}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="ai-key">API key</Label>
            <Input
              id="ai-key"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={
                config.keySuffix ? `Key on file, ending in …${config.keySuffix}` : "No key installed"
              }
            />
            <p className="text-[12px] text-ink-500">
              {config.keySuffix
                ? `A key is installed, ending in …${config.keySuffix}. It is never shown again -- type a new one here to replace it, or leave this blank to keep it.`
                : "Never shown once saved -- only a masked ending, so it can be replaced but not read back."}
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ai-base-url">Base URL</Label>
            <Input
              id="ai-base-url"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="Default provider endpoint"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ai-budget">Daily token budget</Label>
            <Input
              id="ai-budget"
              type="number"
              min={0}
              value={dailyTokenBudget}
              onChange={(event) => setDailyTokenBudget(event.target.value)}
            />
            <p className="text-[12px] text-ink-500">
              A hard stop, not a warning: once the workspace has spent this many
              tokens today, AI answers quietly stop for the rest of the day and
              the widget falls back to today&apos;s behaviour -- no error, and
              it resets at midnight.
            </p>
          </div>
        </div>
      </SettingSection>
    </div>
  );
}
