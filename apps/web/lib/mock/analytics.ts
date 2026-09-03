import type { MetricPoint, MetricSeries } from "./types";

/** Trailing 30 days ending on the fixture's "today", 30 Aug 2026. */
function buildPoints(values: number[]): MetricPoint[] {
  const end = new Date("2026-08-30T00:00:00Z");
  return values.map((value, index) => {
    const day = new Date(end);
    day.setUTCDate(end.getUTCDate() - (values.length - 1 - index));
    return { date: day.toISOString().slice(0, 10), value };
  });
}

const created = [
  9, 12, 11, 7, 4, 3, 14, 16, 13, 12, 18, 6, 5, 15, 17, 19, 14, 16, 8, 6, 20, 22,
  18, 17, 15, 9, 7, 21, 24, 19,
];

const responded = [
  8, 11, 11, 6, 4, 3, 13, 15, 13, 11, 17, 6, 5, 14, 16, 18, 13, 15, 8, 6, 19, 20,
  17, 16, 14, 9, 7, 20, 22, 18,
];

const resolved = [
  7, 9, 10, 6, 3, 2, 11, 14, 12, 10, 15, 5, 4, 13, 14, 17, 12, 13, 7, 5, 17, 19,
  16, 15, 12, 8, 6, 18, 20, 17,
];

/** Seconds to first response. */
const firstResponse = [
  1420, 1260, 1310, 980, 720, 690, 1180, 1240, 1090, 1010, 1150, 640, 610, 980,
  1040, 1120, 890, 940, 700, 620, 860, 910, 820, 780, 740, 560, 540, 690, 620,
  504,
];

const aiResolved = [
  2, 3, 4, 2, 1, 1, 5, 6, 5, 4, 7, 2, 2, 6, 7, 8, 6, 7, 3, 2, 9, 10, 9, 8, 7, 4,
  3, 10, 12, 11,
];

const backlog = [
  22, 25, 26, 27, 28, 29, 32, 34, 35, 37, 40, 41, 42, 44, 47, 49, 51, 54, 55, 56,
  59, 62, 64, 66, 69, 70, 71, 74, 78, 80,
];

const series: MetricSeries[] = [
  {
    id: "tickets-created",
    label: "Tickets created",
    headline: "412",
    delta: 12,
    format: "count",
    points: buildPoints(created),
  },
  {
    id: "tickets-responded",
    label: "Tickets responded",
    hint: "Tickets that received at least one reply from an agent or the AI.",
    headline: "389",
    delta: 9,
    format: "count",
    points: buildPoints(responded),
  },
  {
    id: "tickets-resolved",
    label: "Tickets resolved",
    headline: "356",
    delta: 18,
    format: "count",
    points: buildPoints(resolved),
  },
  {
    id: "first-response",
    label: "Avg first response time",
    hint: "Measured from ingestion to the first outbound message.",
    headline: "8m 24s",
    delta: -22,
    format: "duration",
    points: buildPoints(firstResponse),
  },
  {
    id: "ai-resolved",
    label: "Resolved without an agent",
    hint: "Closed by the AI agent with no human reply on the thread.",
    headline: "148",
    delta: 34,
    format: "count",
    points: buildPoints(aiResolved),
  },
  {
    id: "backlog",
    label: "Open backlog",
    headline: "80",
    delta: 6,
    format: "count",
    points: buildPoints(backlog),
  },
];

export const dateRanges = [
  { id: "7d", label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
  { id: "90d", label: "Last 90 days" },
  { id: "12m", label: "Last 12 months" },
];

export const assignees = [
  { id: "all", label: "All assignees" },
  { id: "nilesh", label: "Nilesh Pant" },
  { id: "sara", label: "Sara Duval" },
  { id: "unassigned", label: "Unassigned" },
];

export async function getMetrics(): Promise<MetricSeries[]> {
  return series;
}
