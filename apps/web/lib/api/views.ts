import "server-only";

import { apiFetch } from "@/lib/api/client";
import type { SavedView } from "@/lib/types";

export async function getViews(): Promise<SavedView[]> {
  return apiFetch<SavedView[]>("/views");
}
