"use client";

import { useState, useTransition } from "react";
import { Plus } from "lucide-react";

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

/**
 * The API mails the invite itself, so there is nothing left for this dialog
 * to hand back to the sender -- no link to copy, just confirmation that the
 * send went through.
 */
export function InviteDialog() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<RoleOption>("agent");
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function reset() {
    setEmail("");
    setRole("agent");
    setError(null);
    setSentTo(null);
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
        setSentTo(email);
      } else {
        setError(result.message);
      }
    });
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
            {sentTo
              ? "They'll get an email with a link to set up their account."
              : "We'll email them a link to set up their account."}
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          {sentTo ? (
            <p className="rounded-md border border-positive-200 bg-positive-50 px-3 py-2 text-[13px] text-positive-600">
              Invitation sent to {sentTo}.
            </p>
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
          {sentTo ? (
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
