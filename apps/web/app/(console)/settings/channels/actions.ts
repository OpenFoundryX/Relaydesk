"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api/client";
import { createEmailChannel, deleteEmailChannel } from "@/lib/api/channels";

export type ChannelActionResult = { ok: true } | { ok: false; message: string };

/** Every mutation touches this page's list, so the whole console refreshes. */
function refresh() {
  revalidatePath("/", "layout");
}

export async function createEmailChannelAction(
  displayName: string,
): Promise<ChannelActionResult> {
  try {
    await createEmailChannel(displayName);
    refresh();
    return { ok: true };
  } catch (error) {
    // A non-admin gets a 403 from the API (the console should already hide
    // these controls for them, but this is what stands between a stale
    // client and an error boundary if it doesn't). Compare
    // settings/team/actions.ts's createInviteAction.
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}

export async function deleteEmailChannelAction(id: string): Promise<ChannelActionResult> {
  try {
    await deleteEmailChannel(id);
    refresh();
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false, message: error.message };
    throw error;
  }
}
