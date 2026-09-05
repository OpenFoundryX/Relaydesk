import { PageHeader } from "@/components/console/page-header";
import { PortalActions } from "@/components/portal/portal-actions";
import { PortalKbSettings } from "@/components/portal/portal-kb-settings";
import { getCategories } from "@/lib/api/kb";

export const metadata = { title: "Portal · Knowledge base" };

export default async function PortalKnowledgeBasePage() {
  const categories = await getCategories("external");

  return (
    <>
      <PageHeader
        title="Knowledge base"
        description="What your customers can read on the portal without opening a ticket."
        actions={<PortalActions />}
      />
      <PortalKbSettings categories={categories} />
    </>
  );
}
