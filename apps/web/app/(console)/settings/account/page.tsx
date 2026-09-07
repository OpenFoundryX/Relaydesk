import { PageHeader } from "@/components/console/page-header";
import { AccountSettings } from "@/components/settings/account-settings";
import { getCurrentUser } from "@/lib/api/workspace";
import { timeZoneOptions } from "@/lib/time-zones";

export const metadata = { title: "Account" };

export default async function AccountPage() {
  const currentUser = await getCurrentUser();

  return (
    <>
      <PageHeader
        title="Account"
        description="Your personal profile and notification preferences."
      />
      <AccountSettings
        user={currentUser}
        timeZones={timeZoneOptions(currentUser.timeZone)}
      />
    </>
  );
}
