/**
 * Shared analytics helpers used by both the client-side metric card and the
 * server-rendered agent table, so they cannot live in a "use client" module.
 */

/**
 * Mirrors `format_duration` in the API's `services/analytics.py`. Resolution
 * times run to hours, and a Y axis reading "252m" is not a reading.
 */
export function formatDuration(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  const rest = Math.round(seconds % 60);
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`;
}
