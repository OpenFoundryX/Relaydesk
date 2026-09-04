"use server";

import { revalidatePath } from "next/cache";

import { createLabel as createLabelApi } from "@/lib/api/labels";
import type { ConversationStatus, Label, Priority } from "@/lib/types";

/** Every mutation touches sidebar counts too, so the whole console refreshes. */
function refresh() {
  revalidatePath("/", "layout");
}

/**
 * Task 9 wires each of these to a real PATCH/POST endpoint. Until then they
 * throw rather than no-op: a mutating control that appears to succeed and
 * silently discards the change is worse than one that visibly fails.
 */
function notImplemented(action: string): never {
  throw new Error(`${action} is not wired to the API yet (Task 9).`);
}

export async function setStatusAction(_id: string, _status: ConversationStatus) {
  notImplemented("setStatusAction");
}

export async function setStatusBulkAction(_ids: string[], _status: ConversationStatus) {
  notImplemented("setStatusBulkAction");
}

export async function setPriorityAction(_id: string, _priority: Priority) {
  notImplemented("setPriorityAction");
}

export async function setAssigneeAction(_id: string, _assignee: string | null) {
  notImplemented("setAssigneeAction");
}

export async function toggleLabelAction(_id: string, _labelId: string) {
  notImplemented("toggleLabelAction");
}

/**
 * Labels themselves DO have a real endpoint already (Task 7/8), so creation
 * is wired for real. Attaching the new label to `conversationId` is not —
 * that half waits on Task 9's conversation-label mutation route.
 */
export async function createLabelAction(name: string, _conversationId?: string): Promise<Label> {
  const label = await createLabelApi(name);
  refresh();
  return label;
}

export async function sendReplyAction(_id: string, _body: string, _resolve: boolean) {
  notImplemented("sendReplyAction");
}

export async function discardDraftAction(_id: string) {
  notImplemented("discardDraftAction");
}

/**
 * Deliberate permanent no-op, not a stand-in for missing wiring like the
 * functions above: summary generation belongs to a later agentic slice, and
 * nothing is expected to happen when this is called until that slice lands.
 */
export async function generateSummaryAction(_id: string) {
  refresh();
}
