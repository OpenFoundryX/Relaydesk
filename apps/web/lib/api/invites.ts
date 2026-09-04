import "server-only";

import { apiFetch } from "@/lib/api/client";

export interface InvitePreview {
  workspaceName: string;
  email: string;
  role: "Admin" | "Agent";
}

export interface AcceptedInvite {
  token: string;
  expiresAt: string;
}

/**
 * Invite endpoints are the one part of the API reached without a session:
 * whoever follows the link has no account yet, so `auth: false` is
 * deliberate rather than an oversight.
 */
export async function getInvitePreview(token: string): Promise<InvitePreview> {
  return apiFetch<InvitePreview>(`/invites/${encodeURIComponent(token)}`, {
    auth: false,
  });
}

export async function acceptInvite(
  token: string,
  name: string,
  password: string,
): Promise<AcceptedInvite> {
  return apiFetch<AcceptedInvite>(
    `/invites/${encodeURIComponent(token)}/accept`,
    { method: "POST", auth: false, body: JSON.stringify({ name, password }) },
  );
}
