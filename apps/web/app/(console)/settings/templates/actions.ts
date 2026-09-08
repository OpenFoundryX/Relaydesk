"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api/client";
import { createSnippet, deleteSnippet, updateSnippet } from "@/lib/api/snippets";

export type SnippetResult = { ok: true } | { ok: false; message: string };

function refresh() {
  // Layout-wide: a snippet is read by the reply composer on every
  // conversation page, not just by Settings -> Templates.
  revalidatePath("/", "layout");
}

/**
 * Every one of these turns an `ApiError` into a message for the dialog
 * rather than an error boundary. Two are routine rather than exceptional: a
 * duplicate title is a 409 the author should see next to the field they
 * typed, and a non-admin gets a 403 the console already hides the controls
 * for. Compare settings/api-keys/actions.ts.
 */
async function attempt(work: () => Promise<unknown>): Promise<SnippetResult> {
  try {
    await work();
    refresh();
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

export async function createSnippetAction(
  title: string,
  content: string,
): Promise<SnippetResult> {
  return attempt(() => createSnippet(title, content));
}

export async function updateSnippetAction(
  id: string,
  title: string,
  content: string,
): Promise<SnippetResult> {
  return attempt(() => updateSnippet(id, title, content));
}

export async function deleteSnippetAction(id: string): Promise<SnippetResult> {
  return attempt(() => deleteSnippet(id));
}
