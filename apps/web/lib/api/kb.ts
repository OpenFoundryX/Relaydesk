import "server-only";

import { cache } from "react";

import { ApiError, apiFetch } from "@/lib/api/client";
import type {
  ArticleStatus,
  KbArticle,
  KbArticleSummary,
  KbCategory,
  KbScope,
} from "@/lib/types";

export const getCategories = cache(async (scope: KbScope): Promise<KbCategory[]> => {
  return apiFetch<KbCategory[]>(`/kb/categories?scope=${scope}`);
});

export interface ArticleQuery {
  scope?: KbScope;
  status?: ArticleStatus;
  /** Full-text search across title, excerpt and body. */
  q?: string;
}

/**
 * `cache()` memoises on argument identity, so a caller handing it a fresh
 * `{ scope: "internal" }` literal would miss every single time. The
 * memoised function therefore takes the built query string -- a primitive
 * two call sites can actually match on -- and `getArticles` below is the
 * object-shaped wrapper around it.
 */
const articlesFor = cache(async (query: string): Promise<KbArticleSummary[]> => {
  return apiFetch<KbArticleSummary[]>(`/kb/articles${query}`);
});

export async function getArticles(
  params: ArticleQuery = {},
): Promise<KbArticleSummary[]> {
  const query = new URLSearchParams();
  if (params.scope) query.set("scope", params.scope);
  if (params.status) query.set("status", params.status);
  if (params.q) query.set("q", params.q);
  return articlesFor(query.size > 0 ? `?${query}` : "");
}

/**
 * A missing article comes back as `null` so the page can render Next's real
 * 404 (via `notFound()`) instead of an uncaught error turning into a 500 --
 * the idiom `getConversation` uses. A 422 lands here too: the article id is
 * a path parameter typed as a UUID, so `/knowledge-base/not-a-uuid` is
 * rejected before the row is ever looked up. To a reader following a stale
 * or mistyped link those are the same thing, and both mean "no such
 * article".
 */
export const getArticle = cache(async (id: string): Promise<KbArticle | null> => {
  try {
    return await apiFetch<KbArticle>(`/kb/articles/${id}`);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) {
      return null;
    }
    throw error;
  }
});

export async function createArticle(
  categoryId: string,
  title: string,
): Promise<KbArticle> {
  return apiFetch<KbArticle>("/kb/articles", {
    method: "POST",
    body: JSON.stringify({ categoryId, title }),
  });
}

export interface ArticlePatch {
  title?: string;
  excerpt?: string;
  /** ProseMirror JSON, straight from the editor. */
  doc?: unknown;
  categoryId?: string;
}

export async function updateArticle(
  id: string,
  patch: ArticlePatch,
): Promise<KbArticle> {
  return apiFetch<KbArticle>(`/kb/articles/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function setArticleStatus(
  id: string,
  status: ArticleStatus,
): Promise<KbArticle> {
  return apiFetch<KbArticle>(`/kb/articles/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export async function deleteArticle(id: string): Promise<void> {
  await apiFetch(`/kb/articles/${id}`, { method: "DELETE" });
}

export async function createCategory(
  name: string,
  scope: KbScope,
): Promise<KbCategory> {
  return apiFetch<KbCategory>("/kb/categories", {
    method: "POST",
    body: JSON.stringify({ name, scope }),
  });
}

export async function updateCategory(
  id: string,
  patch: { name?: string; position?: number },
): Promise<KbCategory> {
  return apiFetch<KbCategory>(`/kb/categories/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteCategory(id: string): Promise<void> {
  await apiFetch(`/kb/categories/${id}`, { method: "DELETE" });
}

export interface KbImage {
  id: string;
  /** The API's own path for the file. The console reads it through the
   * `/api/kb/images/{id}` proxy instead, which attaches the session. */
  url: string;
}

export async function uploadArticleImage(
  articleId: string,
  file: File,
): Promise<KbImage> {
  const body = new FormData();
  body.set("file", file);
  return apiFetch<KbImage>(`/kb/articles/${articleId}/images`, {
    method: "POST",
    body,
  });
}
