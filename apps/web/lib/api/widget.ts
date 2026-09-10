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
  monogram: string;
  settings: Record<string, unknown>;
  /** Drives the empty-knowledge-base screen (spec D7). */
  articleCount: number;
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
 */
export async function searchWidgetKb(
  key: string,
  q: string,
): Promise<WidgetArticleSummary[]> {
  return apiFetch<WidgetArticleSummary[]>(
    `/widget/${encodeURIComponent(key)}/kb/search?q=${encodeURIComponent(q)}`,
    { auth: false },
  );
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

/**
 * `GET /widget/{key}/kb/{path}`, resolved to the article it names.
 *
 * `null` on anything that is not a live article: unknown path, a category
 * (the widget never browses collections, only opens articles a search
 * returned), or a 404 from an unknown key. See `getPublicNode` in
 * `lib/api/public.ts` for the same idiom, one door over.
 */
export async function getWidgetArticle(
  key: string,
  path: string,
): Promise<WidgetArticle | null> {
  try {
    // Encoded per segment, not as one string -- `path` is slash-joined
    // ("billing/refunds") and the API's catch-all expects those slashes
    // intact. See `getPublicNode` in `lib/api/public.ts` for the same idiom.
    const encoded = path.split("/").map(encodeURIComponent).join("/");
    const node = await apiFetch<{ kind: "category" | "article"; article?: WidgetArticle }>(
      `/widget/${encodeURIComponent(key)}/kb/${encoded}`,
      { auth: false },
    );
    return node.kind === "article" && node.article ? node.article : null;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
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
