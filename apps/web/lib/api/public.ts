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

/** An entry in the KB index or search results -- no body, no doc. */
export interface PublicArticleSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
}

/** A single published article, with its rendered body. */
export interface PublicArticle extends PublicArticleSummary {
  doc: unknown;
  publishedAt: string | null;
}

export interface PublicCategory {
  id: string;
  name: string;
  slug: string;
  articles: PublicArticleSummary[];
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

/**
 * The published categories and articles for a workspace's help site. Empty
 * categories are already omitted by the API.
 */
export const getPublicKb = cache(
  async (slug: string): Promise<PublicCategory[]> => {
    return apiFetch<PublicCategory[]>(`/public/${slug}/kb`, { auth: false });
  },
);

/**
 * A single published article. `null` on anything that is not a live,
 * external, published article in this workspace -- draft, ready, another
 * workspace's, or nonexistent all look identical here, so the caller can
 * turn every one of them into the same `notFound()`. See `getArticle` in
 * `lib/api/kb.ts` for the same idiom.
 */
export const getPublicArticle = cache(
  async (
    slug: string,
    category: string,
    article: string,
  ): Promise<PublicArticle | null> => {
    try {
      return await apiFetch<PublicArticle>(
        `/public/${slug}/kb/${category}/${article}`,
        { auth: false },
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
);

/** Full-text search across a workspace's published external articles. */
export const searchPublicKb = cache(
  async (slug: string, q: string): Promise<PublicArticleSummary[]> => {
    return apiFetch<PublicArticleSummary[]>(
      `/public/${slug}/kb/search?q=${encodeURIComponent(q)}`,
      { auth: false },
    );
  },
);
