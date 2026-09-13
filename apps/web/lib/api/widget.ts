import "server-only";

import { ApiError, apiFetch } from "./client";

/**
 * Anonymous calls the embedded widget makes, addressed by widget key rather
 * than by workspace slug (spec D3) -- see `relaydesk.api.widget`, the
 * anonymous door onto the same knowledge-base and ticket services
 * `lib/api/public.ts` already calls by slug.
 *
 * Every schema on the API side inherits `CamelModel`, so the wire is
 * already camelCase -- `workspaceName`, `articleCount` -- and needs no
 * mapping layer here, unlike a naive REST client might.
 *
 * `auth: false` on every call: a widget key is public by construction
 * (spec D1) and never carries a bearer session.
 */

/** Everything the frame needs for its first paint, in one call. */
export interface WidgetBootstrap {
  workspaceName: string;
  /** This workspace's subdomain on the public help site. The panel is
   *  anonymous and has no session to resolve one from, so without this
   *  an article has no help-centre address to offer. */
  workspaceSlug: string;
  monogram: string;
  settings: Record<string, unknown>;
  /** Drives the empty-knowledge-base screen (spec D7). */
  articleCount: number;
  /**
   * Whether this workspace can actually answer a question -- AI switched on
   * AND a key installed. Decides whether the panel opens on the
   * conversation view or on search.
   *
   * Optional because a workspace that has never configured AI is the
   * ordinary case, not an error. Declared here rather than left to the
   * untyped `JSON.parse` it arrives through: the value reaches `Panel` via
   * a `{...bootstrap}` spread, so without this line a refactor to explicit
   * props would drop it silently, with no compiler error and no failing
   * test.
   */
  aiEnabled?: boolean;
}

/**
 * `GET /widget/{key}`, translated to `null` on an unknown or inactive key
 * so the frame page can render `notFound()` rather than an uncaught 404.
 * Unknown and inactive keys answer identically (spec: resolve()), so there
 * is nothing more specific to distinguish here.
 */
