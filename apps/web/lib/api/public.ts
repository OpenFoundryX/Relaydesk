import "server-only";

import { cache } from "react";

import { ApiError, apiFetch } from "./client";

/**
 * The anonymous, subdomain-resolved view of a workspace -- everything the
 * public portal is allowed to know. See `GET /api/public/workspaces/{slug}`.
 */
export interface PublicWorkspace {
  name: string;
  monogram: string;
}

/**
 * Anonymous, unauthenticated calls against `/api/public/*`.
 *
 * The portal resolves a workspace from its subdomain before a session
 * exists at all, so every call here passes `auth: false` -- no bearer
 * header goes out, and there is nothing to redirect to `/signed-out` on a
 * 401, because a public route never returns one for a missing session.
 *
 * An unresolved slug -- unknown, or reserved -- comes back from the API as
 * a 404. That is translated to `null` here rather than left to throw, so
 * the caller renders Next's real 404 page (via `notFound()`) instead of an
 * uncaught error turning into a 500. See `getConversation` in
 * `lib/api/conversations.ts` for the same idiom.
 */
export const getPublicWorkspace = cache(
  async (slug: string): Promise<PublicWorkspace | null> => {
    try {
      return await apiFetch<PublicWorkspace>(`/public/workspaces/${slug}`, {
        auth: false,
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
);
