"use server";

import { ApiError } from "@/lib/api/client";
import { acceptInvite, previewInvite, type InvitePreview } from "@/lib/api/invites";
import { setSessionCookie } from "@/lib/session";

export type PreviewResult = { ok: true; invite: InvitePreview } | { ok: false };

/**
 * The token lives only in the URL fragment (see app/invites/page.tsx), so
 * the client component that calls this passes it as a plain argument --
 * never a query string -- keeping it out of this request's own URL too.
 */
export async function previewInviteAction(token: string): Promise<PreviewResult> {
  try {
    return { ok: true, invite: await previewInvite(token) };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return { ok: false };
    throw error;
  }
}

export type AcceptResult =
  | { ok: true }
  | { ok: false; invalid: true }
  | { ok: false; invalid: false; message: string };

/**
 * Accepting signs you in: the API returns a session token, exactly as
 * /auth/login does, so the new member lands in the inbox rather than on a
 * second sign-in form.
 */
export async function acceptInviteAction(
  token: string,
  name: string,
  password: string,
): Promise<AcceptResult> {
  try {
    const session = await acceptInvite(token, name, password);
    await setSessionCookie(session.token, session.expiresAt);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) return { ok: false, invalid: true };
      // A Conflict's message (already a member, already accepted) is meant
      // to be shown as-is -- see relaydesk.services.team.accept_invite.
      return { ok: false, invalid: false, message: error.message };
    }
    throw error;
  }
}
