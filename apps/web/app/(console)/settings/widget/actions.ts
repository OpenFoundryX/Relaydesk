"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api/client";
import {
  createWidgetKey,
  deleteWidgetKey,
  updateWidgetKey,
  type WidgetKeyInput,
} from "@/lib/api/widget-keys";

export type WidgetKeyResult = { ok: true } | { ok: false; message: string };

function refresh() {
  revalidatePath("/", "layout");
}

/**
 * A non-admin gets a 403 the console already hides these controls for; a bad
 * origin (not a URL, or missing scheme) comes back as a 422. Both land here
 * as a message for the dialog rather than an error boundary. Compare
 * `settings/custom-webhooks/actions.ts`.
 */
async function attempt(work: () => Promise<unknown>): Promise<WidgetKeyResult> {
  try {
    await work();
    refresh();
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

export async function createWidgetKeyAction(input: WidgetKeyInput): Promise<WidgetKeyResult> {
  return attempt(() => createWidgetKey(input));
}

export async function updateWidgetKeyAction(
  id: string,
  patch: Partial<WidgetKeyInput> & { active?: boolean },
): Promise<WidgetKeyResult> {
  return attempt(() => updateWidgetKey(id, patch));
}

export async function deleteWidgetKeyAction(id: string): Promise<WidgetKeyResult> {
  return attempt(() => deleteWidgetKey(id));
}
