"use client";

import { useState, useTransition } from "react";
import { Upload } from "lucide-react";

import { saveWorkspaceIdentityAction } from "@/app/(console)/user-portal/actions";
import { SettingSection } from "@/components/console/setting-section";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const swatches = ["#18181B", "#6E8225", "#1B5E43", "#5145CD", "#B45309", "#B91C1C"];

export function AppearanceSettings({
  headline,
  intro,
  name,
  monogram,
}: {
  headline: string;
  intro: string;
  /** The workspace's own name. Real, unlike the rest of this page. */
  name: string;
  /** The initials on the tile beside it. */
  monogram: string;
}) {
  const [accent, setAccent] = useState(swatches[0]);
  const [identity, setIdentity] = useState({ name, monogram });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, startSaving] = useTransition();

  const dirty = identity.name !== name || identity.monogram !== monogram;

  function save() {
    setError(null);
    setSaved(false);
    startSaving(async () => {
      const result = await saveWorkspaceIdentityAction(
        identity.name.trim(),
        identity.monogram.trim(),
      );
      if (result.ok) setSaved(true);
      else setError(result.message);
    });
  }

  return (
    <div className="space-y-4">
      {/*
       * The workspace's own identity, shown on the help centre's hero and
       * in the console header. This section writes through to the API; the
       * ones below it are still mock.
       */}
      <SettingSection
        title="Workspace"
        description="The name and initials shown at the top of your help centre."
        footer={
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              disabled={
                saving ||
                !dirty ||
                identity.name.trim().length === 0 ||
                identity.monogram.trim().length === 0
              }
              onClick={save}
            >
              {saving ? "Saving…" : "Save"}
            </Button>
            {saved && !dirty && (
              <span className="text-[12px] text-ink-500">Saved</span>
            )}
          </div>
        }
      >
        <div className="space-y-3">
          {error && (
            <p
              role="alert"
              className="rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
            >
              {error}
            </p>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="workspace-name">Name</Label>
            <Input
              id="workspace-name"
              value={identity.name}
              maxLength={120}
              onChange={(event) =>
                setIdentity((current) => ({ ...current, name: event.target.value }))
              }
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="workspace-monogram">Monogram</Label>
            <div className="flex items-center gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-ink-900 text-[11px] font-semibold text-white">
                {identity.monogram.trim() || "—"}
              </span>
              <Input
                id="workspace-monogram"
                value={identity.monogram}
                maxLength={4}
                className="w-24"
                onChange={(event) =>
                  setIdentity((current) => ({
                    ...current,
                    monogram: event.target.value,
                  }))
                }
              />
            </div>
            <p className="text-[12px] text-ink-500">
              Up to four characters. Shown when there is no logo.
            </p>
          </div>
        </div>
      </SettingSection>
      <SettingSection
        title="Brand"
        description="Applied to the portal header and its primary button."
        footer={<Button variant="primary" size="sm">Save</Button>}
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Accent colour</Label>
            <div className="flex items-center gap-2">
              {swatches.map((swatch) => (
                <button
                  key={swatch}
                  type="button"
                  onClick={() => setAccent(swatch)}
                  aria-label={`Use ${swatch}`}
                  aria-pressed={accent === swatch}
                  style={{ backgroundColor: swatch }}
                  className={cn(
                    "size-7 rounded-full ring-offset-2",
                    accent === swatch && "ring-2 ring-ink-900",
                  )}
                />
              ))}
              <Input
                value={accent}
                onChange={(event) => setAccent(event.target.value)}
                className="ml-2 w-28 font-mono text-[12px]"
                aria-label="Accent colour hex"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Logo</Label>
            <div className="flex items-center gap-3">
              <span className="flex size-11 items-center justify-center rounded-md border border-dashed border-ink-300 text-[11px] text-ink-400">
                None
              </span>
              <Button variant="secondary" size="sm">
                <Upload />
                Upload logo
              </Button>
            </div>
            <p className="text-[12px] text-ink-500">
              SVG or PNG, at least 128px square.
            </p>
          </div>
        </div>
      </SettingSection>

      <SettingSection
        title="Copy"
        description="The heading and blurb at the top of the ticket form."
        footer={<Button variant="primary" size="sm">Save</Button>}
      >
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="portal-headline">Heading</Label>
            <Input id="portal-headline" defaultValue={headline} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="portal-intro">Intro</Label>
            <Textarea id="portal-intro" defaultValue={intro} className="min-h-16" />
          </div>
        </div>
      </SettingSection>
    </div>
  );
}
