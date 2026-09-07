import { Suspense, type ReactNode } from "react";

import { Sidebar } from "@/components/console/sidebar";
import { TopBar } from "@/components/console/top-bar";
import { OnboardingProvider } from "@/components/onboarding/onboarding-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getDraftCount, getStatusCounts } from "@/lib/api/conversations";
import { getLabels } from "@/lib/api/labels";
import { getSetupTasks } from "@/lib/api/team";
import { getCurrentUser, getWorkspace, isAdmin } from "@/lib/api/workspace";

export default async function ConsoleLayout({
  children,
}: {
  children: ReactNode;
}) {
  const [
    statusCounts,
    draftCount,
    labels,
    workspace,
    currentUser,
    setupTasks,
    admin,
  ] = await Promise.all([
    getStatusCounts(),
    getDraftCount(),
    getLabels(),
    getWorkspace(),
    getCurrentUser(),
    getSetupTasks(),
    isAdmin(),
  ]);

  return (
    <TooltipProvider delayDuration={250}>
      <OnboardingProvider isAdmin={admin}>
        <div className="flex h-screen flex-col overflow-hidden">
          <TopBar
            workspaceName={workspace.name}
            userName={currentUser.name}
            userMonogram={currentUser.monogram}
            isAdmin={admin}
          />
          <div className="flex min-h-0 flex-1">
            <Suspense
              fallback={
                <div className="w-60 shrink-0 border-r border-ink-200 bg-white" />
              }
            >
              <Sidebar
                statusCounts={statusCounts}
                draftCount={draftCount}
                setupTasks={setupTasks}
                labels={labels}
                isAdmin={admin}
              />
            </Suspense>
            <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
          </div>
        </div>
      </OnboardingProvider>
    </TooltipProvider>
  );
}
