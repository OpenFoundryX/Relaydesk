import { PageHeader } from "@/components/console/page-header";
import { IntegrationGrid } from "@/components/settings/integration-grid";
import { getIntegrations } from "@/lib/mock/settings";

export const metadata = { title: "Integrations" };

export default async function IntegrationsPage() {
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
