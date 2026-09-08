/**
 * Shared analytics helpers used by both the client-side metric card and the
 * server-rendered agent table, so they cannot live in a "use client" module.
 */

/**
 * Mirrors `format_duration` in the API's `services/analytics.py`. Resolution
 * times run to hours, and a Y axis reading "252m" is not a reading.
 */
export function formatDuration(seconds: number) {
  // Round once, then divide -- the same order as `format_duration` in the
  // API's services/analytics.py. Rounding the seconds component on its own
  // turns 479.5 into "7m 60s", and the API really does send fractional
  // seconds: a duration point is a Postgres avg().
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`;
}

export const RANGES = [
  { id: "7d", label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
  { id: "90d", label: "Last 90 days" },
  { id: "12m", label: "Last 12 months" },
] as const;

/** Anything else in the URL falls back rather than 422-ing the page: a
 *  hand-edited query string should not be an error screen. The API is the
 *  authority and refuses an unknown range on its own. */
export function safeRange(raw: string | undefined): string {
  return RANGES.some((option) => option.id === raw) ? raw! : "30d";
}

/** The console's own word for "no assignee", matching the API's. */
export const UNASSIGNED = "unassigned";

/**
 * The same fallback as `safeRange`, for the same reason. The API answers an
 * assignee who is not a member of the workspace with a 422 — deliberately,
 * so a stale console cannot render zeros and pass them off as a quiet month.
 * But a bookmarked `?assignee=` naming a teammate who has since left is not
 * a stale console, it is an ordinary link going out of date, and surfacing
 * it as the console error boundary gives the reader "the change may not
 * have been saved" on a page that saves nothing plus a Try again button
 * that re-renders into the same 422 forever.
 *
 * Falling back to All assignees renders correct, complete data with the
 * select showing which filter is actually in force, which is what the
 * design's "must not silently render zeros" is really asking for.
 * `team` is the assignable roster, so this needs `getTeam()` to have
 * resolved first — one round trip on a page that already makes twenty.
 */
export function safeAssignee(
  raw: string | undefined,
  team: readonly { id: string }[],
): string | null {
  if (!raw) return null;
  if (raw === UNASSIGNED) return UNASSIGNED;
  return team.some((member) => member.id === raw) ? raw : null;
}
