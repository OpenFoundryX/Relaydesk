"use client";

import { useState, useTransition } from "react";
import { Check, Copy, Plus } from "lucide-react";

import { createInviteAction } from "@/app/(console)/settings/team/actions";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type RoleOption = "agent" | "admin";

const ROLE_LABEL: Record<RoleOption, "Agent" | "Admin"> = {
  agent: "Agent",
  admin: "Admin",
};

export function InviteDialog() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<RoleOption>("agent");
  const [error, setError] = useState<string | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isPending, startTransition] = useTransition();

  function reset() {
    setEmail("");
    setRole("agent");
    setError(null);
    setInviteUrl(null);
    setCopied(false);
  }

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) reset();
  }

  function sendInvite() {
    setError(null);
    startTransition(async () => {
      const result = await createInviteAction(email, ROLE_LABEL[role]);
      if (result.ok) {
        setInviteUrl(result.inviteUrl);
      } else {
        setError(result.message);
      }
    });
  }

  async function copyLink() {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked; the link is still selectable in the field.
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Plus />
          Invite teammate
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Invite teammate</DialogTitle>
          <DialogDescription>
            {inviteUrl
              ? "Share this link with them so they can join this workspace."
              : "Relaydesk doesn't send an email — you'll get a link to share yourself."}
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          {inviteUrl ? (
            <div className="space-y-1.5">
              <Label htmlFor="invite-url">Invite link</Label>
              <div className="flex items-center gap-2">
                <Input id="invite-url" readOnly value={inviteUrl} className="font-mono text-[12px]" />
                <Button
                  type="button"
                  variant="secondary"
                  size="icon"
                  aria-label="Copy invite link"
                  onClick={copyLink}
                >
                  {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                </Button>
              </div>
              <p className="text-[12px] text-ink-500">
                This link hasn&apos;t been sent to anyone yet — send it however you&apos;d
                normally reach them.
              </p>
            </div>
          ) : (
            <>
              {error && (
                <p
                  role="alert"
                  className="rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
                >
                  {error}
                </p>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="invite-email">Email</Label>
                <Input
                  id="invite-email"
                  type="email"
                  placeholder="colleague@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoFocus
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="invite-role">Role</Label>
                <Select value={role} onValueChange={(value) => setRole(value as RoleOption)}>
                  <SelectTrigger id="invite-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="agent">Agent — works the queue</SelectItem>
                    <SelectItem value="admin">Admin — full settings access</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          )}
        </DialogBody>
        <DialogFooter>
          {inviteUrl ? (
            <Button variant="primary" onClick={() => handleOpenChange(false)}>
              Done
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={!email.includes("@") || isPending}
                onClick={sendInvite}
              >
                {isPending ? "Sending…" : "Send invite"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
