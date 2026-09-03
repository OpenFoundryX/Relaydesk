"use client";

import { useState } from "react";
import { Flag, Plus, Tag, Users } from "lucide-react";

import { SettingSection } from "@/components/console/setting-section";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function TriageSettings({
  defaults,
}: {
  defaults: { priority: string; assignee: string };
}) {
  const [priority, setPriority] = useState(defaults.priority);
  const [assignee, setAssignee] = useState(defaults.assignee);

  return (
    <div className="space-y-4">
      <SettingSection
        title="Priority"
        description="Let the AI set a priority as each message is ingested, using your rules."
        action={<Flag className="size-4 text-ink-400" />}
        footer={
          <>
            <Button variant="ghost" size="sm">
              Reset
            </Button>
            <Button variant="primary" size="sm">
              Save
            </Button>
          </>
        }
      >
        <Textarea
          value={priority}
          onChange={(event) => setPriority(event.target.value)}
          className="min-h-32 font-mono text-[12px] leading-relaxed"
          aria-label="Priority rules"
        />
        <p className="mt-1.5 text-[12px] text-ink-500">
          Type @ to reference a priority level: URGENT, HIGH, MEDIUM, LOW.
        </p>
      </SettingSection>

      <SettingSection
        title="Assignee"
        description="Let the AI route each conversation to the right teammate as it arrives."
        action={<Users className="size-4 text-ink-400" />}
        footer={
          <>
            <Button variant="ghost" size="sm">
              Reset
            </Button>
            <Button variant="primary" size="sm">
              Save
            </Button>
          </>
        }
      >
        <Textarea
          value={assignee}
          onChange={(event) => setAssignee(event.target.value)}
          className="min-h-32 font-mono text-[12px] leading-relaxed"
          aria-label="Assignment rules"
        />
        <p className="mt-1.5 text-[12px] text-ink-500">
          Type @ to reference a team member.
        </p>
      </SettingSection>

      <SettingSection
        title="Labels"
        description="Let the AI apply labels to conversations as they arrive."
        action={<Tag className="size-4 text-ink-400" />}
      >
        <div className="rounded-md border border-accent-300 bg-accent-50 px-3 py-2.5">
          <p className="text-[13px] text-ink-700">
            Create at least one label before turning on label classification.
          </p>
          <div className="mt-2.5 flex gap-2">
            <Button variant="secondary" size="sm">
              <Plus />
              Create label
            </Button>
            <Button variant="primary" size="sm" disabled>
              Enable
            </Button>
          </div>
        </div>
      </SettingSection>
    </div>
  );
}
