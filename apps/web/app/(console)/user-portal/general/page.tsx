import { PageHeader } from "@/components/console/page-header";
import { SettingSection } from "@/components/console/setting-section";
import { PortalActions } from "@/components/portal/portal-actions";
import { PortalUrlField } from "@/components/portal/portal-url-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getPortalSettings } from "@/lib/mock/workspace";

export const metadata = { title: "Portal · General" };

export default async function PortalGeneralPage() {
  const portal = await getPortalSettings();

  return (
    <>
      <PageHeader
        title="General"
        description="Where your customers go to write in and track their tickets."
        actions={<PortalActions />}
      />

      <div className="space-y-4">
        <SettingSection
          title="Portal settings"
          action={
            <Badge variant={portal.status === "deployed" ? "positive" : "neutral"}>
              {portal.status === "deployed" ? "Deployed" : "Draft"}
            </Badge>
          }
          footer={<Button variant="primary" size="sm">Save</Button>}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="portal-name">Portal name</Label>
              <Input id="portal-name" defaultValue={portal.name} />
            </div>
            <PortalUrlField subdomain={portal.subdomain} domain={portal.domain} />
          </div>
        </SettingSection>

        <SettingSection
          title="Take the portal offline"
          description="Customers will see a short notice instead of the ticket form. Existing tickets are untouched."
          className="border-danger-200"
        >
          <Button variant="danger" size="sm">
            Unpublish portal
          </Button>
        </SettingSection>
      </div>
    </>
  );
}
