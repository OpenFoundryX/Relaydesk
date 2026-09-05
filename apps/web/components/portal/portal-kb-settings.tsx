"use client";

import { useState } from "react";
import Link from "next/link";

import { SettingSection } from "@/components/console/setting-section";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { KbCategory } from "@/lib/types";

export function PortalKbSettings({ categories }: { categories: KbCategory[] }) {
  const [showKb, setShowKb] = useState(categories.length > 0);

  return (
    <div className="space-y-4">
      <SettingSection
        title="Show the knowledge base"
        description="Publish your external articles alongside the ticket form, so customers can answer their own question first."
        action={
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-ink-500">{showKb ? "On" : "Off"}</span>
            <Switch
              checked={showKb}
              onCheckedChange={setShowKb}
              disabled={categories.length === 0}
              aria-label="Show knowledge base on the portal"
            />
          </div>
        }
      >
        {categories.length === 0 && (
          <div className="rounded-md border border-accent-300 bg-accent-50 px-3 py-2.5">
            <p className="text-[13px] text-ink-700">
              Your external knowledge base is empty. Write at least one article
              before you can show it here.
            </p>
            <Button asChild variant="secondary" size="sm" className="mt-2.5">
              <Link href="/knowledge-base?tab=external">Go to the knowledge base</Link>
            </Button>
          </div>
        )}
      </SettingSection>

      {categories.length > 0 && (
        <SettingSection
          title="Sections"
          description="Choose which sections appear on the portal."
          footer={<Button variant="primary" size="sm">Save</Button>}
        >
          <ul className="divide-y divide-ink-200 rounded-md border border-ink-200">
            {categories.map((category) => (
              <li
                key={category.id}
                className="flex items-center gap-3 px-3 py-2.5"
              >
                <span className="text-[13px] font-medium text-ink-900">
                  {category.name}
                </span>
                <span className="text-[12px] text-ink-500">
                  {category.articleCount} articles
                </span>
                <Switch
                  defaultChecked
                  className="ml-auto"
                  aria-label={`Show ${category.name}`}
                />
              </li>
            ))}
          </ul>
        </SettingSection>
      )}
    </div>
  );
}
