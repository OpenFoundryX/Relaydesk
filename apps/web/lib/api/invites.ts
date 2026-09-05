import "server-only";

import { apiFetch } from "./client";

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
 * Reached without a session: whoever holds the link has no account yet, so
 * `auth: false` is deliberate rather than an oversight. The token travels
 * only in the request body -- never a path or query parameter, which is
 * what would otherwise land it verbatim in an access log. See the block
 * comment on the API's invite routes (`relaydesk.api.team`).
 */
export async function previewInvite(token: string): Promise<InvitePreview> {
  return apiFetch<InvitePreview>("/invites/preview", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ token }),
  });
}

export async function acceptInvite(
  token: string,
  name: string,
  password: string,
): Promise<AcceptedInvite> {
  return apiFetch<AcceptedInvite>("/invites/accept", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ token, name, password }),
  });
}
