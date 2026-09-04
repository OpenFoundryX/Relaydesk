import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Invites are disabled for this release, not just unbuilt.
 *
 * Three successive security reviews each found a live cross-tenant account
 * takeover in invite acceptance: an invite binds an email address that
 * nobody has proved they control, and accepting one both adopts an account
 * and signs the accepter in. There is no mailer and no password-reset flow
 * yet, so there is no way to close that loop — the feature is switched off
 * at the API (POST /team/invites now answers 503) until a later release can
 * gate acceptance on proving control of the address by email.
 *
 * The trigger stays visible but disabled, with an inline explanation,
 * rather than a form that would submit into that 503.
 */
export function InviteDialog() {
  return (
    <div className="flex items-center gap-2">
      <p className="max-w-48 text-right text-[12px] leading-snug text-ink-500">
        Coming in a later release — invites need email delivery first.
      </p>
      <Button variant="primary" size="sm" disabled aria-disabled="true">
        <Plus />
        Invite teammate
      </Button>
    </div>
  );
}
