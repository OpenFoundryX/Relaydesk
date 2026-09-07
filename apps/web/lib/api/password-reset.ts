import "server-only";

import { apiFetch } from "./client";

/**
 * Reached without a session -- whoever is asking cannot sign in, which is
 * the point -- so `auth: false` is deliberate rather than an oversight.
 *
 * Always resolves (barring a transport failure or a `422` on a malformed
 * address, both of which the caller handles). The API answers 202 for
 * every syntactically valid address, so there is nothing here to branch on
 * and nothing to report back that would itself say whether the address has
 * an account.
 *
 * `forwardedFor` carries the requester's address for the API's per-IP rate
 * limiter. It is passed through as `X-Forwarded-For` rather than baked into
 * this function's own logic, because the API only believes that header
 * from a peer listed in `TRUSTED_PROXY_IPS` (see docker-compose.yml /
 * README) -- deciding whether to trust it is the API's job, not this
 * function's. Same shape as `submitPublicTicket` in `lib/api/public.ts`.
 * Without this, every request the API sees arrives from the `web`
 * container's own address, which the API's `client_ip.resolve` trusts as a
 * proxy but finds no forwarded header on -- collapsing the whole
 * deployment onto one shared five-per-hour bucket.
 */
export async function requestPasswordReset(
  email: string,
  forwardedFor: string | null,
): Promise<void> {
  await apiFetch<void>("/auth/password-reset", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email }),
    headers: forwardedFor ? { "X-Forwarded-For": forwardedFor } : undefined,
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
