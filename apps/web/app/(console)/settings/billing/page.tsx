import { PageHeader } from "@/components/console/page-header";
import { SettingSection } from "@/components/console/setting-section";
import { PricingDialog } from "@/components/settings/pricing-dialog";
import { Badge } from "@/components/ui/badge";
import { getWorkspace } from "@/lib/api/workspace";
import { getPlans } from "@/lib/mock/settings";

export const metadata = { title: "Billing" };

export default async function BillingPage() {
  const [plans, workspace] = await Promise.all([getPlans(), getWorkspace()]);

  return (
    <>
      <PageHeader
        title="Billing"
        description={`You have ${workspace.trialDaysLeft} days left on your trial. Pick a plan to keep your inbox running once it ends.`}
      />

      <div className="space-y-4">
        <SettingSection
          title="Current plan"
          action={
            <PricingDialog
              plans={plans}
              usage={{
                tickets: workspace.ticketsThisPeriod,
                projected: workspace.projectedTickets,
                seats: workspace.seats,
              }}
            />
          }
        >
          <div className="flex items-baseline gap-2">
            <span className="text-[15px] font-semibold text-ink-900">
              {workspace.plan}
            </span>
            <Badge variant="accent">Trial</Badge>
          </div>
          <p className="mt-1 text-[13px] text-ink-500">
            1,000 tickets a month · {workspace.seats} seats in use
          </p>
        </SettingSection>

        <SettingSection
          title="Usage this period"
          description="Ticket volume is what you are billed on."
        >
          <dl className="grid gap-4 sm:grid-cols-3">
            <Stat label="Tickets handled" value={String(workspace.ticketsThisPeriod)} />
            <Stat label="Projected monthly" value={String(workspace.projectedTickets)} />
            <Stat label="Seats in use" value={String(workspace.seats)} />
          </dl>
        </SettingSection>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-ink-200 px-3 py-2.5">
      <dt className="text-[12px] text-ink-500">{label}</dt>
      <dd className="tabular mt-0.5 text-lg font-semibold tracking-tight text-ink-900">
        {value}
      </dd>
    </div>
  );
}
