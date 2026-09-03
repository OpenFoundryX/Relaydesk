import type { ReactNode } from "react";

import { PageShell } from "@/components/console/page-shell";
import { TrialStrip } from "@/components/console/trial-strip";
import { getWorkspace } from "@/lib/api/workspace";

export default async function UserPortalLayout({ children }: { children: ReactNode }) {
  const workspace = await getWorkspace();

  return (
    <PageShell className="max-w-4xl">
      <TrialStrip daysLeft={workspace.trialDaysLeft} plan={workspace.plan} />
      {children}
    </PageShell>
  );
}
