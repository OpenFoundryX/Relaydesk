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

/** An entry in a collection listing or search results -- no body, no doc. */
export interface PublicArticleSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  /**
   * Slash-joined, no leading slash. Carried with the article rather than
   * derived: once categories nest, a slug alone does not say where the
   * article lives, and rebuilding the href would mean walking the index.
   */
  path: string;
}

/** Who wrote an article. Name and monogram -- never an address. */
export interface PublicAuthor {
  name: string;
  monogram: string;
}

/** A single published article, with its rendered body. */
export interface PublicArticle extends PublicArticleSummary {
  doc: unknown;
  publishedAt: string | null;
  /** ISO-8601. Printed under the body as "Last updated". */
  updatedAt: string;
  /** Null where the author's account has been deleted. */
  author: PublicAuthor | null;
}

/** A collection as it appears on a card. */
export interface PublicCollection {
  id: string;
  name: string;
  slug: string;
  description: string;
  /** A name from the API's fixed set, resolved by `CategoryIcon`. */
  icon: string;
  /** Every published article beneath it, not only its direct ones. */
  articleCount: number;
}

/** One step of a breadcrumb: name to print, slug to build the href. */
export interface PublicCrumb {
  name: string;
  slug: string;
}

/**
 * What a help-site path resolves to. A collection page, a section page and
 * an article page are one walk with three endings, so the API answers all
 * three from one route and `kind` says which came back.
 */
/**
 * One card on a collection page: a section, and the rows it lists. The rows
 * are of two kinds -- articles, and sub-collections carrying their own
 * counts -- and a card mixes them freely.
 */
export interface PublicSection {
  collection: PublicCollection;
  collections: PublicCollection[];
  articles: PublicArticleSummary[];
}

export type PublicNode =
  | {
      kind: "category";
      category: PublicCollection;
      ancestors: PublicCrumb[];
      sections: PublicSection[];
      /** Articles sitting directly here rather than in a section. */
      articles: PublicArticleSummary[];
    }
  | { kind: "article"; article: PublicArticle; ancestors: PublicCrumb[] };

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
 * The help site's front page: root collections, each with its blurb, its
 * icon, and how many published articles sit anywhere beneath it. A
 * collection with nothing published under it is already omitted by the API.
 */
export const getPublicCollections = cache(
  async (slug: string): Promise<PublicCollection[]> => {
    return apiFetch<PublicCollection[]>(`/public/${slug}/kb`, { auth: false });
  },
);

/**
 * One help-site path, resolved to the page it names.
 *
 * `null` on anything that is not a live, external, published page in this
 * workspace -- a draft, a ready-but-unpublished article, an internal
 * category, another workspace's, or a path that never existed all look
 * identical here, so the caller can turn every one of them into the same
 * `notFound()`. See `getArticle` in `lib/api/kb.ts` for the same idiom.
 *
 * The node carries its ancestors, which are both the breadcrumb and the
 * canonical path: a URL that disagrees with them is an old link to an
 * article that has since moved, and the page redirects rather than serving
 * the same article at two addresses.
 */
export const getPublicNode = cache(
  async (slug: string, path: string[]): Promise<PublicNode | null> => {
    const encoded = path.map(encodeURIComponent).join("/");
    try {
      return await apiFetch<PublicNode>(`/public/${slug}/kb/${encoded}`, {
        auth: false,
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
);

/** One row of the browser's search index. See `components/portal/search-index.ts`. */
export interface PublicSearchEntry {
  id: string;
  title: string;
  excerpt: string;
  path: string;
  /** The collections above it, root first. Shown, and matched on. */
  collections: string[];
}

/**
 * Every published article's title, blurb and path -- the whole surface the
 * browser scores instant results against. Bodies are absent by design:
 * they are what makes a knowledge base too large to ship, and
 * `searchPublicKb` below is what searches them.
 */
export const getPublicSearchIndex = cache(
  async (slug: string): Promise<PublicSearchEntry[]> => {
    return apiFetch<PublicSearchEntry[]>(`/public/${slug}/kb/search/index`, {
      auth: false,
    });
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

/** The API's answer to a ticket submission -- a real one or a caught honeypot look identical. */
export interface TicketSubmitted {
  received: boolean;
}

/**
 * Submit a portal ticket. `POST /public/{slug}/tickets`, multipart.
 *
 * Not wrapped in `cache()` -- unlike every read above, this is a mutation,
 * and caching a POST would mean a retried submission after a transient
 * failure silently replays the first attempt's result instead of trying
 * again.
 *
 * `forwardedFor` carries the submitter's address for the API's rate
 * limiter. It is passed through as `X-Forwarded-For` rather than baked into
 * this function's own logic, because the API only believes that header
 * from a peer listed in `TRUSTED_PROXY_IPS` (see docker-compose.yml /
 * README) -- deciding whether to trust it is the API's job, not this
 * function's.
 */
export async function submitPublicTicket(
  slug: string,
  form: FormData,
  forwardedFor: string | null,
): Promise<TicketSubmitted> {
  return apiFetch<TicketSubmitted>(`/public/${slug}/tickets`, {
    method: "POST",
    auth: false,
    body: form,
    headers: forwardedFor ? { "X-Forwarded-For": forwardedFor } : undefined,
  });
}
