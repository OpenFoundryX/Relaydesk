"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api/client";
import { createLabel } from "@/lib/api/labels";
import type { ConversationStatus, Label, Priority } from "@/lib/types";

/** Every mutation touches sidebar counts too, so the whole console refreshes. */
function refresh() {
  revalidatePath("/", "layout");
}

export async function setStatusAction(id: string, status: ConversationStatus) {
  await apiFetch(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
  refresh();
}

export async function setStatusBulkAction(ids: string[], status: ConversationStatus) {
  await apiFetch("/conversations/bulk-status", {
    method: "POST",
    body: JSON.stringify({ ids, status }),
  });
  refresh();
}

export async function setPriorityAction(id: string, priority: Priority) {
  await apiFetch(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ priority }) });
  refresh();
}

export async function setAssigneeAction(id: string, assigneeId: string | null) {
  await apiFetch(`/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ assigneeId }),
  });
  refresh();
}

export async function addLabelAction(id: string, labelId: string) {
  await apiFetch(`/conversations/${id}/labels/${labelId}`, { method: "PUT" });
  refresh();
}

export async function removeLabelAction(id: string, labelId: string) {
  await apiFetch(`/conversations/${id}/labels/${labelId}`, { method: "DELETE" });
  refresh();
}

export async function createLabelAction(
  name: string,
  conversationId?: string,
): Promise<Label> {
  const label = await createLabel(name);
  if (conversationId) {
    await apiFetch(`/conversations/${conversationId}/labels/${label.id}`, { method: "PUT" });
  }
  refresh();
  return label;
}

export async function sendReplyAction(id: string, body: string, resolve: boolean) {
  const trimmed = body.trim();
  if (trimmed) {
    await apiFetch(`/conversations/${id}/replies`, {
      method: "POST",
      body: JSON.stringify({ body: trimmed, resolve }),
    });
  } else if (resolve) {
    await apiFetch(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "resolved" }),
    });
  }
  refresh();
}

export async function discardDraftAction(id: string) {
  await apiFetch(`/conversations/${id}/draft`, { method: "DELETE" });
  refresh();
}

/** No-op until slice 4 gives the agent a summarizer. */
export async function generateSummaryAction(_id: string) {
  return;
}
