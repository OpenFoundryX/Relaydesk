"use server";

/* eslint-disable @typescript-eslint/no-unused-vars -- params kept for call-site
   compatibility on these temporary no-op stubs; Task 9 wires each to a real
   mutation endpoint and will use them. */

import { revalidatePath } from "next/cache";

import { createLabel as createLabelApi } from "@/lib/api/labels";
import type { ConversationStatus, Label, Priority } from "@/lib/types";

/** Every mutation touches sidebar counts too, so the whole console refreshes. */
function refresh() {
  revalidatePath("/", "layout");
}

/**
 * Task 7 shipped only the read half of the conversations API, and Task 8
 * deleted the mock store these actions used to call. Task 9 wires each of
 * these to a real PATCH/POST endpoint; until then they are no-ops so the
 * console keeps compiling and the UI's mutating controls fail silently
 * instead of throwing on a deleted import.
 */

export async function setStatusAction(_id: string, _status: ConversationStatus) {
  refresh();
}

export async function setStatusBulkAction(_ids: string[], _status: ConversationStatus) {
  refresh();
}

export async function setPriorityAction(_id: string, _priority: Priority) {
  refresh();
}

export async function setAssigneeAction(_id: string, _assignee: string | null) {
  refresh();
}

export async function toggleLabelAction(_id: string, _labelId: string) {
  refresh();
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
  refresh();
}

export async function discardDraftAction(_id: string) {
  refresh();
}

export async function generateSummaryAction(_id: string) {
  refresh();
}
