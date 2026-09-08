import { PageHeader } from "@/components/console/page-header";
import { AppearanceSettings } from "@/components/portal/appearance-settings";
import { PortalActions } from "@/components/portal/portal-actions";
import { getPortalSettings } from "@/lib/mock/workspace";
import { getWorkspace } from "@/lib/api/workspace";

export const metadata = { title: "Portal · Appearance" };

export default async function PortalAppearancePage() {
  // The workspace is real; the rest of this page is still mock data.
  const [portal, workspace] = await Promise.all([
    getPortalSettings(),
    getWorkspace(),
  ]);

  return (
    <>
      <PageHeader
        title="Appearance"
        description="How the portal looks to your customers."
        actions={<PortalActions />}
      />
      <AppearanceSettings
        headline={portal.headline}
        intro={portal.intro}
        name={workspace.name}
        monogram={workspace.monogram}
      />
    </>
  );
}
