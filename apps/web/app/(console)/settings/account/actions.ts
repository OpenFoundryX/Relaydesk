"use server";

import { revalidatePath } from "next/cache";

import { ApiError, apiFetch } from "@/lib/api/client";

export type AccountActionResult = { ok: true } | { ok: false; message: string };

export async function setNotifyOnAssignmentAction(notifyOnAssignment: boolean): Promise<void> {
  await apiFetch("/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ notifyOnAssignment }),
  });
  revalidatePath("/", "layout");
}

export async function setNameAction(name: string): Promise<AccountActionResult> {
  return patchMe({ name });
}

export async function setTimeZoneAction(timeZone: string): Promise<AccountActionResult> {
  return patchMe({ timeZone });
}

/**
 * The layout is revalidated, not just this page: the name and its derived
 * monogram are rendered by the top bar, so a save that only refreshed the
 * form would leave the avatar showing the old initials until a hard reload.
 */
async function patchMe(body: Record<string, string>): Promise<AccountActionResult> {
  try {
    await apiFetch("/auth/me", { method: "PATCH", body: JSON.stringify(body) });
  } catch (error) {
    if (error instanceof ApiError) {
      return { ok: false, message: error.message };
    }
    throw error;
  }
  revalidatePath("/", "layout");
  return { ok: true };
}
