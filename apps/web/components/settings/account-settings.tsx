"use client";

import { useState, useTransition } from "react";
import { LogOut } from "lucide-react";

import { setNotifyOnAssignmentAction } from "@/app/(console)/settings/account/actions";
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
    notifyOnAssignment: boolean;
  };
  timeZones: string[];
}

export function AccountSettings({ user, timeZones }: AccountSettingsProps) {
  const [name, setName] = useState(user.name);
  const [timeZone, setTimeZone] = useState(user.timeZone);
  const [notifyOnAssignment, setNotifyOnAssignment] = useState(user.notifyOnAssignment);
  // Not yet returned by the API; defaults to off until Slack ships.
  const [slackNotifications, setSlackNotifications] = useState(false);
  const [, startTransition] = useTransition();

  function handleNotifyChange(next: boolean) {
    setNotifyOnAssignment(next);
    startTransition(async () => {
      await setNotifyOnAssignmentAction(next);
    });
  }

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
        title="Assignment email"
        description="Get an email when a ticket is assigned to you."
        action={
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-ink-500">
              {notifyOnAssignment ? "On" : "Off"}
            </span>
            <Switch
              checked={notifyOnAssignment}
              onCheckedChange={handleNotifyChange}
              aria-label="Assignment email"
            />
          </div>
        }
      />

      <SettingSection
        title="Slack notifications"
        description="Get notified in your team's Slack channel when a ticket is assigned to you. Requires an admin to connect Slack first."
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
