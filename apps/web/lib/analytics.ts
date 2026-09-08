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
