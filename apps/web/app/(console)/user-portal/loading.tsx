import { PageShell } from "@/components/console/page-shell";
import { Skeleton, SkeletonScreen } from "@/components/ui/skeleton";

export default function UserPortalLoading() {
  return (
    <PageShell className="max-w-4xl">
      <SkeletonScreen label="Loading portal settings">
        <div className="mb-5 space-y-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-3.5 w-72" />
        </div>
        <div className="space-y-4">
          {[0, 1].map((index) => (
            <section
              key={index}
              className="rounded-lg border border-ink-200 bg-white p-5"
            >
              <Skeleton className="h-4 w-36" />
              <Skeleton className="mt-4 h-24 w-full rounded-md" />
            </section>
          ))}
        </div>
      </SkeletonScreen>
    </PageShell>
  );
}
