import { PageHeader } from "@/components/console/page-header";
import { IntegrationGrid } from "@/components/settings/integration-grid";
import { getIntegrations } from "@/lib/mock/settings";
import { requireAdmin } from "@/lib/api/workspace";

export const metadata = { title: "Integrations" };

export default async function IntegrationsPage() {
  await requireAdmin();

  const integrations = await getIntegrations();

  return (
    <>
      <PageHeader
        title="Integrations"
        description="Connect the tools your agent reads from when it prepares a resolution."
      />
      <IntegrationGrid integrations={integrations} />
    </>
  );
}
