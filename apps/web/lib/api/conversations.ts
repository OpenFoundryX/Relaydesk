import "server-only";

import { cache } from "react";

import { ApiError, apiFetch } from "@/lib/api/client";
import type {
  ActivityEvent,
  Conversation,
  ConversationStatus,
  Message,
  StatusCount,
} from "@/lib/types";

interface Page<T> {
  items: T[];
  nextCursor: string | null;
}

interface CountsResponse {
  statuses: StatusCount[];
  drafts: number;
}

export interface ConversationFilters {
  status?: ConversationStatus | "all" | "drafts";
  labelId?: string;
  assigneeId?: string;
  viewId?: string;
}

export async function getConversations(
  filters: ConversationFilters = {},
): Promise<Conversation[]> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) query.set(key, value);
  }
  const suffix = query.size > 0 ? `?${query}` : "";
  const page = await apiFetch<Page<Conversation>>(`/conversations${suffix}`);
  return page.items;
}

export async function getConversation(id: string): Promise<Conversation | null> {
  try {
    return await apiFetch<Conversation>(`/conversations/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getMessages(id: string): Promise<Message[]> {
  return apiFetch<Message[]>(`/conversations/${id}/messages`);
}

export async function getDraft(id: string): Promise<string | null> {
  try {
    const draft = await apiFetch<{ body: string }>(`/conversations/${id}/draft`);
    return draft.body;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getActivity(id: string): Promise<ActivityEvent[]> {
  return apiFetch<ActivityEvent[]>(`/conversations/${id}/activity`);
}

/**
 * The layout calls both getStatusCounts and getDraftCount on every render;
 * cache() collapses them into the single /conversations/counts request they
 * both need instead of issuing it twice.
 */
const getCounts = cache(async (): Promise<CountsResponse> => {
  return apiFetch<CountsResponse>("/conversations/counts");
});

export async function getStatusCounts(): Promise<StatusCount[]> {
  return (await getCounts()).statuses;
}

export async function getDraftCount(): Promise<number> {
  return (await getCounts()).drafts;
}
