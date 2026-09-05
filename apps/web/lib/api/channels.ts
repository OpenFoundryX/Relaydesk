import "server-only";

import { cache } from "react";

import { apiFetch } from "./client";
import type { ChannelAccount } from "@/lib/types";

export const getEmailChannels = cache(async (): Promise<ChannelAccount[]> => {
  return apiFetch<ChannelAccount[]>("/channels/email");
});

export async function createEmailChannel(displayName: string): Promise<ChannelAccount> {
  return apiFetch<ChannelAccount>("/channels/email", {
    method: "POST",
    body: JSON.stringify({ displayName }),
  });
}

export async function deleteEmailChannel(id: string): Promise<void> {
  await apiFetch(`/channels/email/${id}`, { method: "DELETE" });
}
