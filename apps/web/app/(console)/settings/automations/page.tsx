import { PageHeader } from "@/components/console/page-header";
import { AutomationSettings } from "@/components/settings/automation-settings";
import { requireAdmin } from "@/lib/api/workspace";

export const metadata = { title: "Automations" };

export default async function AutomationsPage() {
  await requireAdmin();

  return (
    <>
      <PageHeader
        title="Automations"
        description="Rules that run on every message, before anyone on your team sees it."
      />
      <AutomationSettings />
    </>
  );
}
