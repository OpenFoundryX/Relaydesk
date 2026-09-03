import { Bell } from "lucide-react";

import { EmptyState } from "@/components/console/empty-state";
import { PageHeader } from "@/components/console/page-header";
import { PageShell } from "@/components/console/page-shell";

export const metadata = { title: "Notifications" };

export default function NotificationsPage() {
  return (
    <PageShell width="narrow">
      <PageHeader
        title="Notifications"
        description="Mentions, assignments, and new replies on tickets you follow."
      />
      <EmptyState
        icon={Bell}
        title="You're all caught up"
        description="When someone @-mentions you or assigns you a ticket, it will appear here."
      />
    </PageShell>
  );
}
