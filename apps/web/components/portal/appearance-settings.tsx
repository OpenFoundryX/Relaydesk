"use client";

import { useState } from "react";
import { Upload } from "lucide-react";

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
}: {
  headline: string;
  intro: string;
}) {
  const [accent, setAccent] = useState(swatches[0]);

  return (
    <div className="space-y-4">
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
