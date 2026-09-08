"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api/client";
import { updateWorkspace } from "@/lib/api/workspace";

export type PortalActionResult = { ok: true } | { ok: false; message: string };

/**
 * The workspace's name and monogram are chrome on every console page and on
 * the help centre's hero, so the whole tree refreshes rather than this one
 * route -- the same blunt instrument knowledge-base/actions.ts uses.
 */
export async function saveWorkspaceIdentityAction(
  name: string,
  monogram: string,
): Promise<PortalActionResult> {
  try {
    await updateWorkspace({ name, monogram });
  } catch (error) {
    // A 403 (only an admin may change this) and a rejected monogram are
    // both worth reading. Anything else is a bug or an outage and belongs
    // to the error boundary.
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
  revalidatePath("/", "layout");
  return { ok: true };
}
