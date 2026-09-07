import { PageShell } from "@/components/console/page-shell";
import { Skeleton, SkeletonScreen } from "@/components/ui/skeleton";

/**
 * The console-wide fallback, and the only one that covers a *nested layout*
 * fetching its own data -- knowledge-base/layout.tsx awaits five calls
 * before it renders anything, and a `loading.tsx` inside that segment sits
 * below it, so it cannot stand in for that wait.
 *
 * The sidebar and top bar are in the layout above this boundary, so they
 * stay put: only the content pane is replaced.
 */
export default function ConsoleLoading() {
  return (
    <PageShell>
      <SkeletonScreen label="Loading">
        <div className="mb-5 space-y-2">
          <Skeleton className="h-6 w-44" />
          <Skeleton className="h-3.5 w-72" />
        </div>
        <div className="space-y-3">
          <Skeleton className="h-32 w-full rounded-lg" />
          <Skeleton className="h-32 w-full rounded-lg" />
        </div>
      </SkeletonScreen>
    </PageShell>
  );
}
