import "server-only";

import type { SavedView } from "@/lib/types";

/**
 * Stub. Task 10 implements saved views (a real endpoint plus view-based
 * filtering in `getConversations`); until then there are none to list.
 */
export async function getViews(): Promise<SavedView[]> {
  return [];
}
