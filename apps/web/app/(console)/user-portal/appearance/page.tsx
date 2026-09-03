import { PageHeader } from "@/components/console/page-header";
import { AppearanceSettings } from "@/components/portal/appearance-settings";
import { PortalActions } from "@/components/portal/portal-actions";
import { getPortalSettings } from "@/lib/mock/workspace";

export const metadata = { title: "Portal · Appearance" };

export default async function PortalAppearancePage() {
  const portal = await getPortalSettings();

  return (
    <>
      <PageHeader
        title="Appearance"
        description="How the portal looks to your customers."
        actions={<PortalActions />}
      />
      <AppearanceSettings headline={portal.headline} intro={portal.intro} />
    </>
  );
}
