import { AgentTable } from "@/components/analytics/agent-table";
import { AnalyticsFilters } from "@/components/analytics/analytics-filters";
import { MetricCard } from "@/components/analytics/metric-card";
import { PageHeader } from "@/components/console/page-header";
import { PageShell } from "@/components/console/page-shell";
import { getAnalytics } from "@/lib/api/analytics";
import { getTeam } from "@/lib/api/team";
import { requireAdmin } from "@/lib/api/workspace";
import { safeRange } from "@/lib/analytics";

export const metadata = { title: "Analytics" };

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string; assignee?: string }>;
}) {
  await requireAdmin();

  const params = await searchParams;
  const range = safeRange(params.range);
  const assignee = params.assignee ?? null;
  const [report, team] = await Promise.all([getAnalytics(range, assignee), getTeam()]);

  // A pending invite has no user id yet, so it cannot be assigned to or
  // filtered by -- the same rule the assignee picker in the inbox uses.
  const assignableTeam = team
    .filter((member): member is typeof member & { userId: string } => member.userId !== null)
    .map((member) => ({ id: member.userId, name: member.name }));

  return (
    <PageShell>
      <PageHeader
        title="Analytics"
        description="Ticket volume and response health across the selected period."
        actions={
          <AnalyticsFilters team={assignableTeam} range={range} assignee={assignee} />
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {report.series.map((series) => (
          <MetricCard key={series.id} series={series} />
        ))}
      </div>

      <AgentTable rows={report.agents} />
    </PageShell>
  );
}
