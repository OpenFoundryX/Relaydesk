import { PageShell } from "@/components/console/page-shell";
import { Skeleton, SkeletonScreen } from "@/components/ui/skeleton";

export default function AnalyticsLoading() {
  return (
    <PageShell>
      <SkeletonScreen label="Loading analytics">
        <div className="mb-5 flex items-start justify-between gap-6">
          <div className="space-y-2">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-3.5 w-72" />
          </div>
          <Skeleton className="h-7 w-36 shrink-0 rounded-md" />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {[0, 1, 2, 3].map((index) => (
            <div
              key={index}
              className="rounded-lg border border-ink-200 bg-white p-5"
            >
              <Skeleton className="h-3.5 w-28" />
              <Skeleton className="mt-3 h-8 w-24" />
              <Skeleton className="mt-4 h-28 w-full rounded-md" />
            </div>
          ))}
        </div>
      </SkeletonScreen>
    </PageShell>
  );
}
