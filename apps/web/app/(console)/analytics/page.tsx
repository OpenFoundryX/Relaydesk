import { AnalyticsFilters } from "@/components/analytics/analytics-filters";
import { MetricCard } from "@/components/analytics/metric-card";
import { PageHeader } from "@/components/console/page-header";
import { PageShell } from "@/components/console/page-shell";
import { TrialStrip } from "@/components/console/trial-strip";
import { getWorkspace } from "@/lib/api/workspace";
import { getMetrics } from "@/lib/mock/analytics";

export const metadata = { title: "Analytics" };

export default async function AnalyticsPage() {
  const [metrics, workspace] = await Promise.all([getMetrics(), getWorkspace()]);

  return (
    <PageShell>
      <TrialStrip daysLeft={workspace.trialDaysLeft} plan={workspace.plan} />

      <PageHeader
        title="Analytics"
        description="Ticket volume and response health across the last 30 days."
        actions={<AnalyticsFilters />}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {metrics.map((series) => (
          <MetricCard key={series.id} series={series} />
        ))}
      </div>
    </PageShell>
  );
}
