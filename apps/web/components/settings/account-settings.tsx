"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";

import { SettingSection } from "@/components/console/setting-section";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

interface AccountSettingsProps {
  user: {
    name: string;
    email: string;
    monogram: string;
    timeZone: string;
    emailNotifications: boolean;
    slackNotifications: boolean;
  };
  timeZones: string[];
}

export function AccountSettings({ user, timeZones }: AccountSettingsProps) {
  const [name, setName] = useState(user.name);
  const [timeZone, setTimeZone] = useState(user.timeZone);
  const [emailNotifications, setEmailNotifications] = useState(
    user.emailNotifications,
  );
  const [slackNotifications, setSlackNotifications] = useState(
    user.slackNotifications,
  );

  const nameChanged = name !== user.name;

  return (
    <div className="space-y-4">
      <SettingSection
        title="Profile"
        footer={
          <Button variant="primary" size="sm" disabled={!nameChanged}>
            Save
          </Button>
        }
      >
        <div className="flex items-start gap-4">
          <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-ink-900 text-sm font-semibold uppercase text-white">
            {user.monogram}
          </span>
          <div className="grid flex-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="account-name">Name</Label>
              <Input
                id="account-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="account-email">Email</Label>
              <Input id="account-email" value={user.email} disabled />
            </div>
          </div>
        </div>
      </SettingSection>

      <SettingSection
        title="Time zone"
        description="Message timestamps are shown in this zone."
        footer={
          <Button variant="primary" size="sm" disabled={timeZone === user.timeZone}>
            Save
          </Button>
        }
      >
        <Select value={timeZone} onValueChange={setTimeZone}>
          <SelectTrigger className="max-w-sm" aria-label="Time zone">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {timeZones.map((zone) => (
              <SelectItem key={zone} value={zone}>
                {zone}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </SettingSection>

      <SettingSection
        title="Email notifications"
        description="Get an email when you are @-mentioned, assigned a ticket, or a reply lands on one of yours."
        action={
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-ink-500">
              {emailNotifications ? "On" : "Off"}
            </span>
            <Switch
              checked={emailNotifications}
              onCheckedChange={setEmailNotifications}
              aria-label="Email notifications"
            />
          </div>
        }
      />

      <SettingSection
        title="Slack notifications"
        description="Get @-mentioned in your team's Slack channel for the same events. Requires an admin to connect Slack first."
        action={
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-ink-500">
              {slackNotifications ? "On" : "Off"}
            </span>
            <Switch
              checked={slackNotifications}
              onCheckedChange={setSlackNotifications}
              aria-label="Slack notifications"
            />
          </div>
        }
      />

      <SettingSection title="Sign out" description="End this session on this device.">
        <Button variant="secondary" size="sm">
          <LogOut />
          Sign out
        </Button>
      </SettingSection>
    </div>
  );
}
