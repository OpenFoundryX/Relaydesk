"use client";

import { useState } from "react";
import { Plus } from "lucide-react";

import { SettingSection } from "@/components/console/setting-section";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

export function AutomationSettings() {
  const [roundRobin, setRoundRobin] = useState("off");
  const [resolveAfter, setResolveAfter] = useState("7");
  const [draftEagerness, setDraftEagerness] = useState([25]);
  const [chatCapture, setChatCapture] = useState([65]);
  const [syncDrafts, setSyncDrafts] = useState(false);
  const [autoTranslate, setAutoTranslate] = useState(true);
  const [translateReplies, setTranslateReplies] = useState(true);

  return (
    <div className="space-y-4">
      <SettingSection
        title="Round-robin assignment"
        description="Hand new tickets to team members in turn."
        footer={<Button variant="primary" size="sm">Save</Button>}
      >
        <Select value={roundRobin} onValueChange={setRoundRobin}>
          <SelectTrigger className="max-w-xs" aria-label="Round-robin mode">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="off">Off</SelectItem>
            <SelectItem value="all">Across everyone</SelectItem>
            <SelectItem value="agents">Agents only</SelectItem>
          </SelectContent>
        </Select>
      </SettingSection>

      <SettingSection
        title="Automatic labels"
        description="Apply labels based on the sender's address or the subject line."
        action={
          <Button variant="primary" size="sm">
            <Plus />
            Add rule
          </Button>
        }
      >
        <p className="text-[13px] text-ink-500">
          Create a label first, then you can route to it from here.
        </p>
      </SettingSection>

      <SettingSection
        title="Acknowledgement email"
        description="Send an automatic reply when a customer first writes in."
      >
        <p className="text-[13px] text-ink-500">
          Connect an inbox before you can configure this.
        </p>
      </SettingSection>

      <SettingSection
        title="Ignore non-ticket email"
        description="Filter out spam, marketing, and anything else that is not a support request."
      >
        <p className="text-[13px] text-ink-500">
          Connect an inbox before you can configure this.
        </p>
      </SettingSection>

      <SettingSection
        title="Auto-resolve pending tickets"
        description="Close tickets that have sat in Pending without a customer reply."
        footer={<Button variant="primary" size="sm">Save</Button>}
      >
        <div className="flex items-center gap-2">
          <Input
            type="number"
            min={1}
            value={resolveAfter}
            onChange={(event) => setResolveAfter(event.target.value)}
            className="w-20"
            aria-label="Days before auto-resolve"
          />
          <span className="text-[13px] text-ink-500">days</span>
        </div>
      </SettingSection>

      <SettingSection
        title="Draft eagerness"
        description="How confident the AI must be before it offers you a draft."
      >
        <SliderRow
          value={draftEagerness}
          onChange={setDraftEagerness}
          left="Never draft"
          right="Always draft"
          label="Draft eagerness"
        />
      </SettingSection>

      <SettingSection
        title="Chat ticket capture"
        description="How confident the AI must be that a chat is a real issue before it opens a ticket."
      >
        <SliderRow
          value={chatCapture}
          onChange={setChatCapture}
          left="More tickets"
          right="Fewer tickets"
          label="Chat ticket capture"
        />
      </SettingSection>

      <ToggleSection
        title="Mirror AI drafts into Gmail"
        description="When a draft is generated, also create it as a draft in your mailbox."
        checked={syncDrafts}
        onChange={setSyncDrafts}
      />

      <ToggleSection
        title="Translate incoming messages"
        description="Show non-English conversations in English by default."
        checked={autoTranslate}
        onChange={setAutoTranslate}
      />

      <ToggleSection
        title="Translate outgoing replies"
        description="Send your replies in the language the customer wrote in."
        checked={translateReplies}
        onChange={setTranslateReplies}
      />
    </div>
  );
}

function SliderRow({
  value,
  onChange,
  left,
  right,
  label,
}: {
  value: number[];
  onChange: (value: number[]) => void;
  left: string;
  right: string;
  label: string;
}) {
  return (
    <div className="max-w-md">
      <Slider value={value} onValueChange={onChange} max={100} step={1} aria-label={label} />
      <div className="mt-2 flex justify-between text-[12px] text-ink-500">
        <span>{left}</span>
        <span>{right}</span>
      </div>
    </div>
  );
}

function ToggleSection({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <SettingSection
      title={title}
      description={description}
      action={
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-ink-500">
            {checked ? "On" : "Off"}
          </span>
          <Switch
            checked={checked}
            onCheckedChange={onChange}
            aria-label={title}
          />
        </div>
      }
    />
  );
}
