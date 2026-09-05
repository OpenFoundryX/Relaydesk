"use server";

import { revalidatePath } from "next/cache";

import { ApiError, apiFetch } from "@/lib/api/client";

export type CreateInviteResult = { ok: true } | { ok: false; message: string };

/**
 * The API mails the invite itself and answers 202 with no body -- there is
 * no link for this action to hand back, only whether the send was accepted.
 */
export async function createInviteAction(
  email: string,
  role: "Admin" | "Agent",
): Promise<CreateInviteResult> {
  try {
    await apiFetch("/team/invites", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    });
    // The new pending row belongs on the team page immediately.
    revalidatePath("/settings/team");
    return { ok: true };
  } catch (error) {
    // A duplicate invite or an existing member surfaces as a Conflict with
    // a message meant to be shown as-is, so the button doesn't just go dead.
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}
