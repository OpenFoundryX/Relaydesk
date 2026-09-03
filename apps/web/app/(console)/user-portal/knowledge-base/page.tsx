import { PageHeader } from "@/components/console/page-header";
import { PortalActions } from "@/components/portal/portal-actions";
import { PortalKbSettings } from "@/components/portal/portal-kb-settings";
import { getKnowledgeBase } from "@/lib/mock/knowledge-base";

export const metadata = { title: "Portal · Knowledge base" };

export default async function PortalKnowledgeBasePage() {
  const categories = await getKnowledgeBase("external");

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
