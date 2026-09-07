import { PageShell } from "@/components/console/page-shell";
import { Skeleton, SkeletonScreen } from "@/components/ui/skeleton";

/**
 * One screen for the whole settings segment. Every page in it is a header
 * over a stack of `SettingSection` cards, so a single boundary at this level
 * covers all of them without a file each.
 */
export default function SettingsLoading() {
  return (
    <PageShell className="max-w-4xl">
      <SkeletonScreen label="Loading settings">
        <div className="mb-5 space-y-2">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-3.5 w-80" />
        </div>

        <div className="space-y-4">
          {[0, 1, 2].map((index) => (
            <section
              key={index}
              className="rounded-lg border border-ink-200 bg-white"
            >
              <div className="flex items-start justify-between gap-4 p-5">
                <div className="space-y-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3.5 w-64" />
                </div>
                <Skeleton className="h-7 w-24 shrink-0 rounded-md" />
              </div>
              <div className="px-5 pb-5">
                <Skeleton className="h-16 w-full rounded-md" />
              </div>
            </section>
          ))}
        </div>
      </SkeletonScreen>
    </PageShell>
  );
}
