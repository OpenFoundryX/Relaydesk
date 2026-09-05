"use server";

import { revalidatePath } from "next/cache";

import { createEmailChannel, deleteEmailChannel } from "@/lib/api/channels";

/** Every mutation touches this page's list, so the whole console refreshes. */
function refresh() {
  revalidatePath("/", "layout");
}

export async function createEmailChannelAction(displayName: string): Promise<void> {
  await createEmailChannel(displayName);
  refresh();
}

export async function deleteEmailChannelAction(id: string): Promise<void> {
  await deleteEmailChannel(id);
  refresh();
}
