"use server";

import { revalidatePath } from "next/cache";

import * as store from "@/lib/mock/conversations";
import type { ConversationStatus, Priority } from "@/lib/mock/types";

/** Every mutation touches sidebar counts too, so the whole console refreshes. */
function refresh() {
  revalidatePath("/", "layout");
}

export async function setStatusAction(id: string, status: ConversationStatus) {
  await store.setStatus(id, status);
  refresh();
}

export async function setStatusBulkAction(ids: string[], status: ConversationStatus) {
  for (const id of ids) await store.setStatus(id, status);
  refresh();
}

export async function setPriorityAction(id: string, priority: Priority) {
  await store.setPriority(id, priority);
  refresh();
}

export async function setAssigneeAction(id: string, assignee: string | null) {
  await store.setAssignee(id, assignee);
  refresh();
}

export async function toggleLabelAction(id: string, labelId: string) {
  await store.toggleLabel(id, labelId);
  refresh();
}

export async function createLabelAction(name: string, conversationId?: string) {
  const label = await store.createLabel(name);
  if (conversationId) await store.toggleLabel(conversationId, label.id);
  refresh();
  return label;
}

export async function sendReplyAction(id: string, body: string, resolve: boolean) {
  const trimmed = body.trim();
  if (trimmed) await store.addReply(id, trimmed);
  if (resolve) await store.setStatus(id, "resolved");
  refresh();
}

export async function discardDraftAction(id: string) {
  await store.discardDraft(id);
  refresh();
}

export async function generateSummaryAction(id: string) {
  await store.generateSummary(id);
  refresh();
}
