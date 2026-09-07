"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api/client";
import { createApiKey, revokeApiKey } from "@/lib/api/api-keys";
import type { ApiKeyScope } from "@/lib/types";

export type ApiKeyActionResult =
  | { ok: true; token: string }
  | { ok: false; message: string };

export type RevokeResult = { ok: true } | { ok: false; message: string };

function refresh() {
  revalidatePath("/", "layout");
}

/**
 * The token comes back to the browser exactly once, here.
 *
 * It is not stored anywhere the page can read again: the API keeps only a
 * SHA-256 digest, so if the dialog is dismissed before the value is copied,
 * the only recourse is to create another key and delete this one. That is
 * what the dialog's own copy says, and it is true rather than a convention.
 */
export async function createApiKeyAction(
  name: string,
  scopes: ApiKeyScope[],
): Promise<ApiKeyActionResult> {
  try {
    const created = await createApiKey(name, scopes);
    refresh();
    return { ok: true, token: created.token };
  } catch (error) {
    // A non-admin gets a 403 from the API. The page already hides these
    // controls for them; this is what stands between a stale client and an
    // error boundary. Compare settings/channels/actions.ts.
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

export async function revokeApiKeyAction(id: string): Promise<RevokeResult> {
  try {
    await revokeApiKey(id);
    refresh();
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}