export async function getWidgetBootstrap(key: string): Promise<WidgetBootstrap | null> {
  try {
    return await apiFetch<WidgetBootstrap>(`/widget/${encodeURIComponent(key)}`, {
      auth: false,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** An entry in a search result -- no body, no doc, matches the public shape. */
export interface WidgetArticleSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  path: string;
}

/**
 * `GET /widget/{key}/kb/search`. Server-side search, called from the
 * frame's own `search` route rather than the widget key resolving to an
 * unknown one -- the route above already turned that into `notFound()`
 * before this can run.
 *
 * Caught the same way its two siblings above catch theirs: the frame's
 * session can outlive the key it opened with (an admin can deactivate or
 * delete one mid-visit), and without this a search from that stale key
 * surfaces as an unhandled 500 shape instead of the empty result an
 * unknown key already means everywhere else on this door.
 */
export async function searchWidgetKb(
  key: string,
  q: string,
): Promise<WidgetArticleSummary[]> {
  try {
    return await apiFetch<WidgetArticleSummary[]>(
      `/widget/${encodeURIComponent(key)}/kb/search?q=${encodeURIComponent(q)}`,
      { auth: false },
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return [];
    throw error;
  }
}

/** Who wrote an article. Name and monogram -- never an address. */
export interface WidgetAuthor {
  name: string;
  monogram: string;
}

/** A single published article, with its rendered body. */
export interface WidgetArticle extends WidgetArticleSummary {
  doc: unknown;
  publishedAt: string | null;
  updatedAt: string;
  author: WidgetAuthor | null;
}

/** One step of the collections above an article. Name to print (unused by
 * the widget today) and slug to build a `kb/collections` request -- see
 * `PublicCrumb` in `lib/api/public.ts` for the same shape, one door over. */
export interface WidgetCrumb {
  name: string;
  slug: string;
}

/** An article plus where it sits, as `getWidgetArticle` resolves it. */
export interface WidgetArticlePage {
  article: WidgetArticle;
  /** The categories above it, nearest last. Empty for an article filed at
   * the knowledge base's own root. */
  ancestors: WidgetCrumb[];
}

/**
 * A knowledge-base path, encoded for the API's catch-all route, or `null`
 * if it does not name a place inside this key's knowledge base.
 *
 * The slashes have to survive -- the path is slash-joined
 * ("billing/refunds") and the catch-all expects them -- so each segment is
 * encoded separately rather than the whole string at once, which would
 * turn them into %2F and resolve nothing.
 *
 * Encoding alone is not enough to make that safe. `encodeURIComponent`
 * leaves a dot untouched, so `..` passes through intact and URL resolution
 * then normalises it away: `/widget/{key}/kb/../../../../openapi.json`
 * resolves to `/openapi.json`. The key segment is consumed by the climb,
 * so no valid key is needed -- it would turn this proxy into an anonymous
 * door onto every path the API serves. An empty segment is the same bug
 * from the other end: a leading slash addresses the API's root instead of
 * a path beneath this key.
 *
 * So the segments are checked, not just escaped. Dot segments and empty
 * segments are refused outright; everything else is a legitimate slug.
 */
export function encodeKbPath(path: string): string | null {
  const segments = path.split("/");
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
    return null;
  }
  return segments.map(encodeURIComponent).join("/");
}

/**
 * `GET /widget/{key}/kb/{path}`, resolved to the article it names, its
 * collections included -- `article.tsx` needs the nearest one to find the
 * article's related reading.
 *
 * `null` on anything that is not a live article: unknown path, a category
 * (the widget never browses collections, only opens articles a search
 * returned), or a 404 from an unknown key. See `getPublicNode` in
 * `lib/api/public.ts` for the same idiom, one door over.
 */
export async function getWidgetArticle(
  key: string,
  path: string,
): Promise<WidgetArticlePage | null> {
  const encoded = encodeKbPath(path);
  if (encoded === null) return null;

  try {
    const node = await apiFetch<{
      kind: "category" | "article";
      article?: WidgetArticle;
      ancestors?: WidgetCrumb[];
    }>(`/widget/${encodeURIComponent(key)}/kb/${encoded}`, { auth: false });
    return node.kind === "article" && node.article
      ? { article: node.article, ancestors: node.ancestors ?? [] }
      : null;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/**
 * One of "searched", "read" or "submitted" -- what a widget session flag
 * `POST /widget/{key}/sessions/{sessionId}` raises. Matches the API's own
 * closed set in `relaydesk.services.widget_sessions`.
 */
export type WidgetSessionEventKind = "searched" | "read" | "submitted";

/**
 * `POST /widget/{key}/sessions/{sessionId}`. The deflection baseline: how
 * far one panel open got, never what was searched, read or sent.
 *
 * Idempotent server-side (flags only ever go up), but callers still fire
 * each kind at most once per session -- see `panel.tsx`. Nothing here
 * catches a failure: the caller (`app/(widget)/widget/session/route.ts`)
 * is the layer that must swallow one, so a counter can never break a
 * support request.
 */
export async function recordWidgetSessionEvent(
  key: string,
  sessionId: string,
  kind: WidgetSessionEventKind,
): Promise<void> {
  await apiFetch<void>(
    `/widget/${encodeURIComponent(key)}/sessions/${encodeURIComponent(sessionId)}`,
    { method: "POST", auth: false, body: JSON.stringify({ kind }) },
  );
}

/** The API's answer to a ticket submission -- a real one or a caught honeypot look identical. */
export interface WidgetTicketSubmitted {
  received: boolean;
}

/**
 * `POST /widget/{key}/tickets`, form-encoded. Not wrapped in `cache()` --
 * this is a mutation, and caching it would replay a retried submission's
 * first result instead of trying again. See `submitPublicTicket` for the
 * identical reasoning, one door over.
 */
export async function submitWidgetTicket(
  key: string,
  form: FormData,
  forwardedFor: string | null,
): Promise<WidgetTicketSubmitted> {
  return apiFetch<WidgetTicketSubmitted>(`/widget/${encodeURIComponent(key)}/tickets`, {
    method: "POST",
    auth: false,
    body: form,
    headers: forwardedFor ? { "X-Forwarded-For": forwardedFor } : undefined,
  });
}
