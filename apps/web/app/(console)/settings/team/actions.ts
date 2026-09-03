"use server";

import { revalidatePath } from "next/cache";

import { ApiError, apiFetch } from "@/lib/api/client";

interface InviteCreated {
  id: string;
  inviteUrl: string;
}

export type CreateInviteResult =
  | { ok: true; inviteUrl: string }
  | { ok: false; message: string };

export async function createInviteAction(
  email: string,
  role: "Admin" | "Agent",
): Promise<CreateInviteResult> {
  try {
    const created = await apiFetch<InviteCreated>("/team/invites", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    });
    // The new pending row belongs on the team page immediately; it also
    // feeds the sidebar's "Invite your team" setup task once it's accepted.
    revalidatePath("/settings/team");
    return { ok: true, inviteUrl: created.inviteUrl };
  } catch (error) {
    // A duplicate invite or an existing member surfaces as a Conflict with
    // a message meant to be shown as-is, so the button doesn't just go dead.
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}
