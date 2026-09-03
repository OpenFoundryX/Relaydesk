"use client";

import { useState } from "react";
import Link from "next/link";

import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { cn } from "@/lib/utils";

import { SelectTile } from "./select-tile";

const TOTAL_STEPS = 4;

const channelGroups = [
  {
    label: "Email",
    options: [
      { id: "gmail", label: "Gmail", monogram: "GM" },
      { id: "forwarding", label: "Email forwarding", monogram: "FW" },
    ],
  },
  {
    label: "Social",
    options: [{ id: "discord", label: "Discord", monogram: "DC" }],
  },
  {
    label: "API",
    options: [{ id: "api", label: "Tickets API", monogram: "AP" }],
  },
];

const integrationGroups = [
  {
    label: "Payments",
    options: [
      { id: "stripe", label: "Stripe", monogram: "ST" },
      { id: "revenuecat", label: "RevenueCat", monogram: "RC" },
      { id: "google-play", label: "Google Play", monogram: "GP" },
    ],
  },
  {
    label: "Data",
    options: [
      { id: "mongodb", label: "MongoDB", monogram: "MG" },
      { id: "supabase", label: "Supabase", monogram: "SB" },
      { id: "postgresql", label: "PostgreSQL", monogram: "PG" },
      { id: "mysql", label: "MySQL", monogram: "MY" },
      { id: "convex", label: "Convex", monogram: "CV" },
    ],
  },
  {
    label: "Development",
    options: [{ id: "github", label: "GitHub", monogram: "GH" }],
  },
];

const nextSteps = [
  { label: "Connect another channel", href: "/settings/channels" },
  { label: "Import from your old help desk", href: "/settings/channels" },
  { label: "Add more integrations", href: "/settings/integrations" },
  { label: "Tune your automations", href: "/settings/automations" },
];

export function OnboardingWizard({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [step, setStep] = useState(1);
  const [channel, setChannel] = useState<string | null>(null);
  const [integrations, setIntegrations] = useState<string[]>([]);
  const [invites, setInvites] = useState([
    { email: "", role: "agent" },
    { email: "", role: "agent" },
  ]);

  const finished = step > TOTAL_STEPS;

  function close() {
    onOpenChange(false);
    // Reset a beat later so the reset is not visible during the close animation.
    setTimeout(() => setStep(1), 200);
  }

  function toggleIntegration(id: string) {
    setIntegrations((current) =>
      current.includes(id)
        ? current.filter((entry) => entry !== id)
        : [...current, id],
    );
  }

  function updateInvite(index: number, patch: Partial<{ email: string; role: string }>) {
    setInvites((current) =>
      current.map((invite, i) => (i === index ? { ...invite, ...patch } : invite)),
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-xl"
        hideClose
        onInteractOutside={(event) => event.preventDefault()}
      >
        <div className="px-5 pt-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">
            {finished ? "Finished" : `Step ${step} of ${TOTAL_STEPS}`}
          </p>
          <div className="mt-2 flex gap-1.5">
            {Array.from({ length: TOTAL_STEPS }).map((_, index) => (
              <span
                key={index}
                className={cn(
                  "h-1 flex-1 rounded-full",
                  finished || index < step ? "bg-accent-500" : "bg-ink-200",
                )}
              />
            ))}
          </div>
        </div>

        <div className="px-5 pb-4 pt-4">
          <DialogTitle>
            {finished
              ? "You're all set"
              : step === 1
                ? "Connect a channel"
                : step === 2
                  ? "Invite your team"
                  : step === 3
                    ? "Connect your integrations"
                    : "Connect your sources"}
          </DialogTitle>
          <DialogDescription>
            {finished
              ? "Your inbox is live. Here is where most teams go next."
              : step === 1
                ? "Where do your support tickets arrive today?"
                : step === 2
                  ? "Add the admins and agents who will work the queue."
                  : step === 3
                    ? "The AI agent reads these when it prepares a resolution."
                    : "The AI agent pulls live copy from these when it drafts a reply."}
          </DialogDescription>
        </div>

        {/* Fixed height so the footer does not jump as steps change size. */}
        <DialogBody className="h-96 overflow-y-auto">
          {step === 1 &&
            channelGroups.map((group) => (
              <div key={group.label}>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  {group.label}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {group.options.map((option) => (
                    <SelectTile
                      key={option.id}
                      label={option.label}
                      monogram={option.monogram}
                      selected={channel === option.id}
                      onSelect={() => setChannel(option.id)}
                    />
                  ))}
                </div>
              </div>
            ))}

          {step === 2 && (
            <div className="space-y-2">
              {invites.map((invite, index) => (
                <div key={index} className="flex gap-2">
                  <Input
                    type="email"
                    placeholder="colleague@example.com"
                    value={invite.email}
                    onChange={(event) =>
                      updateInvite(index, { email: event.target.value })
                    }
                    aria-label={`Teammate ${index + 1} email`}
                  />
                  <Select
                    value={invite.role}
                    onValueChange={(role) => updateInvite(index, { role })}
                  >
                    <SelectTrigger className="w-32" aria-label="Role">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="agent">Agent</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setInvites((current) => [...current, { email: "", role: "agent" }])
                }
                className="rounded text-[13px] font-medium text-ink-600 transition-colors hover:text-ink-900"
              >
                + Add another
              </button>
            </div>
          )}

          {step === 3 &&
            integrationGroups.map((group) => (
              <div key={group.label}>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  {group.label}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {group.options.map((option) => (
                    <SelectTile
                      key={option.id}
                      label={option.label}
                      monogram={option.monogram}
                      selected={integrations.includes(option.id)}
                      onSelect={() => toggleIntegration(option.id)}
                    />
                  ))}
                </div>
              </div>
            ))}

          {step === 4 && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="docs-url">Help centre or docs URL</Label>
                <Input id="docs-url" placeholder="https://example.com/help" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="site-url">Website URL</Label>
                <Input id="site-url" placeholder="https://example.com" />
              </div>
            </div>
          )}

          {finished && (
            <ul className="space-y-1.5">
              {nextSteps.map((item) => (
                <li key={item.label}>
                  <Link
                    href={item.href}
                    onClick={close}
                    className="flex items-center gap-2 rounded text-[13px] text-ink-600 transition-colors hover:text-ink-900"
                  >
                    <span className="size-1 rounded-full bg-accent-600" />
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </DialogBody>

        <DialogFooter>
          {finished ? (
            <Button variant="primary" onClick={close}>
              Go to my inbox
            </Button>
          ) : (
            <>
              {step > 1 && (
                <Button variant="ghost" onClick={() => setStep(step - 1)}>
                  Back
                </Button>
              )}
              <div className="flex-1" />
              <Button variant="secondary" onClick={() => setStep(step + 1)}>
                Skip for now
              </Button>
              <Button variant="primary" onClick={() => setStep(step + 1)}>
                {step === 1
                  ? "Continue"
                  : step === 2
                    ? "Send invites"
                    : step === 3
                      ? "Continue"
                      : "Sync and finish"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
