"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api/client";
import { updateAiConfig, type AiConfigInput } from "@/lib/api/ai-config";

export type AiConfigResult = { ok: true } | { ok: false; message: string };

/**
 * A non-admin gets a 403 the console already hides these controls for; a
 * negative budget comes back as a 422. Both land here as a message for the
 * form rather than an error boundary. Compare `settings/widget/actions.ts`.
 */
export async function updateAiConfigAction(patch: AiConfigInput): Promise<AiConfigResult> {
  try {
    await updateAiConfig(patch);
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
  revalidatePath("/", "layout");
  return { ok: true };
}
