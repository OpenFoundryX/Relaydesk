import "server-only";

import { apiFetch } from "./client";
import type { AnalyticsResponse } from "@/lib/types";

/** Not `cache`d: the range and assignee are the whole point, and two
 *  different filters are two different requests. */
export async function getAnalytics(
  range: string,
  assignee: string | null,
): Promise<AnalyticsResponse> {
  const query = new URLSearchParams({ range });
  if (assignee) query.set("assignee", assignee);
  return apiFetch<AnalyticsResponse>(`/analytics?${query}`);
}
