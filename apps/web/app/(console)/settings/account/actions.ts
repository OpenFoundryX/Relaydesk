"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api/client";

export async function setNotifyOnAssignmentAction(notifyOnAssignment: boolean): Promise<void> {
  await apiFetch("/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ notifyOnAssignment }),
  });
  revalidatePath("/", "layout");
}
