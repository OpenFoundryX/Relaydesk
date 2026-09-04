import "server-only";

import { apiFetch } from "@/lib/api/client";
import type { Label } from "@/lib/types";

export async function getLabels(): Promise<Label[]> {
  return apiFetch<Label[]>("/labels");
}

export async function createLabel(name: string): Promise<Label> {
  return apiFetch<Label>("/labels", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}
