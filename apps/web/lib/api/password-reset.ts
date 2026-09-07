import "server-only";

import { apiFetch } from "./client";

/**
 * Reached without a session -- whoever is asking cannot sign in, which is
 * the point -- so `auth: false` is deliberate rather than an oversight.
 *
 * Always resolves. The API answers 202 for every address, so there is
 * nothing here to branch on and nothing to report back that would not
 * itself say whether the address has an account.
 */
export async function requestPasswordReset(email: string): Promise<void> {
  await apiFetch<void>("/auth/password-reset", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email }),
  });
}

/**
 * The token travels in the request body, never a path or query parameter,
 * which is what would otherwise land it verbatim in an access log. Same
 * rule as the invite routes.
 */
export async function confirmPasswordReset(
  token: string,
  password: string,
): Promise<void> {
  await apiFetch<void>("/auth/password-reset/confirm", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ token, password }),
  });
}
