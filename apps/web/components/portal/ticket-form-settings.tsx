"use client";

import { useState } from "react";

import { SettingSection } from "@/components/console/setting-section";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

interface FieldConfig {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
  /** Email and message are the two fields a ticket cannot exist without. */
  locked: boolean;
}

const initialFields: FieldConfig[] = [
  {
    id: "email",
    label: "Email",
    description: "Always collected — it is how we reply.",
    enabled: true,
    locked: true,
  },
  {
    id: "name",
    label: "Name",
    description: "Optional. Lets the agent open with a first name.",
    enabled: true,
    locked: false,
  },
  {
    id: "subject",
    label: "Subject",
    description: "Optional. A one-line summary of the issue.",
    enabled: true,
    locked: false,
  },
  {
    id: "message",
    label: "Message",
    description: "Always collected — this is the ticket body.",
    enabled: true,
    locked: true,
  },
  {
    id: "attachments",
    label: "Attachments",
    description: "Images, video, and PDF up to 10MB each.",
    enabled: true,
    locked: false,
  },
];

export function TicketFormSettings() {
  const [fields, setFields] = useState(initialFields);

  return (
    <div className="space-y-4">
      <SettingSection
        title="Fields"
        description="What customers are asked for when they write in."
        footer={<Button variant="primary" size="sm">Save</Button>}
      >
        <ul className="divide-y divide-ink-200 rounded-md border border-ink-200">
          {fields.map((field) => (
            <li key={field.id} className="flex items-center gap-3 px-3 py-2.5">
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-ink-900">{field.label}</p>
                <p className="text-[12px] text-ink-500">{field.description}</p>
              </div>
              <div className="ml-auto shrink-0">
                <Switch
                  checked={field.enabled}
                  disabled={field.locked}
                  aria-label={`Show ${field.label}`}
                  onCheckedChange={(checked) =>
                    setFields((current) =>
                      current.map((entry) =>
                        entry.id === field.id
                          ? { ...entry, enabled: checked }
                          : entry,
                      ),
                    )
                  }
                />
              </div>
            </li>
          ))}
        </ul>
      </SettingSection>

      <SettingSection
        title="Submit button"
        description="The label on the button, and the fine print underneath it."
        footer={<Button variant="primary" size="sm">Save</Button>}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="submit-label">Button label</Label>
            <Input id="submit-label" defaultValue="Submit ticket" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="consent-text">Fine print</Label>
            <Input
              id="consent-text"
              defaultValue="By submitting, you agree to share this information with Chronon."
            />
          </div>
        </div>
      </SettingSection>
    </div>
  );
}
