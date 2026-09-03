import { PageHeader } from "@/components/console/page-header";
import { AutomationSettings } from "@/components/settings/automation-settings";

export const metadata = { title: "Automations" };

export default function AutomationsPage() {
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
