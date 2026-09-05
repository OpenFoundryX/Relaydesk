"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError } from "@/lib/api/client";
import {
  createArticle,
  createCategory,
  setArticleStatus,
  updateArticle,
  uploadArticleImage,
} from "@/lib/api/kb";
import type { ArticleStatus, KbScope } from "@/lib/types";

export type KbActionResult = { ok: true } | { ok: false; message: string };

/**
 * Every mutation here changes what the list page and the sidebar counts
 * show, so the whole console refreshes -- the same blunt instrument
 * settings/channels/actions.ts uses.
 */
function refresh() {
  revalidatePath("/", "layout");
}

/**
 * Turns the API's own rejection into something the caller can show.
 *
 * These are all messages worth reading rather than swallowing: a reserved
 * category slug ("images", "search"), a 403 because only an admin may
 * create a category, an image over the size cap or of a type that cannot be
 * rendered inline, a status transition the state machine refuses. Anything
 * that is not an `ApiError` is a bug or an outage and is rethrown to the
 * error boundary.
 */
function failure(error: unknown): { ok: false; message: string } {
  if (error instanceof ApiError) return { ok: false, message: error.message };
  throw error;
}

export async function createCategoryAction(
  name: string,
  scope: KbScope,
): Promise<KbActionResult> {
  try {
    await createCategory(name, scope);
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true };
}

/**
 * On success this redirects into the new article, and the caller's promise
 * resolves with nothing at all -- Next turns the redirect into a navigation
 * rather than a return value. So a result here always means a failure, and
 * `void` is the honest way to say the success path hands back nothing.
 */
export async function createArticleAction(
  categoryId: string,
  title: string,
): Promise<{ ok: false; message: string } | void> {
  let id: string;
  try {
    id = (await createArticle(categoryId, title)).id;
  } catch (error) {
    return failure(error);
  }
  refresh();
  // Outside the try: `redirect` works by throwing, and a catch that
  // rethrew anything but an ApiError would still be a trap worth avoiding.
  redirect(`/knowledge-base/${id}`);
}

export async function saveArticleAction(
  id: string,
  patch: { title: string; excerpt: string; doc: unknown },
): Promise<KbActionResult> {
  try {
    await updateArticle(id, patch);
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true };
}

export type StatusActionResult =
  | { ok: true; status: ArticleStatus }
  | { ok: false; message: string };

export async function setArticleStatusAction(
  id: string,
  status: ArticleStatus,
): Promise<StatusActionResult> {
  let saved: ArticleStatus;
  try {
    saved = (await setArticleStatus(id, status)).status;
  } catch (error) {
    return failure(error);
  }
  refresh();
  // The new status comes back from the API rather than being assumed, so
  // the editor's control redraws from what was actually stored.
  return { ok: true, status: saved };
}

export type ImageUploadResult =
  | { ok: true; id: string }
  | { ok: false; message: string };

/**
 * Takes `FormData` rather than a `File` because that is what a Server
 * Action can carry a file in, and the editor already has one in hand from
 * a paste or a drop.
 */
export async function uploadArticleImageAction(
  articleId: string,
  form: FormData,
): Promise<ImageUploadResult> {
  const file = form.get("file");
  if (!(file instanceof File)) {
    return { ok: false, message: "No image was attached." };
  }
  try {
    const image = await uploadArticleImage(articleId, file);
    return { ok: true, id: image.id };
  } catch (error) {
    return failure(error);
  }
}
