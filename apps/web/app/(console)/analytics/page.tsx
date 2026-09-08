import { AgentTable } from "@/components/analytics/agent-table";
import { AnalyticsFilters } from "@/components/analytics/analytics-filters";
import { MetricCard } from "@/components/analytics/metric-card";
import { PageHeader } from "@/components/console/page-header";
import { PageShell } from "@/components/console/page-shell";
import { getAnalytics } from "@/lib/api/analytics";
import { getTeam } from "@/lib/api/team";
import { requireAdmin } from "@/lib/api/workspace";
import { safeAssignee, safeRange } from "@/lib/analytics";

export const metadata = { title: "Analytics" };

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string; assignee?: string }>;
}) {
  await requireAdmin();

  const params = await searchParams;
  const range = safeRange(params.range);

  // Sequenced, not `Promise.all`: the assignee in the URL has to be checked
  // against the roster before it reaches the API, which 422s an assignee it
  // does not recognise. A bookmark naming a teammate who has since left the
  // workspace would otherwise land the reader on the console error boundary
  // with a Try again button that re-renders into the same 422 forever.
  const team = await getTeam();

  // A pending invite has no user id yet, so it cannot be assigned to or
  // filtered by -- the same rule the assignee picker in the inbox uses.
  const assignableTeam = team
    .filter((member): member is typeof member & { userId: string } => member.userId !== null)
    .map((member) => ({ id: member.userId, name: member.name }));

  const assignee = safeAssignee(params.assignee, assignableTeam);
  const report = await getAnalytics(range, assignee);

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
