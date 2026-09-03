import { Suspense, type ReactNode } from "react";

import { Sidebar } from "@/components/console/sidebar";
import { TopBar } from "@/components/console/top-bar";
import { OnboardingProvider } from "@/components/onboarding/onboarding-provider";
import { TrialBanner } from "@/components/console/trial-banner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getSetupTasks } from "@/lib/api/team";
import { getCurrentUser, getWorkspace } from "@/lib/api/workspace";
import { getDraftCount, getLabels, getStatusCounts } from "@/lib/mock/conversations";

export default async function ConsoleLayout({
  children,
}: {
  children: ReactNode;
}) {
  const [statusCounts, draftCount, labels, workspace, currentUser, setupTasks] =
    await Promise.all([
      getStatusCounts(),
      getDraftCount(),
      getLabels(),
      getWorkspace(),
      getCurrentUser(),
      getSetupTasks(),
    ]);

  return (
    <TooltipProvider delayDuration={250}>
      <OnboardingProvider>
        <div className="flex h-screen flex-col overflow-hidden">
          {workspace.trialDaysLeft > 0 && <TrialBanner daysLeft={workspace.trialDaysLeft} />}
          <TopBar
            workspaceName={workspace.name}
            userName={currentUser.name}
            userMonogram={currentUser.monogram}
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
              />
            </Suspense>
            <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
          </div>
        </div>
      </OnboardingProvider>
    </TooltipProvider>
  );
}
