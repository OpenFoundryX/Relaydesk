import type { ReactNode } from "react";

import { PageShell } from "@/components/console/page-shell";
import { TrialStrip } from "@/components/console/trial-strip";
import { workspace } from "@/lib/mock/workspace";

export default function UserPortalLayout({ children }: { children: ReactNode }) {
  return (
    <PageShell className="max-w-4xl">
      <TrialStrip daysLeft={workspace.trialDaysLeft} plan={workspace.plan} />
      {children}
    </PageShell>
  );
}
