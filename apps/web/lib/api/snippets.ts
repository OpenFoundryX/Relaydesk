import "server-only";

import { cache } from "react";

import { apiFetch } from "./client";
import type { Snippet } from "@/lib/types";

/**
 * Every snippet in the workspace.
 *
 * Readable by agents as well as admins — the API gates only the writes —
 * because this is what the reply composer's `/` menu is built from.
 */
export const getSnippets = cache(async (): Promise<Snippet[]> => {
  return apiFetch<Snippet[]>("/snippets");
});

export async function createSnippet(
  title: string,
  content: string,
): Promise<Snippet> {
  return apiFetch<Snippet>("/snippets", {
    method: "POST",
    body: JSON.stringify({ title, content }),
  });
}

export async function updateSnippet(
  id: string,
  title: string,
  content: string,
): Promise<Snippet> {
  return apiFetch<Snippet>(`/snippets/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title, content }),
  });
}

export async function deleteSnippet(id: string): Promise<void> {
  await apiFetch(`/snippets/${id}`, { method: "DELETE" });
}
