import { PageHeader } from "@/components/console/page-header";
import { AccountSettings } from "@/components/settings/account-settings";
import { timeZones } from "@/lib/mock/settings";
import { currentUser } from "@/lib/mock/workspace";

export const metadata = { title: "Account" };

export default function AccountPage() {
  return (
    <>
      <PageHeader
        title="Account"
        description="Your personal profile and notification preferences."
      />
      <AccountSettings user={currentUser} timeZones={timeZones} />
    </>
  );
}
